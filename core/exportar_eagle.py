"""
Exportar footprint para formato Eagle .lbr (XML).

Converte um arquivo .kicad_mod (S-Expression KiCad) para o formato
Eagle .lbr (XML), mapeando:
  - Pads SMD  → <smd> elements
  - Pads PTH  → <pad> elements
  - Silkscreen (F.SilkS) → <wire> on layer 21 (tPlace)
  - Courtyard (F.CrtYd) → <wire> on layer 39 (tKeepout)
  - Fab (F.Fab) → <wire> on layer 51 (tDocu)
  - Text → <text> elements

Estrutura XML Eagle:
  <eagle>
    <drawing>
      <library>
        <packages>
          <package>
            ...
          </package>
        </packages>
      </library>
    </drawing>
  </eagle>
"""

import xml.etree.ElementTree as ET
import re
import os
import logging

log = logging.getLogger(__name__)


# =============================================================================
# Layer mapping: KiCad → Eagle
# =============================================================================

_KICAD_TO_EAGLE_LAYER = {
    'F.SilkS':    21,   # tPlace
    'B.SilkS':    22,   # bPlace
    'F.Fab':      51,   # tDocu
    'B.Fab':      52,   # bDocu
    'F.CrtYd':    39,   # tKeepout
    'B.CrtYd':    40,   # bKeepout
    'F.Cu':        1,   # Top
    'B.Cu':       16,   # Bottom
    'F.Mask':     29,   # tStop
    'B.Mask':     30,   # bStop
    'F.Paste':    31,   # tCream
    'B.Paste':    32,   # bCream
    'Edge.Cuts':  20,   # Dimension
}

_PAD_SHAPE_MAP = {
    'rect':       'square',
    'roundrect':  'square',  # Eagle doesn't have roundrect natively
    'circle':     'round',
    'oval':       'long',
    'custom':     'square',
}


# =============================================================================
# S-Expression parser (shared module)
# =============================================================================

try:
    from core.sexpr_parser import (parse_sexpr, find_all, find_one,
                                   get_at, get_size, get_attr)
except ImportError:
    from sexpr_parser import (parse_sexpr, find_all, find_one,
                              get_at, get_size, get_attr)

# Aliases internos para compatibilidade
_parse_sexpr = parse_sexpr
_find_all = find_all
_find_one = find_one
_get_attr = get_attr
_get_at = get_at
_get_size = get_size


# =============================================================================
# Conversion functions
# =============================================================================

def _convert_pad_smd(pad_sexpr, package_elem):
    """Convert a KiCad SMD pad to Eagle <smd> element."""
    name = pad_sexpr[1] if len(pad_sexpr) > 1 else ''
    x, y, angle = _get_at(pad_sexpr)
    w, h = _get_size(pad_sexpr)

    # Eagle Y is inverted relative to KiCad
    y = -y

    attrs = {
        'name': str(name),
        'x': f'{x:.4f}',
        'y': f'{y:.4f}',
        'dx': f'{w:.4f}',
        'dy': f'{h:.4f}',
        'layer': '1',  # Top copper
    }

    if angle != 0:
        attrs['rot'] = f'R{angle:.0f}'

    # Roundness for roundrect pads
    shape_list = _find_one(pad_sexpr, 'roundrect_rratio')
    if shape_list:
        try:
            ratio = float(shape_list[1])
            roundness = int(ratio * 200)  # Eagle uses percentage (0-100)
            roundness = min(100, max(0, roundness))
            attrs['roundness'] = str(roundness)
        except (ValueError, IndexError):
            pass

    ET.SubElement(package_elem, 'smd', attrs)


def _convert_pad_pth(pad_sexpr, package_elem):
    """Convert a KiCad PTH pad to Eagle <pad> element."""
    name = pad_sexpr[1] if len(pad_sexpr) > 1 else ''
    x, y, angle = _get_at(pad_sexpr)

    # Eagle Y is inverted
    y = -y

    # Get drill size
    drill = _find_one(pad_sexpr, 'drill')
    drill_size = 0.8
    if drill and len(drill) > 1:
        try:
            drill_size = float(drill[1])
        except (ValueError, TypeError):
            pass

    # Get pad size
    w, h = _get_size(pad_sexpr)

    # Determine shape
    shape_name = 'round'
    for item in pad_sexpr:
        if isinstance(item, str) and item in ('rect', 'roundrect', 'circle', 'oval'):
            shape_name = _PAD_SHAPE_MAP.get(item, 'round')
            break

    # If width != height, it's an oblong pad
    if abs(w - h) > 0.01:
        shape_name = 'long'

    attrs = {
        'name': str(name),
        'x': f'{x:.4f}',
        'y': f'{y:.4f}',
        'drill': f'{drill_size:.4f}',
        'shape': shape_name,
    }

    # Add diameter if it's larger than drill + default annular ring
    if w > drill_size:
        attrs['diameter'] = f'{w:.4f}'

    if angle != 0:
        attrs['rot'] = f'R{angle:.0f}'

    ET.SubElement(package_elem, 'pad', attrs)


def _convert_line(line_sexpr, package_elem):
    """Convert a KiCad fp_line to Eagle <wire> element."""
    start = _find_one(line_sexpr, 'start')
    end = _find_one(line_sexpr, 'end')
    layer = _find_one(line_sexpr, 'layer')
    width = _find_one(line_sexpr, 'width') or _find_one(line_sexpr, 'stroke')

    if start is None or end is None:
        return

    x1 = float(start[1])
    y1 = -float(start[2])
    x2 = float(end[1])
    y2 = -float(end[2])

    # Determine Eagle layer
    eagle_layer = 51  # default: tDocu
    if layer and len(layer) > 1:
        layer_name = layer[1]
        eagle_layer = _KICAD_TO_EAGLE_LAYER.get(layer_name, 51)

    # Width
    w = 0.12
    if width and len(width) > 1:
        if isinstance(width[1], list):
            # stroke format: (stroke (width 0.12) ...)
            w_node = _find_one(width, 'width')
            if w_node and len(w_node) > 1:
                try:
                    w = float(w_node[1])
                except (ValueError, TypeError):
                    pass
        else:
            try:
                w = float(width[1])
            except (ValueError, TypeError):
                pass

    ET.SubElement(package_elem, 'wire', {
        'x1': f'{x1:.4f}',
        'y1': f'{y1:.4f}',
        'x2': f'{x2:.4f}',
        'y2': f'{y2:.4f}',
        'width': f'{w:.4f}',
        'layer': str(eagle_layer),
    })


def _convert_circle(circle_sexpr, package_elem):
    """Convert a KiCad fp_circle to Eagle <circle> element."""
    center = _find_one(circle_sexpr, 'center')
    end = _find_one(circle_sexpr, 'end')
    layer = _find_one(circle_sexpr, 'layer')
    width = _find_one(circle_sexpr, 'width') or _find_one(circle_sexpr, 'stroke')

    if center is None or end is None:
        return

    cx = float(center[1])
    cy = -float(center[2])
    ex = float(end[1])
    ey = -float(end[2])

    import math
    radius = math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2)

    eagle_layer = 51
    if layer and len(layer) > 1:
        eagle_layer = _KICAD_TO_EAGLE_LAYER.get(layer[1], 51)

    w = 0.12
    if width and len(width) > 1:
        try:
            w = float(width[1])
        except (ValueError, TypeError):
            pass

    ET.SubElement(package_elem, 'circle', {
        'x': f'{cx:.4f}',
        'y': f'{cy:.4f}',
        'radius': f'{radius:.4f}',
        'width': f'{w:.4f}',
        'layer': str(eagle_layer),
    })


def _convert_text(text_sexpr, package_elem):
    """Convert a KiCad fp_text to Eagle <text> element."""
    if len(text_sexpr) < 3:
        return

    text_type = text_sexpr[1]  # reference, value, user
    text_content = text_sexpr[2]
    x, y, angle = _get_at(text_sexpr)
    y = -y

    layer = _find_one(text_sexpr, 'layer')
    eagle_layer = 25  # tNames
    if text_type == 'value':
        eagle_layer = 27  # tValues
    elif layer and len(layer) > 1:
        eagle_layer = _KICAD_TO_EAGLE_LAYER.get(layer[1], 25)

    # Font size
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

    # Use >NAME or >VALUE for reference/value
    if text_type == 'reference':
        text_content = '>NAME'
    elif text_type == 'value':
        text_content = '>VALUE'

    attrs = {
        'x': f'{x:.4f}',
        'y': f'{y:.4f}',
        'size': f'{font_size:.4f}',
        'layer': str(eagle_layer),
    }

    if angle != 0:
        attrs['rot'] = f'R{angle:.0f}'

    text_elem = ET.SubElement(package_elem, 'text', attrs)
    text_elem.text = text_content


# =============================================================================
# Main conversion function
# =============================================================================

def kicad_to_eagle(kicad_mod_path: str, output_path: str) -> str:
    """Converte .kicad_mod para Eagle .lbr XML.

    Args:
        kicad_mod_path: Caminho do arquivo .kicad_mod de entrada.
        output_path:    Caminho do arquivo .lbr de saída.

    Returns:
        Caminho do arquivo .lbr gerado.

    Raises:
        FileNotFoundError: Se o arquivo .kicad_mod não existe.
        ValueError:        Se o arquivo não pode ser parseado.
    """
    if not os.path.isfile(kicad_mod_path):
        raise FileNotFoundError(f'Arquivo não encontrado: {kicad_mod_path}')

    log.info(f'Convertendo {kicad_mod_path} → Eagle .lbr')

    with open(kicad_mod_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse S-Expression
    try:
        sexpr = _parse_sexpr(content)
    except Exception as e:
        raise ValueError(f'Erro ao parsear .kicad_mod: {e}')

    # Get footprint name
    fp_name = 'Unknown'
    if isinstance(sexpr, list) and len(sexpr) > 1:
        if sexpr[0] == 'footprint' or sexpr[0] == 'module':
            fp_name = sexpr[1]

    # Build Eagle XML structure
    eagle = ET.Element('eagle', {'version': '7.7.0'})
    drawing = ET.SubElement(eagle, 'drawing')
    library = ET.SubElement(drawing, 'library', {'name': 'DataFrontier'})
    packages = ET.SubElement(library, 'packages')
    package = ET.SubElement(packages, 'package', {'name': fp_name})

    # Add description
    desc = ET.SubElement(package, 'description')
    desc.text = f'Generated by Data Frontier from {os.path.basename(kicad_mod_path)}'

    # Convert pads
    for pad in _find_all(sexpr, 'pad'):
        pad_type = None
        for item in pad:
            if isinstance(item, str) and item in ('smd', 'thru_hole'):
                pad_type = item
                break

        if pad_type == 'smd':
            _convert_pad_smd(pad, package)
        elif pad_type == 'thru_hole':
            _convert_pad_pth(pad, package)

    # Convert lines (fp_line)
    for line in _find_all(sexpr, 'fp_line'):
        _convert_line(line, package)

    # Convert circles (fp_circle)
    for circle in _find_all(sexpr, 'fp_circle'):
        _convert_circle(circle, package)

    # Convert text (fp_text)
    for text in _find_all(sexpr, 'fp_text'):
        _convert_text(text, package)

    # Also handle KiCad 7+ format (line, circle, etc. without fp_ prefix,
    # nested under footprint)
    for line in _find_all(sexpr, 'line'):
        _convert_line(line, package)
    for circle in _find_all(sexpr, 'circle'):
        _convert_circle(circle, package)

    # Write XML
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    tree = ET.ElementTree(eagle)
    ET.indent(tree, space='  ')
    tree.write(output_path, encoding='unicode', xml_declaration=True)

    log.info(f'Eagle .lbr salvo: {output_path}')
    return output_path
