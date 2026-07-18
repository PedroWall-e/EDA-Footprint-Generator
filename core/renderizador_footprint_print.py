"""Renderizador de footprint para impressão/relatório técnico.

Difere do viewer 2D (dark theme) por usar:
- Fundo branco para impressão
- Cores de alto contraste para laser/jato de tinta
- Cotas dimensionais automáticas
"""
import os
import re
import math
import logging
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Ellipse, Arc, Polygon
import numpy as np

log = logging.getLogger(__name__)

# Attempt relative import for package use, fall back to direct for standalone
try:
    from core.renderizador_cotas import DesenhadorCotas
except ImportError:
    try:
        from renderizador_cotas import DesenhadorCotas
    except ImportError:
        DesenhadorCotas = None

# Print color palette (white background, high contrast)
PRINT_COLORS = {
    'background': '#FFFFFF',
    'pad_face': '#808080',        # gray pads
    'pad_edge': '#212121',        # dark border
    'pad_pin1': '#4CAF50',        # green pin 1
    'drill': '#FFFFFF',            # white drill holes
    'drill_edge': '#424242',       # drill hole border
    'silkscreen': '#DAA520',      # golden
    'fab': '#90CAF9',             # light blue
    'courtyard': '#FF9800',       # orange dashed
    'text': '#212121',            # black text
    'grid': '#E0E0E0',            # light gray grid
    'pin_num': '#FFFFFF',         # pad number text (white)
    'pin_num_p1': '#000000',      # pad number text for pin 1 (black)
}


def parse_kicad_mod(filepath):
    """Parse .kicad_mod file and return structured data.

    Adapted from gui/painel_footprint_2d.py for standalone use.
    Returns dict with keys: name, pads, lines, arcs, circles, polys
    Each pad has: num, x, y, w, h, shape, drill
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return {'pads': [], 'lines': [], 'arcs': [], 'circles': [],
                'polys': [], 'name': 'Erro'}

    # Module/footprint name
    name_m = re.search(r'\((?:module|footprint)\s+"?([^"\s)]+)"?', content)
    name = name_m.group(1) if name_m else 'Desconhecido'

    pads = []

    # ── Pads SMD (rect, roundrect, oval, circle) ───────────────────────────────
    # Supports KiCad 5/6 (pad without quotes) and KiCad 7/8 (pad "1" with quotes)
    _smd_any = re.compile(
        r'\(pad\s+"?(\w+)"?\s+smd\s+(rect|roundrect|oval|circle)\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _smd_any.finditer(content):
        raw_shape = m.group(2)
        pads.append({
            'num': m.group(1),
            'x': float(m.group(3)), 'y': float(m.group(4)),
            'w': float(m.group(5)), 'h': float(m.group(6)),
            'shape': f'smd_{raw_shape}', 'drill': 0
        })

    # ── Pads THT circulares ────────────────────────────────────────────────────
    _tht_circ = re.compile(
        r'\(pad\s+"?(\w+)"?\s+thru_hole\s+circle\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(drill\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _tht_circ.finditer(content):
        pads.append({
            'num': m.group(1),
            'x': float(m.group(2)), 'y': float(m.group(3)),
            'w': float(m.group(4)), 'h': float(m.group(5)),
            'shape': 'tht_circle', 'drill': float(m.group(6))
        })

    # ── Pads THT retangulares (pino 1 quadrado) ────────────────────────────────
    _tht_rect = re.compile(
        r'\(pad\s+"?(\w+)"?\s+thru_hole\s+rect\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(drill\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _tht_rect.finditer(content):
        pads.append({
            'num': m.group(1),
            'x': float(m.group(2)), 'y': float(m.group(3)),
            'w': float(m.group(4)), 'h': float(m.group(5)),
            'shape': 'tht_rect', 'drill': float(m.group(6))
        })

    # ── Pads THT ovais ─────────────────────────────────────────────────────────
    _tht_oval = re.compile(
        r'\(pad\s+"?(\w+)"?\s+thru_hole\s+oval\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(drill\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _tht_oval.finditer(content):
        pads.append({
            'num': m.group(1),
            'x': float(m.group(2)), 'y': float(m.group(3)),
            'w': float(m.group(4)), 'h': float(m.group(5)),
            'shape': 'tht_oval', 'drill': float(m.group(6))
        })

    # ── fp_line (KiCad 5/6 and 7/8) ───────────────────────────────────────────
    _line_v56 = re.compile(
        r'\(fp_line\s+\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    _line_v7 = re.compile(
        r'\(fp_line\s+\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(stroke\s+[^)]*\)\s*'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    lines = []
    _seen_lines = set()
    for regex in (_line_v56, _line_v7):
        for m in regex.finditer(content):
            key = (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
            if key not in _seen_lines:
                _seen_lines.add(key)
                lines.append({
                    'x1': float(m.group(1)), 'y1': float(m.group(2)),
                    'x2': float(m.group(3)), 'y2': float(m.group(4)),
                    'layer': m.group(5)
                })

    # ── fp_arc (KiCad 5/6: center=start, endpoint=end, angle=angle) ───────────
    _arc_old = re.compile(
        r'\(fp_arc\s+\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(angle\s+([\-\d.]+)\)\s+'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    arcs = []
    for m in _arc_old.finditer(content):
        cx, cy = float(m.group(1)), float(m.group(2))
        ex, ey = float(m.group(3)), float(m.group(4))
        angle = float(m.group(5))
        layer = m.group(6)
        r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
        a1 = math.degrees(math.atan2(-(ey - cy), ex - cx))
        a2 = a1 + angle
        arcs.append({
            'cx': cx, 'cy': cy, 'r': r,
            'a1': a1, 'a2': a2, 'layer': layer
        })

    # ── fp_arc (KiCad 7/8: start/mid/end style) ──────────────────────────────
    _arc_v7 = re.compile(
        r'\(fp_arc\s+\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(mid\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'(?:\(stroke\s+[^)]*\)\s*)?'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    for m in _arc_v7.finditer(content):
        sx, sy = float(m.group(1)), float(m.group(2))
        mx, my = float(m.group(3)), float(m.group(4))
        ex, ey = float(m.group(5)), float(m.group(6))
        layer = m.group(7)
        # Calculate circle from 3 points (start, mid, end)
        ax_v, ay_v = sx, sy
        bx_v, by_v = mx, my
        cx_v, cy_v = ex, ey
        D = 2 * (ax_v * (by_v - cy_v) + bx_v * (cy_v - ay_v) + cx_v * (ay_v - by_v))
        if abs(D) < 1e-10:
            continue
        ux = ((ax_v ** 2 + ay_v ** 2) * (by_v - cy_v) +
              (bx_v ** 2 + by_v ** 2) * (cy_v - ay_v) +
              (cx_v ** 2 + cy_v ** 2) * (ay_v - by_v)) / D
        uy = ((ax_v ** 2 + ay_v ** 2) * (cx_v - bx_v) +
              (bx_v ** 2 + by_v ** 2) * (ax_v - cx_v) +
              (cx_v ** 2 + cy_v ** 2) * (bx_v - ax_v)) / D
        r = math.sqrt((ax_v - ux) ** 2 + (ay_v - uy) ** 2)
        a_start = math.degrees(math.atan2(-(sy - uy), sx - ux))
        a_end = math.degrees(math.atan2(-(ey - uy), ex - ux))
        a_mid = math.degrees(math.atan2(-(my - uy), mx - ux))
        # Ensure arc goes through mid point
        def _normalize(a):
            while a < 0:
                a += 360
            while a >= 360:
                a -= 360
            return a
        a_s = _normalize(a_start)
        a_e = _normalize(a_end)
        a_m = _normalize(a_mid)
        # Check if mid is in the arc from start to end (CCW)
        if a_s < a_e:
            if not (a_s <= a_m <= a_e):
                a_s, a_e = a_e, a_s
        else:
            if a_m < a_s and a_m > a_e:
                a_s, a_e = a_e, a_s
        arcs.append({
            'cx': ux, 'cy': uy, 'r': r,
            'a1': a_s, 'a2': a_e, 'layer': layer
        })

    # ── fp_circle ─────────────────────────────────────────────────────────────
    _circle = re.compile(
        r'\(fp_circle\s+\(center\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    circles = []
    for m in _circle.finditer(content):
        cx, cy = float(m.group(1)), float(m.group(2))
        ex, ey = float(m.group(3)), float(m.group(4))
        r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
        circles.append({'cx': cx, 'cy': cy, 'r': r, 'layer': m.group(5)})

    # KiCad 7/8 fp_circle with (stroke ...)
    _circle_v7 = re.compile(
        r'\(fp_circle\s+\(center\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s+'
        r'\(stroke\s+[^)]*\)\s*'
        r'\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    for m in _circle_v7.finditer(content):
        cx, cy = float(m.group(1)), float(m.group(2))
        ex, ey = float(m.group(3)), float(m.group(4))
        r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
        key = (cx, cy, r, m.group(5))
        # Avoid duplicates from the v56 regex
        if not any(c['cx'] == cx and c['cy'] == cy and abs(c['r'] - r) < 0.001
                   and c['layer'] == m.group(5) for c in circles):
            circles.append({'cx': cx, 'cy': cy, 'r': r, 'layer': m.group(5)})

    # ── fp_poly ───────────────────────────────────────────────────────────────
    _poly_block = re.compile(
        r'\(fp_poly\s+\(pts(.*?)\)\s+\(layer\s+"?([\w.]+)"?\)',
        re.DOTALL)
    _xy = re.compile(r'\(xy\s+([\-\d.]+)\s+([\-\d.]+)\)')
    polys = []
    for pm in _poly_block.finditer(content):
        pts = [(float(x), float(y)) for x, y in _xy.findall(pm.group(1))]
        if pts:
            polys.append({'pts': pts, 'layer': pm.group(2)})

    return {
        'pads': pads, 'lines': lines, 'arcs': arcs,
        'circles': circles, 'polys': polys, 'name': name
    }


# Layer style mapping for print (white background, high contrast)
_PRINT_LAYER_STYLE = {
    'F.SilkS':  {'color': PRINT_COLORS['silkscreen'], 'lw': 1.0, 'ls': '-',  'zorder': 4},
    'F.Fab':    {'color': PRINT_COLORS['fab'],         'lw': 0.7, 'ls': '-',  'zorder': 3},
    'F.CrtYd':  {'color': PRINT_COLORS['courtyard'],  'lw': 0.6, 'ls': '--', 'zorder': 2},
    'B.SilkS':  {'color': '#9C27B0',                  'lw': 0.8, 'ls': '-',  'zorder': 1},
    'B.Fab':    {'color': '#64B5F6',                   'lw': 0.7, 'ls': '-',  'zorder': 1},
    'B.CrtYd':  {'color': '#FFC107',                   'lw': 0.6, 'ls': '--', 'zorder': 1},
}


def render_footprint_print(ax, kicad_mod_path, cotas=True, escala=1.0,
                           show_grid=True, show_pin_numbers=True,
                           titulo=None):
    """Renderiza footprint no Axes com tema de impressão.

    Args:
        ax: matplotlib Axes
        kicad_mod_path: path to .kicad_mod file
        cotas: whether to draw dimension rulers
        escala: scale factor (1.0 = 1:1)
        show_grid: whether to draw mm grid
        show_pin_numbers: whether to show pad numbers
        titulo: optional title text
    """
    data = parse_kicad_mod(kicad_mod_path)
    if not data or (not data['pads'] and not data['lines']):
        ax.text(0.5, 0.5, 'Erro ao carregar footprint',
                ha='center', transform=ax.transAxes,
                fontsize=10, color='#9E9E9E')
        return

    ax.set_facecolor(PRINT_COLORS['background'])
    ax.set_aspect('equal')

    pads = data.get('pads', [])
    lines_data = data.get('lines', [])
    arcs_data = data.get('arcs', [])
    circles_data = data.get('circles', [])
    polys_data = data.get('polys', [])
    name = data.get('name', '')

    # Collect all coordinates for grid bounds
    all_xs = []
    all_ys = []
    for pad in pads:
        all_xs.append(pad['x'])
        all_ys.append(-pad['y'])
    for line in lines_data:
        all_xs.extend([line['x1'], line['x2']])
        all_ys.extend([-line['y1'], -line['y2']])
    for arc in arcs_data:
        all_xs.append(arc['cx'])
        all_ys.append(-arc['cy'])
    for circ in circles_data:
        all_xs.extend([circ['cx'] - circ['r'], circ['cx'] + circ['r']])
        all_ys.extend([-circ['cy'] - circ['r'], -circ['cy'] + circ['r']])
    for poly in polys_data:
        for px, py in poly['pts']:
            all_xs.append(px)
            all_ys.append(-py)

    # Draw grid (1mm intervals)
    if show_grid and all_xs and all_ys:
        g_x0 = math.floor(min(all_xs)) - 2
        g_x1 = math.ceil(max(all_xs)) + 2
        g_y0 = math.floor(min(all_ys)) - 2
        g_y1 = math.ceil(max(all_ys)) + 2
        for gx in range(g_x0, g_x1 + 1):
            lw = 0.3 if gx % 5 != 0 else 0.5
            ax.axvline(x=gx, color=PRINT_COLORS['grid'], lw=lw, zorder=0)
        for gy in range(g_y0, g_y1 + 1):
            lw = 0.3 if gy % 5 != 0 else 0.5
            ax.axhline(y=gy, color=PRINT_COLORS['grid'], lw=lw, zorder=0)

    # ── Draw lines (fp_line) per layer ────────────────────────────────────────
    for line in lines_data:
        layer = line['layer']
        style = _PRINT_LAYER_STYLE.get(
            layer,
            {'color': '#BDBDBD', 'lw': 0.5, 'ls': '-', 'zorder': 1}
        )
        ax.plot(
            [line['x1'], line['x2']], [-line['y1'], -line['y2']],
            color=style['color'], linewidth=style['lw'],
            linestyle=style['ls'], zorder=style['zorder'],
            solid_capstyle='round',
        )

    # ── Draw arcs (fp_arc) ───────────────────────────────────────────────────
    for arc in arcs_data:
        layer = arc['layer']
        style = _PRINT_LAYER_STYLE.get(
            layer,
            {'color': '#BDBDBD', 'lw': 0.5, 'zorder': 1}
        )
        patch = Arc(
            (arc['cx'], -arc['cy']),
            width=arc['r'] * 2, height=arc['r'] * 2,
            angle=0,
            theta1=min(arc['a1'], arc['a2']),
            theta2=max(arc['a1'], arc['a2']),
            color=style['color'],
            linewidth=style['lw'],
            zorder=style.get('zorder', 2),
        )
        ax.add_patch(patch)

    # ── Draw circles (fp_circle) ─────────────────────────────────────────────
    for circ in circles_data:
        layer = circ['layer']
        style = _PRINT_LAYER_STYLE.get(
            layer,
            {'color': '#BDBDBD', 'lw': 0.5, 'zorder': 1}
        )
        patch = Circle(
            (circ['cx'], -circ['cy']), circ['r'],
            fill=False,
            edgecolor=style['color'],
            linewidth=style['lw'],
            linestyle=style.get('ls', '-'),
            zorder=style.get('zorder', 2),
        )
        ax.add_patch(patch)

    # ── Draw polygons (fp_poly) ──────────────────────────────────────────────
    for poly in polys_data:
        layer = poly['layer']
        style = _PRINT_LAYER_STYLE.get(
            layer,
            {'color': '#BDBDBD', 'lw': 0.5, 'zorder': 1}
        )
        pts_inv = [(x, -y) for x, y in poly['pts']]
        patch = Polygon(
            pts_inv, closed=True,
            fill=False,
            edgecolor=style['color'],
            linewidth=style['lw'],
            zorder=style.get('zorder', 2),
        )
        ax.add_patch(patch)

    # ── Draw pads ────────────────────────────────────────────────────────────
    for i, pad in enumerate(pads):
        x, y = pad['x'], -pad['y']  # Y inverted
        w, h = pad['w'], pad['h']
        shape = pad.get('shape', 'smd_rect')
        drill = pad.get('drill', 0)
        num = pad.get('num', '')
        is_pin1 = (str(num) == '1' or str(num) == 'A1')

        face = PRINT_COLORS['pad_pin1'] if is_pin1 else PRINT_COLORS['pad_face']
        edge = PRINT_COLORS['pad_edge']

        if shape == 'smd_circle' or shape == 'tht_circle':
            circ_patch = Circle(
                (x, y), w / 2,
                facecolor=face, edgecolor=edge,
                lw=0.8, zorder=5
            )
            ax.add_patch(circ_patch)

        elif shape == 'smd_oval' or shape == 'tht_oval':
            ell = Ellipse(
                (x, y), w, h,
                facecolor=face, edgecolor=edge,
                lw=0.8, zorder=5
            )
            ax.add_patch(ell)

        elif shape == 'smd_roundrect':
            rpad = min(w, h) * 0.25
            box = FancyBboxPatch(
                (x - w / 2 + rpad, y - h / 2 + rpad),
                w - 2 * rpad, h - 2 * rpad,
                boxstyle=f'round,pad={rpad}',
                facecolor=face, edgecolor=edge,
                lw=0.8, zorder=5
            )
            ax.add_patch(box)

        elif shape in ('smd_rect', 'tht_rect'):
            box = FancyBboxPatch(
                (x - w / 2, y - h / 2), w, h,
                boxstyle='square,pad=0',
                facecolor=face, edgecolor=edge,
                lw=0.8, zorder=5
            )
            ax.add_patch(box)

        else:
            # Fallback: draw as rectangle
            box = FancyBboxPatch(
                (x - w / 2, y - h / 2), w, h,
                boxstyle='square,pad=0',
                facecolor=face, edgecolor=edge,
                lw=0.8, zorder=5
            )
            ax.add_patch(box)

        # Drill hole (for THT pads)
        if drill > 0:
            hole = Circle(
                (x, y), drill / 2,
                facecolor=PRINT_COLORS['drill'],
                edgecolor=PRINT_COLORS['drill_edge'],
                lw=0.5, zorder=6
            )
            ax.add_patch(hole)

        # Pad number
        if show_pin_numbers:
            fontsize = 5 if len(pads) > 20 else 6
            txt_color = (PRINT_COLORS['pin_num_p1'] if is_pin1
                         else PRINT_COLORS['pin_num'])
            ax.text(
                x, y, str(num),
                ha='center', va='center',
                fontsize=fontsize, color=txt_color,
                fontweight='bold', zorder=7
            )

    # ── Title ────────────────────────────────────────────────────────────────
    if titulo:
        ax.set_title(titulo, fontsize=9, fontweight='bold',
                     color=PRINT_COLORS['text'], pad=8)
    elif name:
        n_smd = sum(1 for p in pads if p.get('shape', '').startswith('smd_'))
        n_tht = sum(1 for p in pads if p.get('shape', '').startswith('tht_'))
        if n_tht == 0:
            tipo_info = f'{n_smd} SMD'
        elif n_smd == 0:
            tipo_info = f'{n_tht} PTH'
        else:
            tipo_info = f'{n_smd} SMD + {n_tht} PTH'
        ax.set_title(
            f'Footprint — {name}  |  {len(pads)} pads ({tipo_info})',
            fontsize=9, fontweight='bold',
            color=PRINT_COLORS['text'], pad=8
        )

    # ── Auto-add cotas (dimension rulers) ────────────────────────────────────
    if cotas and pads and DesenhadorCotas is not None:
        dc = DesenhadorCotas(ax, escala=escala)
        corpo = _extract_body_bounds(data)
        dc.auto_cotas(pads, corpo=corpo)

    # ── Auto-scale axes with margin ──────────────────────────────────────────
    # A folga e o piso de viewport existem porque as cotas têm texto de tamanho
    # fixo (pontos) e offsets em mm: se uma peça minúscula (0402) for ampliada
    # até preencher a folha, o texto fica enorme em relação aos gaps entre cotas
    # e elas se sobrepõem. O piso mostra a peça pequena e centralizada — como um
    # preview de CAD — mantendo o texto legível e as cotas separadas. Aspecto
    # igual evita distorcer um pad 1×0,5 diferente em X e Y.
    ax.autoscale()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    span = max(xlim[1] - xlim[0], ylim[1] - ylim[0])
    margin = max(2.0, span * 0.12)
    cx = (xlim[0] + xlim[1]) / 2
    cy = (ylim[0] + ylim[1]) / 2
    MIN_SEMI_SPAN = 7.0
    semi = max((xlim[1] - xlim[0]) / 2 + margin,
               (ylim[1] - ylim[0]) / 2 + margin,
               MIN_SEMI_SPAN)
    ax.set_xlim(cx - semi, cx + semi)
    ax.set_ylim(cy - semi, cy + semi)
    ax.set_aspect('equal', adjustable='box')

    ax.set_xlabel('mm', fontsize=7, color='#616161')
    ax.set_ylabel('mm', fontsize=7, color='#616161')
    ax.tick_params(labelsize=6, colors='#9E9E9E')


def _extract_body_bounds(data):
    """Extract body rectangle from Fab layer lines."""
    fab_lines = [l for l in data.get('lines', [])
                 if 'Fab' in l.get('layer', '')]
    if not fab_lines:
        return None
    xs = []
    ys = []
    for l in fab_lines:
        xs.extend([l['x1'], l['x2']])
        ys.extend([l['y1'], l['y2']])
    if xs and ys:
        return {'x0': min(xs), 'y0': min(ys), 'x1': max(xs), 'y1': max(ys)}
    return None
