import os
import urllib.request
import sys

MODELS_DIR = r"C:\ameva\AI_Models"

MODELS_TO_DOWNLOAD = {
    "ggml-medium-q5_0.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium-q5_0.bin",
    "ggml-large-v3-turbo-q5_0.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
}

def download_model(filename, url):
    filepath = os.path.join(MODELS_DIR, filename)
    if os.path.exists(filepath):
        print(f"[*] Model {filename} already exists. Skipping download.")
        return

    print(f"[*] Downloading {filename}...")
    try:
        def reporthook(blocknum, blocksize, totalsize):
            readsofar = blocknum * blocksize
            if totalsize > 0:
                percent = readsofar * 1e2 / totalsize
                s = "\r%5.1f%% %*d / %d" % (
                    percent, len(str(totalsize)), readsofar, totalsize)
                sys.stderr.write(s)
                if readsofar >= totalsize:
                    sys.stderr.write("\n")
            else:
                sys.stderr.write("read %d\n" % (readsofar,))
                
        urllib.request.urlretrieve(url, filepath, reporthook)
        print(f"[*] Successfully downloaded {filename}")
    except Exception as e:
        print(f"[!] Failed to download {filename}: {e}")

if __name__ == "__main__":
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR, exist_ok=True)
        
    for filename, url in MODELS_TO_DOWNLOAD.items():
        download_model(filename, url)
