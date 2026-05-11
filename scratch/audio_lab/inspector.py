import wave
import os
import struct

def inspect_wav(file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return

    try:
        with wave.open(file_path, 'rb') as f:
            params = f.getparams()
            n_channels = params.nchannels
            sample_width = params.sampwidth
            framerate = params.framerate
            n_frames = params.nframes
            
            duration = n_frames / float(framerate)
            
            # Simple RMS check
            read_frames = min(n_frames, framerate)
            frames = f.readframes(read_frames)
            
            # Standard 16-bit PCM
            fmt = f"<{read_frames * n_channels}h"
            samples = struct.unpack(fmt, frames)
            
            # RMS calculation
            sum_sq = sum(float(s)**2 for s in samples)
            rms = (sum_sq / len(samples))**0.5
            
            print("--- Audio Analysis Report ---")
            print(f"File: {os.path.basename(file_path)}")
            print(f"Duration: {duration:.2f} sec")
            print(f"Sample Rate: {framerate} Hz")
            print(f"Channels: {'Stereo' if n_channels == 2 else 'Mono'} ({n_channels} ch)")
            print(f"Bit Depth: {sample_width * 8} bit")
            print(f"RMS Energy: {rms:.2f}")
            print(f"Status: {'Optimal for STT' if framerate == 16000 else 'Resampling required'}")
            print("------------------------------")

    except Exception as e:
        print(f"[ERROR] Analysis failed: {str(e)}")

if __name__ == "__main__":
    target = r"C:\ameva\AMEVA-STT-Agent\input_audios\test_cut_2_small.wav"
    inspect_wav(target)
