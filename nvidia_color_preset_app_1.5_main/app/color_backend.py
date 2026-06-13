from __future__ import annotations

import ctypes
import math
import platform
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Optional


class ColorBackendError(RuntimeError):
    pass


@dataclass
class ApplyResult:
    ok: bool
    message: str


class WindowsGammaRampBackend:
    """
    Applies desktop brightness/contrast/gamma through the Windows GDI gamma ramp.

    This does not hook, inject into, or overlay games. It asks Windows to alter the display
    gamma ramp for the desktop device context. Neutral values are brightness=50,
    contrast=50, gamma=1.0.
    """

    def __init__(self) -> None:
        if platform.system().lower() != "windows":
            raise ColorBackendError("This backend only runs on Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.ReleaseDC.restype = ctypes.c_int
        self.gdi32.SetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]
        self.gdi32.SetDeviceGammaRamp.restype = wintypes.BOOL

    @staticmethod
    def _ramp_value(i: int, brightness: int, contrast: int, gamma: float, channel_strength: int = 100) -> int:
        b_offset = (brightness - 50) / 100.0
        c_scale = max(0.05, contrast / 50.0)
        g = max(0.5, min(2.5, gamma))
        x = i / 255.0
        x = math.pow(max(0.0, min(1.0, x)), 1.0 / g)
        x = ((x - 0.5) * c_scale) + 0.5 + b_offset
        x = max(0.0, min(1.0, x))
        strength = max(0.0, min(2.0, channel_strength / 100.0))
        x = max(0.0, min(1.0, x * strength))
        return int(x * 65535)

    def apply(self, brightness: int, contrast: int, gamma: float, digital_vibrance: int = 50, red_channel: int = 100, green_channel: int = 100, blue_channel: int = 100) -> ApplyResult:
        brightness = max(0, min(100, int(brightness)))
        contrast = max(0, min(100, int(contrast)))
        gamma = max(0.5, min(2.5, float(gamma)))
        red_channel = max(0, min(200, int(red_channel)))
        green_channel = max(0, min(200, int(green_channel)))
        blue_channel = max(0, min(200, int(blue_channel)))

        RampArray = wintypes.WORD * (256 * 3)
        ramp = RampArray()
        channel_strengths = [red_channel, green_channel, blue_channel]
        for channel, strength in enumerate(channel_strengths):
            vals = [self._ramp_value(i, brightness, contrast, gamma, strength) for i in range(256)]
            offset = 256 * channel
            for i, v in enumerate(vals):
                ramp[offset + i] = v

        hdc = self.user32.GetDC(None)
        if not hdc:
            raise ColorBackendError("Could not get desktop device context.")
        try:
            ok = self.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
            if not ok:
                err = ctypes.get_last_error()
                return ApplyResult(False, f"SetDeviceGammaRamp failed. Windows error: {err}")
            return ApplyResult(True, f"Applied brightness={brightness}, contrast={contrast}, gamma={gamma:.2f}, RGB={red_channel}/{green_channel}/{blue_channel}")
        finally:
            self.user32.ReleaseDC(None, hdc)


class NvidiaDvcBackend:
    """
    NVIDIA Digital Vibrance Control backend using documented/known NVAPI DVC entrypoints.

    This touches only the NVIDIA display driver API. It does not inject DLLs, hook graphics APIs,
    draw overlays, inspect processes, or alter game files/shaders.

    NVAPI functions used:
      - NvAPI_Initialize
      - NvAPI_EnumNvidiaDisplayHandle
      - NvAPI_GetDVCInfoEx / NvAPI_SetDVCLevelEx
      - fallback: NvAPI_GetDVCInfo / NvAPI_SetDVCLevel
    """

    NVAPI_OK = 0
    NVAPI_END_ENUMERATION = -7

    ID_INITIALIZE = 0x0150E828
    ID_GET_ERROR_MESSAGE = 0x6C2D048C
    ID_ENUM_NVIDIA_DISPLAY_HANDLE = 0x9ABDD40D
    ID_GET_DVC_INFO = 0x4085DE45
    ID_SET_DVC_LEVEL = 0x172409B4
    ID_GET_DVC_INFO_EX = 0x0E45002D
    ID_SET_DVC_LEVEL_EX = 0x4A82C2B1

    def __init__(self) -> None:
        if platform.system().lower() != "windows":
            raise ColorBackendError("NVAPI only runs on Windows.")

        dll_names = ["nvapi64.dll", "nvapi.dll"] if ctypes.sizeof(ctypes.c_void_p) == 8 else ["nvapi.dll", "nvapi64.dll"]
        last_exc: Optional[Exception] = None
        self.dll = None
        for name in dll_names:
            try:
                self.dll = ctypes.WinDLL(name)
                break
            except Exception as exc:
                last_exc = exc
        if self.dll is None:
            raise ColorBackendError(f"Could not load NVIDIA NVAPI DLL. Last error: {last_exc}")

        self.query = getattr(self.dll, "nvapi_QueryInterface")
        self.query.argtypes = [ctypes.c_uint32]
        self.query.restype = ctypes.c_void_p

        self._initialize()
        self.handles = self._enum_display_handles()
        if not self.handles:
            raise ColorBackendError("No NVIDIA display handles were found. Is this display driven by the NVIDIA GPU?")

    def _fn(self, api_id: int, restype, *argtypes) -> Callable:
        ptr = self.query(ctypes.c_uint32(api_id))
        if not ptr:
            raise ColorBackendError(f"NVAPI function 0x{api_id:08X} is unavailable on this driver.")
        prototype = ctypes.CFUNCTYPE(restype, *argtypes)
        return prototype(ptr)

    @staticmethod
    def _make_version(size: int, version: int = 1) -> int:
        return size | (version << 16)

    def _initialize(self) -> None:
        init = self._fn(self.ID_INITIALIZE, ctypes.c_int)
        status = init()
        if status != self.NVAPI_OK:
            raise ColorBackendError(f"NvAPI_Initialize failed: {self.error_message(status)}")

    def error_message(self, status: int) -> str:
        try:
            buf = ctypes.create_string_buffer(64)
            get_error = self._fn(self.ID_GET_ERROR_MESSAGE, ctypes.c_int, ctypes.c_int, ctypes.c_char_p)
            get_error(ctypes.c_int(status), buf)
            return buf.value.decode(errors="replace") or f"NVAPI status {status}"
        except Exception:
            return f"NVAPI status {status}"

    def _enum_display_handles(self) -> list[int]:
        enum = self._fn(
            self.ID_ENUM_NVIDIA_DISPLAY_HANDLE,
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        )
        handles: list[int] = []
        for index in range(16):
            handle = ctypes.c_void_p()
            status = enum(ctypes.c_uint32(index), ctypes.byref(handle))
            if status == self.NVAPI_OK and handle.value:
                handles.append(int(handle.value))
                continue
            if status == self.NVAPI_END_ENUMERATION:
                break
        return handles

    def _get_dvc_range_ex(self, handle: int) -> tuple[int, int, int, int]:
        class DVCInfoEx(ctypes.Structure):
            _fields_ = [
                ("version", ctypes.c_uint32),
                ("currentLevel", ctypes.c_int32),
                ("minLevel", ctypes.c_int32),
                ("maxLevel", ctypes.c_int32),
                ("defaultLevel", ctypes.c_int32),
            ]

        info = DVCInfoEx()
        info.version = self._make_version(ctypes.sizeof(DVCInfoEx), 1)
        fn = self._fn(
            self.ID_GET_DVC_INFO_EX,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(DVCInfoEx),
        )
        status = fn(ctypes.c_void_p(handle), ctypes.c_uint32(0), ctypes.byref(info))
        if status != self.NVAPI_OK:
            raise ColorBackendError(self.error_message(status))
        return int(info.currentLevel), int(info.minLevel), int(info.maxLevel), int(info.defaultLevel)

    def _set_dvc_ex(self, handle: int, level: int) -> None:
        class DVCInfoEx(ctypes.Structure):
            _fields_ = [
                ("version", ctypes.c_uint32),
                ("currentLevel", ctypes.c_int32),
                ("minLevel", ctypes.c_int32),
                ("maxLevel", ctypes.c_int32),
                ("defaultLevel", ctypes.c_int32),
            ]

        info = DVCInfoEx()
        info.version = self._make_version(ctypes.sizeof(DVCInfoEx), 1)
        info.currentLevel = int(level)
        fn = self._fn(
            self.ID_SET_DVC_LEVEL_EX,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(DVCInfoEx),
        )
        status = fn(ctypes.c_void_p(handle), ctypes.c_uint32(0), ctypes.byref(info))
        if status != self.NVAPI_OK:
            raise ColorBackendError(self.error_message(status))

    def _get_dvc_range_legacy(self, handle: int) -> tuple[int, int, int]:
        class DVCInfo(ctypes.Structure):
            _fields_ = [
                ("version", ctypes.c_uint32),
                ("currentLevel", ctypes.c_uint32),
                ("minLevel", ctypes.c_uint32),
                ("maxLevel", ctypes.c_uint32),
            ]

        info = DVCInfo()
        info.version = self._make_version(ctypes.sizeof(DVCInfo), 1)
        fn = self._fn(
            self.ID_GET_DVC_INFO,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(DVCInfo),
        )
        status = fn(ctypes.c_void_p(handle), ctypes.c_uint32(0), ctypes.byref(info))
        if status != self.NVAPI_OK:
            raise ColorBackendError(self.error_message(status))
        return int(info.currentLevel), int(info.minLevel), int(info.maxLevel)

    def _set_dvc_legacy(self, handle: int, level: int) -> None:
        fn = self._fn(
            self.ID_SET_DVC_LEVEL,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        )
        status = fn(ctypes.c_void_p(handle), ctypes.c_uint32(0), ctypes.c_uint32(level))
        if status != self.NVAPI_OK:
            raise ColorBackendError(self.error_message(status))

    @staticmethod
    def _map_percent_to_range(percent: int, min_level: int, max_level: int) -> int:
        percent = max(0, min(100, int(percent)))
        # Most NVIDIA desktop DVC ranges are already 0..100. This mapping also handles
        # signed or driver-specific ranges without assuming one fixed scale.
        return int(round(min_level + ((max_level - min_level) * (percent / 100.0))))

    def set_digital_vibrance(self, digital_vibrance: int) -> ApplyResult:
        digital_vibrance = max(0, min(100, int(digital_vibrance)))
        successes = 0
        failures: list[str] = []

        for handle in self.handles:
            try:
                _cur, min_level, max_level, _default = self._get_dvc_range_ex(handle)
                level = self._map_percent_to_range(digital_vibrance, min_level, max_level)
                self._set_dvc_ex(handle, level)
                successes += 1
                continue
            except Exception as exc_ex:
                try:
                    _cur, min_level, max_level = self._get_dvc_range_legacy(handle)
                    level = self._map_percent_to_range(digital_vibrance, min_level, max_level)
                    self._set_dvc_legacy(handle, level)
                    successes += 1
                    continue
                except Exception as exc_legacy:
                    failures.append(f"EX: {exc_ex}; legacy: {exc_legacy}")

        if successes:
            suffix = "" if not failures else f"; {len(failures)} display(s) failed"
            return ApplyResult(True, f"Applied Digital Vibrance={digital_vibrance} on {successes} NVIDIA display(s){suffix}")
        return ApplyResult(False, "Digital Vibrance failed: " + " | ".join(failures[:2]))


class HybridColorBackend:
    """Applies Windows gamma ramp plus NVIDIA DVC when NVAPI is available."""

    def __init__(self) -> None:
        self.gamma_backend = WindowsGammaRampBackend()
        self.dvc_backend: Optional[NvidiaDvcBackend] = None
        self.dvc_init_error: Optional[str] = None
        try:
            self.dvc_backend = NvidiaDvcBackend()
        except Exception as exc:
            self.dvc_init_error = str(exc)

    def apply(self, brightness: int, contrast: int, gamma: float, digital_vibrance: int = 50, red_channel: int = 100, green_channel: int = 100, blue_channel: int = 100) -> ApplyResult:
        gamma_result = self.gamma_backend.apply(brightness, contrast, gamma, digital_vibrance, red_channel, green_channel, blue_channel)
        messages = [gamma_result.message]
        ok = gamma_result.ok

        if self.dvc_backend is None:
            messages.append(f"Digital Vibrance not applied: NVAPI unavailable ({self.dvc_init_error})")
            return ApplyResult(ok, " | ".join(messages))

        dvc_result = self.dvc_backend.set_digital_vibrance(digital_vibrance)
        messages.append(dvc_result.message)
        return ApplyResult(ok and dvc_result.ok, " | ".join(messages))


# Backwards-compatible name for older imports.
NvApiBackend = NvidiaDvcBackend
