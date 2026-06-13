from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

try:
    from app.presets import app_data_dir, resource_path
except ImportError:
    from presets import app_data_dir, resource_path

SUPPORTED_ICON_EXTENSIONS = {".ico", ".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def icon_store_dir() -> Path:
    path = app_data_dir() / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_icon_png() -> Path:
    return resource_path("assets/icon.png")


def default_icon_ico() -> Path:
    return resource_path("assets/icon.ico")


def custom_icon_png() -> Path:
    return icon_store_dir() / "custom_icon.png"


def custom_icon_ico() -> Path:
    return icon_store_dir() / "custom_icon.ico"


def active_icon_png(settings: dict | None = None) -> Path:
    if settings and settings.get("custom_icon_enabled", False) and custom_icon_png().exists():
        return custom_icon_png()
    p = default_icon_png()
    return p if p.exists() else custom_icon_png()


def active_icon_ico(settings: dict | None = None) -> Path:
    if settings and settings.get("custom_icon_enabled", False) and custom_icon_ico().exists():
        return custom_icon_ico()
    p = default_icon_ico()
    return p if p.exists() else custom_icon_ico()


def _load_square_image(source: Path) -> Image.Image:
    img = Image.open(source).convert("RGBA")
    # Use contained fit so user images don't get aggressively cropped.
    img = ImageOps.contain(img, (1024, 1024), Image.LANCZOS)
    size = max(img.width, img.height, 256)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def install_custom_icon(source_file: str | Path) -> tuple[Path, Path]:
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(f"Icon file not found: {source}")
    if source.suffix.lower() not in SUPPORTED_ICON_EXTENSIONS:
        raise ValueError("Unsupported icon format. Use .ico, .png, .jpg, .jpeg, .webp, or .bmp.")

    store = icon_store_dir()
    png_out = store / "custom_icon.png"
    ico_out = store / "custom_icon.ico"

    img = _load_square_image(source)
    png_img = img.resize((256, 256), Image.LANCZOS)
    png_img.save(png_out, format="PNG")
    img.save(ico_out, format="ICO", sizes=ICO_SIZES)
    return png_out, ico_out


def clear_custom_icon() -> None:
    for p in (custom_icon_png(), custom_icon_ico()):
        if p.exists():
            p.unlink()
