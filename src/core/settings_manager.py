import json
import os
from PyQt6.QtCore import QObject, pyqtSignal

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "stt": {
        "model": "ggml-medium-q5_0.bin",
        "language": "ko",
        "threads": 4,
        "temperature": 0.0
    },
    "diarization": {
        "margin": 0.5,
        "max_speakers": 4
    },
    "batch": {
        "input_folder": "",
        "output_folder": "",
        "cycle_minutes": 60
    }
}

class SettingsManager(QObject):
    settings_changed = pyqtSignal(dict)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SettingsManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.init_manager()
        return cls._instance

    def init_manager(self):
        super().__init__()
        self.settings = DEFAULT_SETTINGS.copy()
        self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge loaded settings into default settings to ensure all keys exist
                    self._merge_dict(self.settings, loaded)
            except Exception as e:
                print(f"Error loading settings: {e}")
        else:
            self.save_settings()

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            self.settings_changed.emit(self.settings)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def update_settings(self, section, key, value):
        if section in self.settings:
            self.settings[section][key] = value
            self.save_settings()

    def get(self, section, key=None):
        if key:
            return self.settings.get(section, {}).get(key)
        return self.settings.get(section, {})

    def _merge_dict(self, base, override):
        for k, v in override.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._merge_dict(base[k], v)
            else:
                base[k] = v

settings_manager = SettingsManager()
