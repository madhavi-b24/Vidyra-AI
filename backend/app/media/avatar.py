"""AI teacher avatar.

Default ("animated"): a clean, generated presenter portrait shown in the
corner with a subtle "speaking" pulse -- always works, no GPU, no downloads.

Optional ("sadtalker"/"wav2lip"): photorealistic / lip-synced talking head
generated from a portrait + the narration audio. These need a GPU and the
respective repo (see docs). We shell out and fall back gracefully.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from ..config import settings

_ASSETS = Path(__file__).resolve().parents[3] / "assets"


def ensure_portrait() -> Path:
    """Return a teacher portrait, generating a friendly one if none exists."""
    _ASSETS.mkdir(parents=True, exist_ok=True)
    custom = _ASSETS / "teacher.png"
    if custom.exists():
        return custom
    gen = _ASSETS / "teacher_generated.png"
    if not gen.exists():
        _draw_portrait(gen)
    return gen


def _draw_portrait(out: Path):
    S = 400
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # background circle
    d.ellipse([10, 10, S - 10, S - 10], fill=(30, 41, 59, 255),
              outline=(56, 189, 248, 255), width=6)
    # shoulders
    d.ellipse([70, 250, S - 70, S + 120], fill=(37, 99, 235, 255))
    # neck
    d.rectangle([175, 210, 225, 270], fill=(240, 200, 170, 255))
    # head
    d.ellipse([130, 90, 270, 240], fill=(244, 208, 178, 255))
    # hair
    d.chord([128, 78, 272, 210], 180, 360, fill=(60, 40, 30, 255))
    d.rectangle([128, 130, 145, 175], fill=(60, 40, 30, 255))
    d.rectangle([255, 130, 272, 175], fill=(60, 40, 30, 255))
    # eyes
    d.ellipse([168, 150, 184, 166], fill=(40, 40, 40, 255))
    d.ellipse([216, 150, 232, 166], fill=(40, 40, 40, 255))
    # smile
    d.arc([175, 165, 225, 205], 20, 160, fill=(120, 70, 60, 255), width=5)
    # glasses (teacher vibe)
    d.ellipse([160, 145, 192, 172], outline=(15, 23, 42, 255), width=4)
    d.ellipse([208, 145, 240, 172], outline=(15, 23, 42, 255), width=4)
    d.line([192, 158, 208, 158], fill=(15, 23, 42, 255), width=4)
    img.save(out)


def generate_talking_clip(audio_path: str | Path, out_path: str | Path) -> Path | None:
    """Return a talking-head mp4 if an external engine is configured, else None."""
    mode = settings.avatar_mode.lower()
    if mode == "sadtalker" and settings.sadtalker_dir:
        return _sadtalker(audio_path, out_path)
    # wav2lip and others could be added here similarly.
    return None


def _sadtalker(audio_path, out_path) -> Path | None:
    portrait = ensure_portrait()
    out_path = Path(out_path)
    try:
        subprocess.run(
            [
                "python", "inference.py",
                "--driven_audio", str(audio_path),
                "--source_image", str(portrait),
                "--result_dir", str(out_path.parent),
                "--still", "--preprocess", "full",
            ],
            cwd=settings.sadtalker_dir,
            check=True,
            timeout=1200,
        )
        # SadTalker writes an mp4 into result_dir; pick the newest.
        mp4s = sorted(
            Path(out_path.parent).glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
        )
        return mp4s[-1] if mp4s else None
    except Exception:
        return None