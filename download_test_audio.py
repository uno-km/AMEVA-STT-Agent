import os
import subprocess
import sys

# Ensure ffmpeg is in path
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

try:
    import yt_dlp
except ImportError:
    print("yt_dlp not found. Please install it using pip.")
    sys.exit(1)

url = "https://www.youtube.com/watch?v=Wd9XshGEwhE"
output_dir = r"C:\ameva\input"
os.makedirs(output_dir, exist_ok=True)

# Temporarily download full audio to a temp file
temp_file = os.path.join(output_dir, "temp_full_audio.mp3")

# We use a raw template name, yt-dlp will append the extension
outtmpl_path = os.path.join(output_dir, "temp_full_audio")

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': outtmpl_path,
    'quiet': False,
    'ffmpeg_location': r'C:\ffmpeg\bin'
}

print("Downloading full video audio...")
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

# Check if file exists
if os.path.exists(temp_file):
    print("Full audio downloaded successfully. Trimming from 1m to 3m...")
    final_output = os.path.join(output_dir, "test_youtube_1m_3m.mp3")
    
    # Trim using ffmpeg: -ss 60 (1 minute) to 180 (3 minutes), duration 120 seconds
    ffmpeg_cmd = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "-y",
        "-ss", "60",
        "-t", "120",
        "-i", temp_file,
        "-acodec", "copy",
        final_output
    ]
    
    print(f"Running command: {' '.join(ffmpeg_cmd)}")
    res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"Successfully trimmed audio saved to: {final_output}")
        # Also copy it to user's downloads folder if possible
        downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.exists(downloads_folder):
            dest_downloads = os.path.join(downloads_folder, "test_youtube_1m_3m.mp3")
            import shutil
            try:
                shutil.copy2(final_output, dest_downloads)
                print(f"Also copied to Windows Downloads folder: {dest_downloads}")
            except Exception as e:
                print(f"Could not copy to Downloads folder: {e}")
    else:
        print(f"FFmpeg error: {res.stderr}")
    
    # Remove temporary file
    try:
        os.remove(temp_file)
    except Exception as e:
        print(f"Could not remove temp file: {e}")
else:
    print(f"Failed to find temp audio at {temp_file}")
