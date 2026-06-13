from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw
import pystray


TRAY_VERSION = "2026-06-07-custom-icon-v7"


def make_fallback_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(32, 32, 38, 255))
    d.ellipse((17, 17, 47, 47), fill=(118, 255, 0, 255))
    d.rectangle((30, 11, 34, 53), fill=(235, 235, 245, 255))
    return img


def load_tray_icon(icon_path_getter: Callable[[], str] | None = None) -> Image.Image:
    if icon_path_getter:
        try:
            path = Path(icon_path_getter())
            if path.exists():
                return Image.open(path).convert("RGBA").resize((64, 64), Image.LANCZOS)
        except Exception:
            pass
    return make_fallback_icon()


class PresetMenuAction:
    def __init__(self, preset_name: str, callback: Callable[[str], None]) -> None:
        self.preset_name = preset_name
        self.callback = callback

    def __call__(self, icon=None, item=None) -> None:
        self.callback(self.preset_name)


class TrayController:
    def __init__(self, open_cb: Callable[[], None], exit_cb: Callable[[], None], preset_cb: Callable[[str], None], icon_path_getter: Callable[[], str] | None = None) -> None:
        self.open_cb = open_cb
        self.exit_cb = exit_cb
        self.preset_cb = preset_cb
        self.icon_path_getter = icon_path_getter
        self.icon: pystray.Icon | None = None
        self.thread: threading.Thread | None = None

    def on_open(self, icon=None, item=None) -> None:
        self.open_cb()

    def on_exit(self, icon=None, item=None) -> None:
        self.exit_cb()

    def _build_menu(self, preset_names: Iterable[str]) -> pystray.Menu:
        preset_items = []
        for name in preset_names:
            preset_items.append(pystray.MenuItem(str(name), PresetMenuAction(str(name), self.preset_cb)))

        if not preset_items:
            preset_items = [pystray.MenuItem("No presets found", None, enabled=False)]

        return pystray.Menu(
            pystray.MenuItem("Open", self.on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Change Preset", pystray.Menu(*preset_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.on_exit),
        )

    def start(self, preset_names: Iterable[str]) -> None:
        self.stop()
        menu = self._build_menu(preset_names)
        self.icon = pystray.Icon("NvidiaColorPreset", load_tray_icon(self.icon_path_getter), "NVIDIA Color Presets", menu)
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
