"""Subject-aware visual generation.

Renders a VisualSpec into a 1280x720 PNG frame. The teacher chooses the
visual type per concept: Math -> graphs/equations, Programming -> code,
History -> timelines, Biology -> diagrams, etc. (Assessment criterion #10.)

All text is shaped with HarfBuzz (see text_render) so Hindi / Tamil / Telugu
on-screen text renders correctly in the video.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import text_render as tr

W, H = 1280, 720
BG = (15, 23, 42)          # slate-900
PANEL = (30, 41, 59)       # slate-800
ACCENT = (56, 189, 248)    # sky-400
ACCENT2 = (250, 204, 21)   # amber-300
TEXT = (241, 245, 249)
MUTED = (148, 163, 184)


def _new_canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=ACCENT)
    d.rectangle([0, H - 6, W, H], fill=PANEL)
    return img, d


def _title(img, d, title: str):
    tr.draw(img, (60, 40), (title or "")[:80], 46, TEXT, bold=True)
    d.line([60, 112, W - 60, 112], fill=ACCENT, width=3)


def render(visual, out_path: str | Path) -> Path:
    from ..schemas import VisualSpec

    if not isinstance(visual, VisualSpec):
        visual = VisualSpec(**visual)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t = visual.type
    try:
        if t == "graph":
            _render_graph(visual, out_path)
        elif t == "code":
            _render_code(visual, out_path)
        elif t == "equation":
            _render_equation(visual, out_path)
        elif t == "timeline":
            _render_timeline(visual, out_path)
        elif t == "table":
            _render_table(visual, out_path)
        elif t in ("diagram", "map"):
            _render_diagram(visual, out_path)
        else:
            _render_slide(visual, out_path)
    except Exception:
        _render_slide(visual, out_path)
    return out_path


def _render_slide(v, out: Path):
    img, d = _new_canvas()
    _title(img, d, v.title or "")
    y = 155
    bullets = v.bullets or v.items or ([v.note] if v.note else [])
    for b in bullets[:6]:
        d.ellipse([64, y + 14, 82, y + 32], fill=ACCENT2)
        for line in tr.wrap(str(b), 34, W - 220):
            tr.draw(img, (100, y), line, 34, TEXT)
            y += 48
        y += 12
    if v.note and bullets and v.note not in bullets:
        tr.draw(img, (64, H - 70), v.note[:110], 24, MUTED)
    img.save(out)


def _render_equation(v, out: Path):
    img, d = _new_canvas()
    _title(img, d, v.title or "Key Formula")
    eq = v.equation or (v.bullets[0] if v.bullets else "")
    d.rounded_rectangle([120, 300, W - 120, 440], radius=18, fill=PANEL,
                        outline=ACCENT, width=3)
    tw = tr.measure(eq, 52)
    tr.draw(img, ((W - tw) / 2, 338), eq, 52, ACCENT2, bold=True)
    y = 470
    for b in (v.bullets or [])[1:5]:
        tr.draw(img, (120, y), f"- {b}", 28, TEXT)
        y += 42
    img.save(out)


def _render_timeline(v, out: Path):
    img, d = _new_canvas()
    _title(img, d, v.title or "Timeline")
    items = v.items or v.bullets
    n = max(1, len(items[:6]))
    d.line([80, 380, W - 80, 380], fill=ACCENT, width=5)
    step = (W - 160) / n
    for i, it in enumerate(items[:6]):
        cx = int(80 + step * i + step / 2)
        d.ellipse([cx - 12, 368, cx + 12, 392], fill=ACCENT2)
        up = i % 2 == 0
        ty = 250 if up else 420
        for j, line in enumerate(tr.wrap(str(it), 22, step - 10)[:3]):
            tr.draw(img, (cx - 90, ty + j * 28), line, 22, TEXT)
    img.save(out)


def _render_table(v, out: Path):
    img, d = _new_canvas()
    _title(img, d, v.title or "Comparison")
    rows = v.rows or [[b] for b in (v.bullets or [])]
    if not rows:
        return _render_slide(v, out)
    cols = max(len(r) for r in rows)
    x0, y0 = 80, 160
    cw = (W - 160) / max(1, cols)
    rh = min(70, (H - 220) / max(1, len(rows)))
    for ri, row in enumerate(rows[:8]):
        for ci in range(cols):
            x = x0 + ci * cw
            y = y0 + ri * rh
            d.rectangle([x, y, x + cw, y + rh],
                        fill=PANEL if ri == 0 else BG, outline=MUTED)
            cell = str(row[ci]) if ci < len(row) else ""
            tr.draw(img, (x + 12, y + rh / 2 - 16), cell[:22], 26, TEXT,
                    bold=(ri == 0))
    img.save(out)


def _render_diagram(v, out: Path):
    img, d = _new_canvas()
    _title(img, d, v.title or "Process")
    steps = v.items or v.bullets
    n = min(4, max(1, len(steps)))
    bw, bh = 250, 120
    gap = (W - 120 - bw * n) / max(1, n - 1) if n > 1 else 0
    y = 320
    for i, s in enumerate(steps[:4]):
        x = 60 + i * (bw + gap)
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=16, fill=PANEL,
                            outline=ACCENT, width=3)
        for j, line in enumerate(tr.wrap(str(s), 24, bw - 30)[:3]):
            tr.draw(img, (x + 16, y + 22 + j * 30), line, 24, TEXT)
        if i < n - 1:
            d.line([x + bw, y + bh / 2, x + bw + gap, y + bh / 2],
                   fill=ACCENT2, width=4)
            d.polygon([(x + bw + gap, y + bh / 2 - 10),
                       (x + bw + gap, y + bh / 2 + 10),
                       (x + bw + gap + 16, y + bh / 2)], fill=ACCENT2)
    img.save(out)


def _render_graph(v, out: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor("#0f172a")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f172a")
    x, y = v.x, v.y
    if not x or not y or len(x) != len(y):
        import numpy as np

        x = list(np.linspace(-10, 10, 50))
        y = [xi * xi for xi in x]
    ax.plot(x, y, color="#38bdf8", linewidth=3, label=v.curve_label or None)
    ax.set_title(v.title or "Graph", color="#f1f5f9", fontsize=22, pad=16)
    ax.set_xlabel(v.x_label, color="#cbd5e1", fontsize=14)
    ax.set_ylabel(v.y_label, color="#cbd5e1", fontsize=14)
    ax.tick_params(colors="#94a3b8")
    for s in ax.spines.values():
        s.set_color("#334155")
    ax.grid(True, color="#1e293b")
    if v.curve_label:
        ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f1f5f9")
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)


def _render_code(v, out: Path):
    code = v.code or "# no code"
    try:
        from pygments import highlight
        from pygments.formatters import ImageFormatter
        from pygments.lexers import get_lexer_by_name

        lexer = get_lexer_by_name(v.code_lang or "python", stripall=True)
        fmt = ImageFormatter(font_size=26, line_numbers=True, style="monokai",
                             image_pad=24, line_pad=6)
        png = highlight(code, lexer, fmt)
        tmp = out.with_name(out.stem + "_raw.png")
        tmp.write_bytes(png)
        src = Image.open(tmp).convert("RGB")
        canvas = Image.new("RGB", (W, H), (39, 40, 34))
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, W, 8], fill=ACCENT)
        tr.draw(canvas, (30, 24), v.title or "Code", 30, TEXT, bold=True)
        src.thumbnail((W - 60, H - 120))
        canvas.paste(src, (30, 90))
        canvas.save(out)
        try:
            tmp.unlink()
        except Exception:
            pass
    except Exception:
        _render_slide(v, out)