import json
import os
from PyQt6.QtCore import QObject, pyqtSignal

class SettingsManager(QObject):
    settings_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.default_settings = {
            "theme": "dark",
            "models_dir": r"C:\ameva\AI_Models",
            "stt": {
                "model": "medium", # small, medium, turbo
                "custom_model_path": "",
                "language": "ko",
                "threads": 4,
                "diarization_enabled": True,
                "speakers": 2,
                "max_offset": 2.0,
                "max_len": 20,
                "split_on_word": True,
                "vad_enabled": False,
                "vad_max_speech_duration": 5,
                "vad_min_silence_duration": 500
            },
            "batch": {
                "input_dir": r"C:\ameva\AMEVA-STT-Agent\input_audios",
                "output_dir": r"C:\ameva\AMEVA-STT-Agent\output_results",
                "interval_min": 1,
                "auto_mode": False,
                "db_file": "stt_batch_log.csv",
                "exception_db_file": "stt_exception_log.csv"
            },
            "ui": {
                "splitter_pos": [400, 400, 400, 400]
            }
        }
        self.settings = self.default_settings.copy()
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._update_nested_dict(self.settings, data)
            except: pass
        else:
            self.save()

    def save(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)
        self.settings_changed.emit(self.settings)

    def _update_nested_dict(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                self._update_nested_dict(base[k], v)
            else:
                base[k] = v

    def get(self, *keys):
        d = self.settings
        for k in keys:
            d = d.get(k, {})
        return d

# Create the global instance
settings_manager = SettingsManager()
