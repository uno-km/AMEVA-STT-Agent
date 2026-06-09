import os
import argparse
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager

def main():
    parser = argparse.ArgumentParser(description="AMEVA STT Agent - CLI Edition")
    parser.add_argument("--audio", type=str, required=True, help="Path to input audio file")
    parser.add_argument("--output_dir", type=str, default="./outputs", help="Output directory")
    parser.add_argument("--model", type=str, default="medium", choices=["tiny", "small", "medium", "large", "turbo"], help="Whisper model size")
    parser.add_argument("--language", type=str, default="ko", help="Language code (e.g. ko, en, auto)")
    parser.add_argument("--threads", type=int, default=4, help="Number of CPU threads to use")
    parser.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for Diarization")
    parser.add_argument("--no_diarization", action="store_true", help="Disable Vosk speaker diarization")

    args = parser.parse_args()

    if not os.path.exists(args.audio):
        print(f"❌ Error: Audio file not found at {args.audio}")
        return

    # Update settings globally for pipeline
    settings_manager.set("stt", {
        "model": args.model,
        "language": args.language,
        "threads": args.threads,
        "speakers": args.speakers
    })

    print(f"🚀 Starting AMEVA STT Agent CLI")
    print(f"🎙️ Target Audio: {args.audio}")
    print(f"🤖 Model: {args.model} | Lang: {args.language} | Threads: {args.threads}")
    print(f"🗣️ Diarization: {'Disabled' if args.no_diarization else f'Enabled (K={args.speakers})'}")
    print("-" * 50)

    pipeline = STTPipeline()
    
    def log_print(msg):
        print(msg)
    
    os.makedirs(args.output_dir, exist_ok=True)

    try:
        final_json_path, pca_coords, labels, final_cluster_path, dia_texts, full_text = pipeline.execute(
            audio_path=args.audio,
            output_dir=args.output_dir,
            logger_callback=log_print,
            system_callback=log_print,
            task_id="CLI",
            diarization_enabled=not args.no_diarization
        )
        print("-" * 50)
        print("✅ Processing Complete!")
        print(f"📄 JSON Result: {final_json_path}")
        if not args.no_diarization:
            print(f"📊 Cluster Result: {final_cluster_path}")
        
    except Exception as e:
        print(f"❌ Pipeline Execution Failed: {str(e)}")

if __name__ == "__main__":
    main()
