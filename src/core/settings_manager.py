import json
import os
from PyQt6.QtCore import QObject, pyqtSignal

class SettingsManager(QObject):
    settings_changed = pyqtSignal(dict)
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        super().__init__()
        self.settings_file = "settings.json"
        self.default_settings = {
            "theme": "dark",
            "models_dir": r"C:\ameva\AI_Models",
            "stt": {
                "model": "medium", # small, medium, turbo
                "language": "ko",
                "threads": 4
            },
            "batch": {
                "input_dir": "",
                "output_dir": "",
                "interval_min": 60
            },
            "ui": {
                "splitter_pos": [400, 400, 400, 400]
            }
        }
        self.settings = self.default_settings.copy()
        self.load()
        self._initialized = True

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

settings_manager = SettingsManager()
