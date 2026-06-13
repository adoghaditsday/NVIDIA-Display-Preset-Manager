# NVIDIA Color Presets

A local Windows desktop color preset utility for NVIDIA-focused setups.

## Features

- Editable presets
- Brightness, contrast, and gamma controls through Windows gamma ramp
- Digital Vibrance through NVIDIA NVAPI DVC backend when available
- Red, green, and blue channel balance through per-channel gamma-ramp correction
- System tray menu: Open, Change Preset, Exit
- Hotkey preferences using Windows `RegisterHotKey`
- Custom icon support from `.ico`, `.png`, `.jpg`, `.jpeg`, `.webp`, or `.bmp`
- Automatic PNG/bitmap-to-ICO conversion for Windows scaling

## Run from source

```bat
run_app.bat
```

or:

```bat
python -m pip install -r requirements.txt
python app/main.py
```

## Custom icon

Open the app, then use either:

```text
Icon > Change Custom Icon...
```

or:

```text
Preferences > Change Custom Icon...
```

The app creates:

```text
%APPDATA%\NvidiaColorPreset\icons\custom_icon.png
%APPDATA%\NvidiaColorPreset\icons\custom_icon.ico
```

The custom icon updates the running app window and tray icon. To bake an icon into the EXE file itself, replace `assets\icon.ico` before running `build_exe.bat`.

## Build EXE

```bat
build_exe.bat
```

Output is created in:

```text
dist\NvidiaColorPreset.exe
```

## Anti-cheat design boundary

This utility does not inject DLLs, draw overlays, hook game render APIs, modify shaders, or attach to game processes. It only changes desktop/display color state through Windows display APIs and NVIDIA NVAPI where available.
