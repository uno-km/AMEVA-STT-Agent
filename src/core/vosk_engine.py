import os
import time
import json
import wave
import traceback
from vosk import Model as VoskModel, SpkModel, KaldiRecognizer

class VoskEngineCPU:
    def __init__(self, model_path=r"C:\ameva\AI_Models\vosk\ko-model", spk_model_path=r"C:\ameva\AI_Models\vosk\spk-model"):
        self.model_path = model_path
        self.spk_model_path = spk_model_path

    def extract_forced_embeddings(self, audio_path, stt_segments, output_queue):
        output_queue.put(("log", f"[Diarization Worker] Forced Diarization 가동 중 (총 {len(stt_segments)}개 문장)..."))
        start_time = time.time()
        
        if not os.path.exists(self.model_path) or not os.path.exists(self.spk_model_path):
            output_queue.put(("log", f"❌ 치명적 오류: Vosk 화자 모델 폴더가 삭제되었습니다!"))
            output_queue.put(("system", f"⚠️ Vosk 모델 누락!"))
            output_queue.put(("dia_result", ([], [])))
            return

        try:
            model = VoskModel(self.model_path)
            spk_model = SpkModel(self.spk_model_path)
            
            wf = wave.open(audio_path, "rb")
            framerate = wf.getframerate()
            
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                output_queue.put(("system", "❌ 오디오 포맷 오류 (16kHz Mono PCM WAV 필요)"))
                output_queue.put(("dia_result", ([], [])))
                return

            vectors = []
            valid_indices = []
            
            for i, seg in enumerate(stt_segments):
                start_frame = int(seg['start'] * framerate)
                end_frame = int(seg['end'] * framerate)
                num_frames = end_frame - start_frame
                
                if num_frames <= 0: continue
                    
                wf.setpos(start_frame)
                data = wf.readframes(num_frames)
                
                rec = KaldiRecognizer(model, framerate)
                rec.SetWords(True)
                rec.SetSpkModel(spk_model)
                
                rec.AcceptWaveform(data)
                res = json.loads(rec.FinalResult())
                
                if 'spk' in res:
                    vectors.append(res['spk'])
                    valid_indices.append(i)
                    if len(vectors) % 10 == 0:
                        output_queue.put(("log", f"[Diarization] 현재 {len(vectors)}개의 화자 지문 추출 완료..."))

            elapsed = time.time() - start_time
            output_queue.put(("log", f"[Diarization Worker] 완료 ({elapsed:.1f}초) - {len(vectors)}개 화자 지문 추출 성공!"))
            output_queue.put(("dia_result", (vectors, valid_indices)))
        except Exception as e:
            output_queue.put(("system", f"❌ Diarization Error:\n{traceback.format_exc()}"))
            output_queue.put(("dia_result", ([], [])))

def run_vosk_process(audio_path, stt_segments, output_queue):
    engine = VoskEngineCPU()
    engine.extract_forced_embeddings(audio_path, stt_segments, output_queue)
