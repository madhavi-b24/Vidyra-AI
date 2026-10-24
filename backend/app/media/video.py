"""Compose the final AI teaching video with moviepy (FREE).

Per segment we stack:
  - a subject-aware visual background (slides, graphs, code, diagrams...)
  - burned-in on-screen text (Unicode-safe, incl. Hindi)
  - the AI teacher avatar in the corner (animated pulse or SadTalker clip)
  - synchronized natural voice narration (free TTS)

No ImageMagick required -- all text is rendered with PIL.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from ..config import settings
from ..schemas import LearnerProfile, SegmentContent, VisualSpec
from . import avatar, text_render as tr, tts, visuals

W, H = visuals.W, visuals.H


def _caption_png(bullets: list[str], out: Path) -> Path | None:
    if not bullets:
        return None
    img = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 10, W - 300, 160], radius=16, fill=(2, 6, 23, 205),
                        outline=visuals.ACCENT, width=2)
    y = 26
    for b in bullets[:3]:
        d.ellipse([60, y + 10, 74, y + 24], fill=visuals.ACCENT2)
        tr.draw(img, (90, y), str(b)[:64], 26, visuals.TEXT)
        y += 44
    img.save(out)
    return out


def _title_card(topic: str, subject: str, language: str, out: Path) -> Path:
    v = VisualSpec(
        type="slide",
        title=topic,
        bullets=[f"Subject: {subject}", f"Language: {language}",
                 "Your AI Teacher: Aria"],
        note="An adaptive, personalized lesson",
    )
    return visuals.render(v, out)


def build_lesson_video(
    contents: list[SegmentContent],
    profile: LearnerProfile,
    plan_topic: str,
    subject: str,
    out_path: str | Path,
    progress_cb=None,
) -> Path:
    from moviepy.editor import (
        AudioFileClip,
        ImageClip,
        VideoFileClip,
        concatenate_videoclips,
    )

    out_path = Path(out_path)
    work = out_path.parent
    work.mkdir(parents=True, exist_ok=True)
    portrait = avatar.ensure_portrait()
    clips = []

    # --- intro title card (silent, 2.5s) ---
    tcard = _title_card(plan_topic, subject, profile.language, work / "title.png")
    clips.append(ImageClip(str(tcard)).set_duration(2.5))

    total = len(contents)
    for i, c in enumerate(contents):
        if progress_cb:
            progress_cb(i, total, c.title)
        stem = work / f"seg_{i:02d}"

        # 1) voice
        audio_path = tts.synthesize(
            c.narration, profile.language, stem, settings.tts_provider
        )
        try:
            audio = AudioFileClip(str(audio_path))
            dur = max(2.0, audio.duration + 0.3)
        except Exception:
            audio = None
            dur = max(3.0, len(c.narration.split()) / 2.5)

        # 2) visual background
        vpng = visuals.render(c.visual, stem.with_suffix(".png"))
        bg = ImageClip(str(vpng)).set_duration(dur)
        layers = [bg]

        # 3) on-screen caption
        cap = _caption_png(c.on_screen, stem.with_name(stem.name + "_cap.png"))
        if cap:
            layers.append(
                ImageClip(str(cap)).set_duration(dur).set_position((0, H - 190))
            )

        # 4) avatar (talking clip if available, else animated pulse)
        # 4) Lightweight animated avatar
        # Skip expensive talking-head generation during normal rendering.
        base = ImageClip(str(portrait), transparent=True).set_duration(dur)
        base = base.resize(height=220)

        av = base.resize(
            lambda t: 1 + 0.01 * math.sin(2 * math.pi * 1.2 * t)
        )

        av = av.set_position((W - 250, H - 250))
        layers.append(av)

        from moviepy.editor import CompositeVideoClip

        seg = CompositeVideoClip(layers, size=(W, H)).set_duration(dur)
        if audio is not None:
            seg = seg.set_audio(audio)
        clips.append(seg)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
    str(out_path),
    fps=15,
    codec="libx264",
    audio_codec="aac",
    preset="ultrafast",
    threads=4,
    logger=None,
     )
    final.close()
    return out_path