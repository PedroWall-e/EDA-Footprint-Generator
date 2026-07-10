"""Gera ícone da aplicação (.ico) via Pillow/QPainter.

Uso:
    python assets/icon_generator.py

Gera assets/app_icon.ico com múltiplas resoluções (16, 32, 48, 64, 128, 256).
Se Pillow não estiver disponível, gera um .ico básico com fallback puro em bytes.
"""
import os
import sys
import math
import struct

# Diretório de saída (mesmo diretório deste script)
_DIR = os.path.dirname(os.path.abspath(__file__))
_OUTPUT = os.path.join(_DIR, 'app_icon.ico')

# Cores da marca (Catppuccin Mocha)
_BG = (26, 26, 46)          # #1A1A2E — fundo escuro
_ACCENT = (137, 180, 250)   # #89B4FA — azul
_GREEN = (166, 227, 161)    # #A6E3A1 — verde acento
_TEXT = (24, 24, 37)         # #181825 — texto dentro do hexágono


def _hex_points(cx, cy, r):
    """Calcula os 6 vértices de um hexágono regular centrado em (cx, cy)."""
    pts = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


# =============================================================================
# Método 1: Geração via Pillow (alta qualidade, múltiplas resoluções)
# =============================================================================

def generate_icon_pillow():
    """Gera app_icon.ico usando Pillow com hexágono CAD e texto 'CAD'."""
    from PIL import Image, ImageDraw, ImageFont

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for sz in sizes:
        img = Image.new('RGBA', (sz, sz), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        cx, cy = sz / 2, sz / 2
        r = sz * 0.40  # raio do hexágono proporcional

        # --- Hexágono com gradiente simulado ---
        hex_pts = _hex_points(cx, cy, r)

        # Contorno preenchido (gradiente linear simulado com cor mista)
        fill_color = (
            (_ACCENT[0] + _GREEN[0]) // 2,
            (_ACCENT[1] + _GREEN[1]) // 2,
            (_ACCENT[2] + _GREEN[2]) // 2,
        )
        draw.polygon(hex_pts, fill=(*fill_color, 255),
                     outline=(*_ACCENT, 200))

        # --- Texto "CAD" dentro do hexágono ---
        if sz >= 32:
            font_size = max(8, int(sz * 0.28))
            try:
                font = ImageFont.truetype('consola.ttf', font_size)
            except (IOError, OSError):
                try:
                    font = ImageFont.truetype('cour.ttf', font_size)
                except (IOError, OSError):
                    font = ImageFont.load_default()

            text = 'EDA'
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = cx - tw / 2
            ty = cy - th / 2 - bbox[1]  # compensar offset do bbox
            draw.text((tx, ty), text, fill=(*_TEXT, 255), font=font)

        # --- Linha decorativa no topo (gradiente accent) ---
        if sz >= 48:
            line_y = int(sz * 0.08)
            x_start = int(sz * 0.15)
            x_end = int(sz * 0.85)
            draw.line([(x_start, line_y), (x_end, line_y)],
                      fill=(*_ACCENT, 180), width=max(1, sz // 64))

        images.append(img)

    # Salvar como .ico com múltiplas resoluções
    images[0].save(
        _OUTPUT,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f'✅  Ícone gerado (Pillow): {_OUTPUT}')
    print(f'    Resoluções: {sizes}')
    return _OUTPUT


# =============================================================================
# Método 2: Fallback puro em bytes (sem Pillow)
# =============================================================================

def _create_bmp_data(size, bg, accent):
    """Cria dados BMP (BGRA) para um ícone simples com fundo e borda."""
    pixels = bytearray()
    cx, cy = size / 2, size / 2
    r = size * 0.38

    hex_pts = _hex_points(cx, cy, r)

    def _point_in_hex(x, y):
        """Ray-casting para verificar se ponto está dentro do hexágono."""
        n = len(hex_pts)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = hex_pts[i]
            xj, yj = hex_pts[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    # BMP é bottom-up
    for row in range(size - 1, -1, -1):
        for col in range(size):
            if _point_in_hex(col + 0.5, row + 0.5):
                # Dentro do hexágono — cor accent
                pixels.extend([accent[2], accent[1], accent[0], 255])  # BGRA
            else:
                # Fundo
                pixels.extend([bg[2], bg[1], bg[0], 255])  # BGRA

    return bytes(pixels)


def generate_icon_fallback():
    """Gera app_icon.ico básico usando bytes puros (16x16 e 32x32)."""
    entries = []
    icon_data_list = []
    offset = 6 + 16 * 2  # ICO header (6) + 2 entries (16 each)

    for size in [16, 32]:
        bmp_data = _create_bmp_data(size, _BG, _ACCENT)

        # BMP info header (BITMAPINFOHEADER) — 40 bytes
        bih = struct.pack('<IiiHHIIiiII',
                          40,           # biSize
                          size,         # biWidth
                          size * 2,     # biHeight (doubled for ICO: image + mask)
                          1,            # biPlanes
                          32,           # biBitCount (BGRA)
                          0,            # biCompression (BI_RGB)
                          len(bmp_data),  # biSizeImage
                          0, 0,         # biXPelsPerMeter, biYPelsPerMeter
                          0, 0)         # biClrUsed, biClrImportant

        # AND mask (all zeros = fully opaque)
        mask_row_size = ((size + 31) // 32) * 4
        mask_data = b'\x00' * (mask_row_size * size)

        icon_chunk = bih + bmp_data + mask_data

        # ICO directory entry
        entry = struct.pack('<BBBBHHII',
                            size if size < 256 else 0,  # bWidth
                            size if size < 256 else 0,  # bHeight
                            0,    # bColorCount
                            0,    # bReserved
                            1,    # wPlanes
                            32,   # wBitCount
                            len(icon_chunk),  # dwBytesInRes
                            offset)           # dwImageOffset

        entries.append(entry)
        icon_data_list.append(icon_chunk)
        offset += len(icon_chunk)

    # ICO header
    ico_header = struct.pack('<HHH', 0, 1, len(entries))

    with open(_OUTPUT, 'wb') as f:
        f.write(ico_header)
        for entry in entries:
            f.write(entry)
        for data in icon_data_list:
            f.write(data)

    print(f'✅  Ícone gerado (fallback): {_OUTPUT}')
    print(f'    Resoluções: [16, 32]')
    return _OUTPUT


# =============================================================================
# Entry point
# =============================================================================

def generate_icon():
    """Gera o ícone usando Pillow se disponível, senão usa fallback."""
    try:
        return generate_icon_pillow()
    except ImportError:
        print('⚠️  Pillow não encontrado, usando fallback puro...')
        return generate_icon_fallback()


if __name__ == '__main__':
    generate_icon()
