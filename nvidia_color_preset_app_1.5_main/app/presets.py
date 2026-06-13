from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any

APP_NAME = "NvidiaColorPreset"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent / relative


@dataclass
class ColorPreset:
    brightness: int = 50
    contrast: int = 50
    gamma: float = 1.0
    digital_vibrance: int = 50
    red_channel: int = 100
    green_channel: int = 100
    blue_channel: int = 100
    notes: str = ""

    def normalized(self) -> "ColorPreset":
        self.brightness = max(0, min(100, int(self.brightness)))
        self.contrast = max(0, min(100, int(self.contrast)))
        self.gamma = max(0.5, min(2.5, float(self.gamma)))
        self.digital_vibrance = max(0, min(100, int(self.digital_vibrance)))
        self.red_channel = max(0, min(200, int(getattr(self, "red_channel", 100))))
        self.green_channel = max(0, min(200, int(getattr(self, "green_channel", 100))))
        self.blue_channel = max(0, min(200, int(getattr(self, "blue_channel", 100))))
        return self


class PresetStore:
    def __init__(self) -> None:
        self.path = app_data_dir() / "presets.json"
        self.settings_path = app_data_dir() / "settings.json"
        if not self.path.exists():
            default_path = resource_path("app/default_presets.json")
            if default_path.exists():
                shutil.copy(default_path, self.path)
            else:
                self.save_all({"Normal Color": ColorPreset()})
        if not self.settings_path.exists():
            self.save_settings({"hotkeys_enabled": False, "hotkeys": {}})

    def load_all(self) -> Dict[str, ColorPreset]:
        with self.path.open("r", encoding="utf-8") as f:
            raw: Dict[str, Any] = json.load(f)
        out: Dict[str, ColorPreset] = {}
        for name, vals in raw.items():
            # Older preset files may not contain RGB channel fields; dataclass defaults fill them in.
            allowed = {f.name for f in ColorPreset.__dataclass_fields__.values()}
            clean_vals = {k: v for k, v in vals.items() if k in allowed}
            out[name] = ColorPreset(**clean_vals).normalized()
        return out

    def save_all(self, presets: Dict[str, ColorPreset]) -> None:
        raw = {name: asdict(p.normalized()) for name, p in presets.items()}
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)

    def upsert(self, name: str, preset: ColorPreset) -> None:
        presets = self.load_all()
        presets[name.strip()] = preset.normalized()
        self.save_all(presets)

    def delete(self, name: str) -> None:
        presets = self.load_all()
        presets.pop(name, None)
        self.save_all(presets)

    def load_settings(self) -> Dict[str, Any]:
        with self.settings_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_settings(self, settings: Dict[str, Any]) -> None:
        with self.settings_path.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
