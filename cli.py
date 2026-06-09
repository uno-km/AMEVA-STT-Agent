import os
import argparse
import json
import time
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager
from src.utils.report_generator import create_stt_report

def save_meeting_minutes(stt_data, output_prefix):
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    md_lines = [
        "# 🎙️ 자동 생성 회의록 (AMEVA Hybrid STT)",
        f"- **생성 일시:** {now}",
        "- **사용 엔진:** Whisper (Text) + Vosk (Diarization)",
        "", "---", ""
    ]
    txt_lines = [
        "자동 생성 회의록 (AMEVA Hybrid STT)",
        f"생성 일시: {now}",
        "사용 엔진: Whisper (Text) + Vosk (Diarization)",
        "", "="*60, ""
    ]

    prev_speaker = None
    for seg in stt_data:
        speaker_id = seg.get("speaker", "Unknown")
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = seg.get("text", "").strip()
        ts = f"[{start:05.1f}s - {end:05.1f}s]"

        if speaker_id != prev_speaker:
            md_lines.append(f"### 🗣️ {speaker_id}")
            txt_lines.append(f"{speaker_id}")
            prev_speaker = speaker_id

        md_lines.append(f"> {ts} {text}")
        txt_lines.append(f"{ts} {text}")

    md_path = f"{output_prefix}_minutes.md"
    txt_path = f"{output_prefix}_minutes.txt"

    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write("\n".join(md_lines) + "\n")
    with open(txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write("\n".join(txt_lines) + "\n")

    return md_path, txt_path

def process_file(pipeline, audio_path, args, log_print):
    print(f"\n[Processing] {os.path.basename(audio_path)}")
    start_t = time.time()
    try:
        final_json_path, pca_coords, labels, final_cluster_path, dia_texts, full_text = pipeline.execute(
            audio_path=audio_path,
            output_dir=args.output_dir,
            logger_callback=log_print,
            system_callback=log_print,
            task_id="CLI",
            diarization_enabled=not args.no_diarization
        )
        
        proc_time = time.time() - start_t
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_prefix = os.path.join(args.output_dir, f"CLI_{base_name}")

        chart_path = None
        if not args.no_diarization and len(pca_coords) > 0:
            try:
                import plotly.express as px
                import pandas as pd
                df_c = pd.DataFrame({
                    "PCA1": [c[0] for c in pca_coords],
                    "PCA2": [c[1] for c in pca_coords],
                    "Speaker": [str(lbl) for lbl in labels]
                })
                fig = px.scatter(df_c, x="PCA1", y="PCA2", color="Speaker", title="Speaker Clustering")
                chart_path = os.path.join(args.output_dir, f"CLI_{base_name}_chart.png")
                fig.write_image(chart_path)
            except Exception as e:
                log_print(f"⚠️ Failed to generate chart: {e}")

        stt_data = []
        if os.path.exists(final_json_path):
            with open(final_json_path, 'r', encoding='utf-8') as f:
                stt_data = json.load(f)

        if args.generate_minutes and stt_data:
            md_p, txt_p = save_meeting_minutes(stt_data, output_prefix)
            log_print(f"📝 Meeting minutes saved: {md_p}")

        if args.generate_report and stt_data:
            stats = {
                "processing_time_sec": proc_time,
                "model": args.model,
                "language": args.language,
                "diarization_enabled": not args.no_diarization
            }
            report_path = create_stt_report(audio_path, args.output_dir, stats, stt_data, chart_path, task_id="CLI")
            log_print(f"📑 Word Report saved: {report_path}")

        print("✅ Success!")
        
    except Exception as e:
        print(f"❌ Failed processing {audio_path}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="AMEVA STT Agent - Advanced CLI Edition")
    parser.add_argument("--audio", type=str, help="Path to single input audio file")
    parser.add_argument("--batch_dir", type=str, help="Path to directory for batch processing")
    parser.add_argument("--output_dir", type=str, default="./outputs", help="Output directory")
    parser.add_argument("--model", type=str, default="medium", choices=["tiny", "small", "medium", "large", "turbo"], help="Whisper model size")
    parser.add_argument("--language", type=str, default="ko", help="Language code (e.g. ko, en, auto)")
    parser.add_argument("--threads", type=int, default=4, help="Number of CPU threads to use")
    parser.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for Diarization")
    parser.add_argument("--no_diarization", action="store_true", help="Disable Vosk speaker diarization")
    parser.add_argument("--generate_report", action="store_true", help="Generate enterprise Word document report")
    parser.add_argument("--generate_minutes", action="store_true", help="Generate Markdown & TXT meeting minutes")

    args = parser.parse_args()

    if not args.audio and not args.batch_dir:
        print("❌ Error: Must provide either --audio or --batch_dir")
        return

    settings_manager.set("stt", {
        "model": args.model,
        "language": args.language,
        "threads": args.threads,
        "speakers": args.speakers
    })

    print(f"🚀 Starting AMEVA STT Agent Advanced CLI")
    print(f"🤖 Model: {args.model} | Lang: {args.language} | Threads: {args.threads}")
    print(f"🗣️ Diarization: {'Disabled' if args.no_diarization else f'Enabled (K={args.speakers})'}")
    print("-" * 50)

    pipeline = STTPipeline()
    def log_print(msg): print(msg)
    os.makedirs(args.output_dir, exist_ok=True)

    if args.audio:
        if not os.path.exists(args.audio):
            print(f"❌ Error: Audio file not found at {args.audio}")
            return
        process_file(pipeline, args.audio, args, log_print)

    if args.batch_dir:
        if not os.path.isdir(args.batch_dir):
            print(f"❌ Error: Directory not found at {args.batch_dir}")
            return
        print(f"📁 Starting Batch Processing on: {args.batch_dir}")
        for f in os.listdir(args.batch_dir):
            if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.mp4', '.mkv', '.avi')):
                p = os.path.join(args.batch_dir, f)
                process_file(pipeline, p, args, log_print)
                
    print("-" * 50)
    print("🎉 All tasks completed!")

if __name__ == "__main__":
    main()
