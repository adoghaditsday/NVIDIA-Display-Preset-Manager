from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Dict, Tuple

MODIFIERS = {
    "ALT": 0x0001,
    "CTRL": 0x0002,
    "SHIFT": 0x0004,
    "WIN": 0x0008,
}

VK = {
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    **{chr(i): i for i in range(0x30, 0x3A)},
    **{chr(i): i for i in range(0x41, 0x5B)},
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PGDN": 0x22,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
}


def parse_hotkey(text: str) -> Tuple[int, int]:
    parts = [p.strip().upper() for p in text.replace("+", " ").split() if p.strip()]
    if len(parts) != 2:
        raise ValueError("Use exactly two commands, example: CTRL+F7 or ALT+G")
    mod_name, key_name = parts
    if mod_name not in MODIFIERS:
        raise ValueError("First command must be CTRL, ALT, SHIFT, or WIN")
    if key_name not in VK:
        raise ValueError("Second command must be a letter, number, function key, or navigation key")
    return MODIFIERS[mod_name], VK[key_name]


class HotkeyManager:
    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._id_to_preset: Dict[int, str] = {}
        self._next_id = 1001

    def start(self, mapping: Dict[str, str]) -> None:
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(mapping,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        for hotkey_id in list(self._id_to_preset.keys()):
            self.user32.UnregisterHotKey(None, hotkey_id)
        self._id_to_preset.clear()

    def _run(self, mapping: Dict[str, str]) -> None:
        self._id_to_preset.clear()
        for preset_name, hotkey in mapping.items():
            if not hotkey:
                continue
            try:
                modifiers, vk = parse_hotkey(hotkey)
                hotkey_id = self._next_id
                self._next_id += 1
                ok = self.user32.RegisterHotKey(None, hotkey_id, modifiers, vk)
                if ok:
                    self._id_to_preset[hotkey_id] = preset_name
            except Exception:
                continue

        msg = wintypes.MSG()
        PM_REMOVE = 0x0001
        WM_HOTKEY = 0x0312
        while not self._stop.is_set():
            while self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    preset = self._id_to_preset.get(msg.wParam)
                    if preset:
                        self.callback(preset)
                self.user32.TranslateMessage(ctypes.byref(msg))
                self.user32.DispatchMessageW(ctypes.byref(msg))
            self._stop.wait(0.05)
