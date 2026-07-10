"""
Exportar footprint para formato Altium (CSV importável).

Como o formato .PcbLib do Altium é binário, esta exportação gera um
CSV importável que pode ser usado com ferramentas de importação do
Altium Designer ou conversores de terceiros.

Colunas CSV:
  Type, Name, X, Y, Width, Height, Layer, Shape, HoleSize

Tipos suportados:
  - PAD_SMD:   Pad SMD (sem furo)
  - PAD_PTH:   Pad through-hole (com furo)
  - LINE:      Linha (silkscreen, fab, courtyard)
  - CIRCLE:    Círculo
  - TEXT:      Texto (referência, valor)
"""

import csv
import os
import re
import logging

log = logging.getLogger(__name__)


# =============================================================================
# Layer mapping: KiCad → Altium layer names
# =============================================================================

_KICAD_TO_ALTIUM_LAYER = {
    'F.SilkS':    'TopOverlay',
    'B.SilkS':    'BottomOverlay',
    'F.Fab':      'Mechanical1',
    'B.Fab':      'Mechanical2',
    'F.CrtYd':    'Mechanical15',
    'B.CrtYd':    'Mechanical16',
    'F.Cu':       'TopLayer',
    'B.Cu':       'BottomLayer',
    'F.Mask':     'TopSolder',
    'B.Mask':     'BottomSolder',
    'F.Paste':    'TopPaste',
    'B.Paste':    'BottomPaste',
    'Edge.Cuts':  'Mechanical20',
}

_PAD_SHAPE_ALTIUM = {
    'rect':       'Rectangle',
    'roundrect':  'RoundedRectangle',
    'circle':     'Round',
    'oval':       'Round',
    'custom':     'Rectangle',
}


# =============================================================================
# S-Expression parser (shared module)
# =============================================================================

try:
    from core.sexpr_parser import parse_sexpr, find_all, find_one, get_at, get_size
except ImportError:
    from sexpr_parser import parse_sexpr, find_all, find_one, get_at, get_size

# Aliases internos para compatibilidade
_parse_sexpr = parse_sexpr
_find_all = find_all
_find_one = find_one
_get_at = get_at
_get_size = get_size


# =============================================================================
# CSV row builders
# =============================================================================

def _pad_to_row(pad_sexpr):
    """Convert a KiCad pad to a CSV row dict."""
    name = pad_sexpr[1] if len(pad_sexpr) > 1 else ''
    x, y, _ = _get_at(pad_sexpr)
    w, h = _get_size(pad_sexpr)

    # Determine pad type
    pad_type = 'PAD_SMD'
    for item in pad_sexpr:
        if isinstance(item, str) and item == 'thru_hole':
            pad_type = 'PAD_PTH'
            break

    # Shape
    shape = 'Rectangle'
    for item in pad_sexpr:
        if isinstance(item, str) and item in _PAD_SHAPE_ALTIUM:
            shape = _PAD_SHAPE_ALTIUM[item]
            break

    # Hole size
    hole_size = 0.0
    drill = _find_one(pad_sexpr, 'drill')
    if drill and len(drill) > 1:
        try:
            hole_size = float(drill[1])
        except (ValueError, TypeError):
            pass

    # Layer
    layers = _find_one(pad_sexpr, 'layers')
    layer = 'TopLayer'
    if layers:
        for l in layers[1:]:
            if isinstance(l, str):
                if 'F.Cu' in l or '*.Cu' in l:
                    layer = 'TopLayer'
                    break
                elif 'B.Cu' in l:
                    layer = 'BottomLayer'
                    break

    return {
        'Type': pad_type,
        'Name': str(name),
        'X': f'{x:.4f}',
        'Y': f'{y:.4f}',
        'Width': f'{w:.4f}',
        'Height': f'{h:.4f}',
        'Layer': layer,
        'Shape': shape,
        'HoleSize': f'{hole_size:.4f}',
    }


def _line_to_row(line_sexpr):
    """Convert a KiCad fp_line to a CSV row dict."""
    start = _find_one(line_sexpr, 'start')
    end = _find_one(line_sexpr, 'end')
    layer_node = _find_one(line_sexpr, 'layer')
    width_node = _find_one(line_sexpr, 'width') or _find_one(line_sexpr, 'stroke')

    if start is None or end is None:
        return None

    x1 = float(start[1])
    y1 = float(start[2])
    x2 = float(end[1])
    y2 = float(end[2])

    layer = 'Mechanical1'
    if layer_node and len(layer_node) > 1:
        layer = _KICAD_TO_ALTIUM_LAYER.get(layer_node[1], 'Mechanical1')

    w = 0.12
    if width_node and len(width_node) > 1:
        if isinstance(width_node[1], list):
            w_sub = _find_one(width_node, 'width')
            if w_sub and len(w_sub) > 1:
                try:
                    w = float(w_sub[1])
                except (ValueError, TypeError):
                    pass
        else:
            try:
                w = float(width_node[1])
            except (ValueError, TypeError):
                pass

    # Represent line as: start point → end point
    # Width=line_width, Height=0 (line)
    return {
        'Type': 'LINE',
        'Name': f'{x1:.4f},{y1:.4f}->{x2:.4f},{y2:.4f}',
        'X': f'{x1:.4f}',
        'Y': f'{y1:.4f}',
        'Width': f'{w:.4f}',
        'Height': f'{((x2-x1)**2 + (y2-y1)**2)**0.5:.4f}',
        'Layer': layer,
        'Shape': 'Line',
        'HoleSize': '0.0000',
    }


def _circle_to_row(circle_sexpr):
    """Convert a KiCad fp_circle to a CSV row dict."""
    center = _find_one(circle_sexpr, 'center')
    end = _find_one(circle_sexpr, 'end')
    layer_node = _find_one(circle_sexpr, 'layer')
    width_node = _find_one(circle_sexpr, 'width')

    if center is None or end is None:
        return None

    cx = float(center[1])
    cy = float(center[2])
    ex = float(end[1])
    ey = float(end[2])

    import math
    radius = math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2)

    layer = 'Mechanical1'
    if layer_node and len(layer_node) > 1:
        layer = _KICAD_TO_ALTIUM_LAYER.get(layer_node[1], 'Mechanical1')

    w = 0.12
    if width_node and len(width_node) > 1:
        try:
            w = float(width_node[1])
        except (ValueError, TypeError):
            pass

    return {
        'Type': 'CIRCLE',
        'Name': f'circle@{cx:.4f},{cy:.4f}',
        'X': f'{cx:.4f}',
        'Y': f'{cy:.4f}',
        'Width': f'{radius * 2:.4f}',
        'Height': f'{radius * 2:.4f}',
        'Layer': layer,
        'Shape': 'Round',
        'HoleSize': '0.0000',
    }


def _text_to_row(text_sexpr):
    """Convert a KiCad fp_text to a CSV row dict."""
    if len(text_sexpr) < 3:
        return None

    text_type = text_sexpr[1]
    text_content = text_sexpr[2]
    x, y, _ = _get_at(text_sexpr)

    layer = 'TopOverlay'
    layer_node = _find_one(text_sexpr, 'layer')
    if layer_node and len(layer_node) > 1:
        layer = _KICAD_TO_ALTIUM_LAYER.get(layer_node[1], 'TopOverlay')

    effects = _find_one(text_sexpr, 'effects')
    font_size = 1.0
    if effects:
        font = _find_one(effects, 'font')
        if font:
            size = _find_one(font, 'size')
            if size and len(size) > 1:
                try:
                    font_size = float(size[1])
                except (ValueError, TypeError):
                    pass

    return {
        'Type': 'TEXT',
        'Name': text_content,
        'X': f'{x:.4f}',
        'Y': f'{y:.4f}',
        'Width': f'{font_size:.4f}',
        'Height': f'{font_size:.4f}',
        'Layer': layer,
        'Shape': text_type,
        'HoleSize': '0.0000',
    }


# =============================================================================
# Main conversion function
# =============================================================================

def kicad_to_altium_csv(kicad_mod_path: str, output_path: str) -> str:
    """Converte .kicad_mod para formato Altium CSV importável.

    Args:
        kicad_mod_path: Caminho do arquivo .kicad_mod de entrada.
        output_path:    Caminho do arquivo .csv de saída.

    Returns:
        Caminho do arquivo CSV gerado.

    Raises:
        FileNotFoundError: Se o arquivo .kicad_mod não existe.
        ValueError:        Se o arquivo não pode ser parseado.
    """
    if not os.path.isfile(kicad_mod_path):
        raise FileNotFoundError(f'Arquivo não encontrado: {kicad_mod_path}')

    log.info(f'Convertendo {kicad_mod_path} → Altium CSV')

    with open(kicad_mod_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        sexpr = _parse_sexpr(content)
    except Exception as e:
        raise ValueError(f'Erro ao parsear .kicad_mod: {e}')

    # Get footprint name for header comment
    fp_name = 'Unknown'
    if isinstance(sexpr, list) and len(sexpr) > 1:
        if sexpr[0] in ('footprint', 'module'):
            fp_name = sexpr[1]

    rows = []

    # Convert pads
    for pad in _find_all(sexpr, 'pad'):
        row = _pad_to_row(pad)
        if row:
            rows.append(row)

    # Convert lines
    for line in _find_all(sexpr, 'fp_line'):
        row = _line_to_row(line)
        if row:
            rows.append(row)

    # Convert circles
    for circle in _find_all(sexpr, 'fp_circle'):
        row = _circle_to_row(circle)
        if row:
            rows.append(row)

    # Convert text
    for text in _find_all(sexpr, 'fp_text'):
        row = _text_to_row(text)
        if row:
            rows.append(row)

    # Also handle KiCad 7+ format
    for line in _find_all(sexpr, 'line'):
        row = _line_to_row(line)
        if row:
            rows.append(row)

    # Write CSV
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    fieldnames = ['Type', 'Name', 'X', 'Y', 'Width', 'Height',
                  'Layer', 'Shape', 'HoleSize']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        # Write header comment
        f.write(f'# Altium CSV Export — Footprint: {fp_name}\n')
        f.write(f'# Generated by EDA Footprint Generator Platform\n')
        f.write(f'# Source: {os.path.basename(kicad_mod_path)}\n')
        f.write(f'# Units: mm\n')

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info(f'Altium CSV salvo: {output_path} ({len(rows)} elementos)')
    return output_path
