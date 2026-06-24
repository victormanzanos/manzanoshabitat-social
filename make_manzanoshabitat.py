#!/usr/bin/env python3
"""
Manzanos Hábitat — image processor for Instagram (@manzanoshabitat).

Toma renders de proyectos / fotos del blog y les aplica:
- crop/resize a 1080x1350 (post) o 1080x1920 (story)
- viñeta sutil en bordes
- marco DOBLE dorado (línea exterior + interior con gap)
- acentos en L en las 4 esquinas (art-déco)
- LOGO Manzanos Hábitat (dorado/blanco) compuesto abajo sobre panel translúcido

Uso:
    python3 make_manzanoshabitat.py post  villafranca/hero.jpg   01-villafranca.jpg
    python3 make_manzanoshabitat.py story villafranca/hero.jpg   01-villafranca-story.jpg
    python3 make_manzanoshabitat.py batch
"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFilter

LOCAL       = os.path.expanduser("~/manzanoshabitat-social")
RAW         = os.path.join(LOCAL, "raw")           # renders fuente (copiados de la web)
ASSETS      = os.path.join(LOCAL, "assets")
OUT_POSTS   = os.path.join(LOCAL, "posts")
OUT_STORIES = os.path.join(LOCAL, "stories")

# Paleta Manzanos Hábitat (del sitio: oro #c9a96e, oscuro #1a1a2e)
GOLD     = (201, 169, 110)   # #c9a96e
GOLD_LT  = (224, 200, 156)
INK      = (26, 26, 46)      # #1a1a2e

POST_W,  POST_H  = 1080, 1350
STORY_W, STORY_H = 1080, 1920

LOGO_WHITE = os.path.join(ASSETS, "logo-mh-white.png")
LOGO_GOLD  = os.path.join(ASSETS, "logo-mh-gold.png")


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    nw, nh = int(im.width * s + 1), int(im.height * s + 1)
    im = im.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def add_vignette(im, strength=0.20):
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    px = mask.load()
    cx, cy = w / 2, h / 2
    max_d = math.hypot(cx, cy)
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / max_d
            v = max(0.0, d - 0.55) / 0.45
            px[x, y] = int(255 * v * strength)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, im, mask)


def draw_double_frame(im, margin_outer, gap, line_outer, line_inner):
    w, h = im.size
    canvas = im.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([margin_outer, margin_outer, w - margin_outer - 1, h - margin_outer - 1],
                outline=GOLD, width=line_outer)
    mi = margin_outer + gap
    d.rectangle([mi, mi, w - mi - 1, h - mi - 1], outline=GOLD, width=line_inner)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def draw_corner_accents(im, margin, size, line):
    w, h = im.size
    canvas = im.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.line([(margin, margin + size), (margin, margin)], fill=GOLD, width=line)
    d.line([(margin, margin), (margin + size, margin)], fill=GOLD, width=line)
    d.line([(w - margin - size, margin), (w - margin - 1, margin)], fill=GOLD, width=line)
    d.line([(w - margin - 1, margin), (w - margin - 1, margin + size)], fill=GOLD, width=line)
    d.line([(margin, h - margin - size), (margin, h - margin - 1)], fill=GOLD, width=line)
    d.line([(margin, h - margin - 1), (margin + size, h - margin - 1)], fill=GOLD, width=line)
    d.line([(w - margin - size, h - margin - 1), (w - margin - 1, h - margin - 1)], fill=GOLD, width=line)
    d.line([(w - margin - 1, h - margin - size), (w - margin - 1, h - margin - 1)], fill=GOLD, width=line)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def add_logo_bottom(im, story=False):
    """Compone el logo MH (blanco) abajo, centrado, sobre panel translúcido oscuro
    con una fina línea dorada encima. El logo es el cierre de marca que pidió Victor."""
    w, h = im.size
    canvas = im.convert("RGBA")

    # Panel translúcido (degradado oscuro hacia abajo para legibilidad)
    panel_h = 230 if story else 190
    panel_y = h - panel_h - (54 if story else 44)   # por encima del marco inferior
    panel = Image.new("RGBA", (w, panel_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    for i in range(panel_h):
        a = int(150 * (i / panel_h) ** 1.4)         # más opaco abajo
        pd.line([(0, i), (w, i)], fill=(INK[0], INK[1], INK[2], a))
    canvas.alpha_composite(panel, (0, panel_y))

    # Línea dorada fina sobre el panel
    d = ImageDraw.Draw(canvas)
    d.line([(w * 0.34, panel_y), (w * 0.66, panel_y)], fill=GOLD, width=2)

    # Logo blanco centrado dentro del panel
    logo = Image.open(LOGO_WHITE).convert("RGBA")
    target_w = int(w * (0.56 if story else 0.50))
    target_h = int(target_w * logo.height / logo.width)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)
    lx = (w - target_w) // 2
    ly = panel_y + (panel_h - target_h) // 2 + (6 if story else 4)
    canvas.alpha_composite(logo, (lx, ly))

    return canvas.convert("RGB")


def make_post(src_rel, out_filename, story=False):
    src_path = os.path.join(RAW, src_rel)
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"No existe: {src_path}")
    w, h = (STORY_W, STORY_H) if story else (POST_W, POST_H)
    out_dir = OUT_STORIES if story else OUT_POSTS
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_filename)

    img = Image.open(src_path).convert("RGB")
    img = cover(img, w, h)
    img = add_vignette(img, strength=0.20)
    if story:
        img = draw_double_frame(img, 54, 20, 4, 1)
        img = draw_corner_accents(img, 54, 90, 4)
    else:
        img = draw_double_frame(img, 44, 16, 3, 1)
        img = draw_corner_accents(img, 44, 70, 3)
    img = add_logo_bottom(img, story=story)
    img.save(out_path, "JPEG", quality=92, optimize=True)
    print(f"  ✓ {('STORY' if story else 'POST '):<5} {src_rel:<42} → {out_filename}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] in ("post", "story"):
        make_post(sys.argv[2], sys.argv[3], story=(sys.argv[1] == "story"))
    else:
        print("Uso: make_manzanoshabitat.py post|story <src_rel> <out.jpg>")
