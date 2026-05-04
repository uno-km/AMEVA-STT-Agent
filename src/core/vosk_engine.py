import time

class VoskEngineCPU:
    def __init__(self):
        pass
        
    def extract_speaker_embeddings(self, audio_path):
        """
        Mock for Vosk speaker embedding extraction on CPU.
        Returns mock timestamps and multi-dimensional vectors representing voice characteristics.
        """
        print(f"[VoskEngine] Starting vector extraction for {audio_path}")
        
        # Simulate processing time
        time.sleep(2)
        
        # Mock embeddings (timestamp, vector)
        return [
            {"start": 0.0, "end": 2.5, "vector": [0.12, 0.45, -0.34, 0.88]}, # Speaker 0
            {"start": 3.0, "end": 5.0, "vector": [-0.85, 0.22, 0.11, -0.45]}  # Speaker 1
        ]
