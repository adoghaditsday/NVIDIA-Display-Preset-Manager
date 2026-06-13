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

## The application was designed for users who frequently adjust display settings depending on what they are doing. A competitive gamer may prefer a high-vibrance profile that makes enemies easier to distinguish, while a video editor may require a more neutral color profile for accurate grading. Instead of manually adjusting settings each time, profiles can be saved and recalled instantly.

Features
Save and load unlimited display presets
Brightness control
Contrast control
Gamma adjustment
Digital Vibrance support through NVIDIA APIs
Individual Red, Green, and Blue channel tuning
System tray operation
Customizable hotkeys for instant profile switching
User-defined icons and themes
Lightweight desktop application
No overlays
No game hooks
No shader injection
No modification of game files
Designed For
Gamers

Different games often benefit from different visual settings. Competitive shooters may benefit from higher vibrance and contrast, while immersive single-player games may look better with softer color settings.

Examples:

Counter-Strike 2 competitive profile
Escape From Tarkov visibility profile
Racing simulator profile
HDR-inspired profile
Streaming profile
Content Creators

Editors frequently switch between color-sensitive work and general desktop usage.

Examples:

Photo editing profile
Video grading profile
SDR editing profile
Review and approval profile
General productivity profile
Streamers

Streamers often need separate settings for gameplay and content production.

Examples:

Streaming profile
Recording profile
Editing profile
Competitive gaming profile

This utility does not inject DLLs, draw overlays, hook game render APIs, modify shaders, or attach to game processes. It only changes desktop/display color state through Windows display APIs and NVIDIA NVAPI where available.
