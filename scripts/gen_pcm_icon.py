#!/usr/bin/env python3
# =============================================================================
# scripts/gen_pcm_icon.py
# Gera o ícone 64x64 PNG exigido pelo KiCad PCM (kicad_plugin/icon.png),
# reutilizando a identidade visual do app (hexágono CAD, tema Catppuccin).
#
# Uso:  python scripts/gen_pcm_icon.py
# Requer: Pillow
# =============================================================================

import math
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, 'kicad_plugin', 'icon.png')

# Cores da marca (Catppuccin Mocha) — iguais a assets/icon_generator.py
_BG = (26, 26, 46)          # #1A1A2E
_ACCENT = (137, 180, 250)   # #89B4FA
_GREEN = (166, 227, 161)    # #A6E3A1
_TEXT = (24, 24, 37)        # #181825

SIZE = 64  # PCM exige 64x64


def _hex_points(cx, cy, r):
    return [
        (cx + r * math.cos(math.radians(60 * i - 30)),
         cy + r * math.sin(math.radians(60 * i - 30)))
        for i in range(6)
    ]


def main():
    from PIL import Image, ImageDraw, ImageFont

    # Renderiza em 4x e reduz (supersampling) para bordas suaves
    scale = 4
    sz = SIZE * scale
    img = Image.new('RGBA', (sz, sz), (*_BG, 255))
    draw = ImageDraw.Draw(img)

    cx, cy = sz / 2, sz / 2
    r = sz * 0.40
    hex_pts = _hex_points(cx, cy, r)

    fill_color = tuple((a + g) // 2 for a, g in zip(_ACCENT, _GREEN))
    draw.polygon(hex_pts, fill=(*fill_color, 255), outline=(*_ACCENT, 220))

    # Texto "CAD"
    font_size = int(sz * 0.28)
    font = None
    for name in ('consola.ttf', 'cour.ttf', 'DejaVuSansMono.ttf', 'arial.ttf'):
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    text = 'EDA'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - bbox[1]), text,
              fill=(*_TEXT, 255), font=font)

    # Linha decorativa no topo
    line_y = int(sz * 0.08)
    draw.line([(int(sz * 0.15), line_y), (int(sz * 0.85), line_y)],
              fill=(*_ACCENT, 200), width=max(1, sz // 64))

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, format='PNG')
    print(f'OK: {OUT}  ({SIZE}x{SIZE} PNG)')


if __name__ == '__main__':
    main()
