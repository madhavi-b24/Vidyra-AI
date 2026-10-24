"""Complex-script text rendering (Devanagari, Tamil, Telugu, ... + Latin).

PIL alone cannot shape Indic scripts (conjuncts/matras) without libraqm, so we
shape with HarfBuzz and rasterize glyphs with FreeType. Falls back to plain PIL
text if those libraries are unavailable.

Nirmala UI (Windows) covers Latin + most Indian scripts, giving true
multilingual on-screen text for the teaching videos.
"""
from __future__ import annotations

import functools
import os
from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\Nirmala.ttc",   # Latin + Devanagari/Tamil/Telugu/... 
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

try:
    import uharfbuzz as hb
    import freetype

    _HAS_HB = True
except Exception:  # pragma: no cover
    _HAS_HB = False


@functools.lru_cache(maxsize=1)
def font_path() -> str | None:
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    try:
        import matplotlib

        return os.path.join(
            os.path.dirname(matplotlib.__file__),
            "mpl-data", "fonts", "ttf", "DejaVuSans.ttf",
        )
    except Exception:
        return None


# --------------------------- HarfBuzz path --------------------------------
@functools.lru_cache(maxsize=4)
def _hb_font(path: str):
    with open(path, "rb") as f:
        data = f.read()
    face = hb.Face(data)
    hbfont = hb.Font(face)
    ft = freetype.Face(path)
    return hbfont, face.upem, ft


def _shape(text: str):
    path = font_path()
    hbfont, upem, ft = _hb_font(path)
    hbfont.scale = (upem, upem)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf)
    return buf.glyph_infos, buf.glyph_positions, upem, ft


# ------------------------------ PIL fallback ------------------------------
@functools.lru_cache(maxsize=16)
def _pil_font(size: int) -> ImageFont.FreeTypeFont:
    p = font_path()
    if p and p.lower().endswith((".ttf", ".ttc")):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ------------------------------- public API -------------------------------
def measure(text: str, size: int) -> float:
    if not text:
        return 0.0
    if _HAS_HB and font_path():
        try:
            _, positions, upem, _ = _shape(text)
            scale = size / upem
            return sum(p.x_advance for p in positions) * scale
        except Exception:
            pass
    return _pil_font(size).getlength(text)


def draw(img: Image.Image, xy, text: str, size: int, fill, bold: bool = False) -> float:
    """Draw shaped text with a top-left anchor. Returns pixel width."""
    text = text or ""
    x, y = xy
    if not text:
        return 0.0
    if isinstance(fill, str):
        fill = (241, 245, 249)
    if not (_HAS_HB and font_path()):
        d = ImageDraw.Draw(img)
        d.text((x, y), text, font=_pil_font(size), fill=fill)
        if bold:
            d.text((x + 1, y), text, font=_pil_font(size), fill=fill)
        return _pil_font(size).getlength(text)

    try:
        infos, positions, upem, ft = _shape(text)
    except Exception:
        d = ImageDraw.Draw(img)
        d.text((x, y), text, font=_pil_font(size), fill=fill)
        return _pil_font(size).getlength(text)

    ft.set_char_size(int(size * 64))
    asc = ft.size.ascender / 64.0
    scale = size / upem
    penx = float(x)
    offsets = [(0, 0)] + ([(1, 0)] if bold else [])
    for dx, _dy in offsets:
        penx = float(x)
        for info, pos in zip(infos, positions):
            ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
            bmp = ft.glyph.bitmap
            w, h = bmp.width, bmp.rows
            if w and h:
                glyph = Image.frombytes("L", (w, h), bytes(bmp.buffer))
                gx = int(penx + pos.x_offset * scale + ft.glyph.bitmap_left) + dx
                gy = int(y + asc - ft.glyph.bitmap_top - pos.y_offset * scale)
                solid = Image.new("RGBA", (w, h), tuple(fill) + (0,))
                solid.putalpha(glyph)
                img.paste(solid, (gx, gy), solid)
            penx += pos.x_advance * scale
    return penx - x


def wrap(text: str, size: int, max_width: float) -> list[str]:
    """Word-wrap using true shaped width."""
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if measure(trial, size) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines