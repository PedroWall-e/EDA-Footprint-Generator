# =============================================================================
# painel_footprint_2d.py
# Widget Qt com visualizador 2D de footprints KiCad usando matplotlib.
# Parseia o arquivo .kicad_mod e desenha pads, silkscreen, courtyard, fab.
# Zoom: scroll do mouse (centrado no cursor) + barra de ferramentas.
# Legenda: posicionada ABAIXO do plot, sem sobrepor o desenho.
# Auto-atualiza via QFileSystemWatcher quando o arquivo muda.
# =============================================================================

import re
import os
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QFrame, QAction, QFileDialog
)
from PyQt5.QtCore import Qt, QFileSystemWatcher, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle, Arc, Polygon, Ellipse
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np

from gui.canvas_base import InteractiveCanvas


# =============================================================================
# Paleta de cores por camada (tema escuro estilo KiCad)
# =============================================================================
LAYER_STYLE = {
    'F.SilkS':  {'color': '#FFD700', 'lw': 1.2,  'ls': '-',  'zorder': 4},
    'F.Fab':    {'color': '#4FC3F7', 'lw': 0.8,  'ls': '-',  'zorder': 3},
    'F.CrtYd':  {'color': '#FF9800', 'lw': 0.7,  'ls': '--', 'zorder': 2},
    'B.SilkS':  {'color': '#CE93D8', 'lw': 1.0,  'ls': '-',  'zorder': 1},
    'B.Fab':    {'color': '#90CAF9', 'lw': 0.8,  'ls': '-',  'zorder': 1},
    'B.CrtYd':  {'color': '#FFCC02', 'lw': 0.7,  'ls': '--', 'zorder': 1},
}
PAD_FACECOLOR   = '#C47722'   # cobre
PAD_EDGECOLOR   = '#FFD700'   # borda dourada
PAD_ALPHA       = 0.92
BG_COLOR        = '#1A1A2E'   # fundo escuro
GRID_COLOR      = '#2D2D4E'   # grade faint
TEXT_COLOR      = '#E0E0E0'   # texto geral
PIN1_FACECOLOR  = '#7CFC00'   # pino 1 verde brilhante


# =============================================================================
# Parser S-Expression .kicad_mod
# =============================================================================
def parse_kicad_mod(filepath: str) -> dict:
    """
    Parseia um arquivo .kicad_mod e retorna dicionario com:
      pads   : list of {num, x, y, w, h, shape, drill}  (smd_rect | tht_circle | tht_rect)
      lines  : list of {x1, y1, x2, y2, layer}
      arcs   : list of {cx, cy, r, a1, a2, layer}       (angulos em graus)
      circles: list of {cx, cy, r, layer}
      polys  : list of {pts: [(x,y),...], layer}
      name   : str
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return {'pads': [], 'lines': [], 'arcs': [], 'circles': [], 'polys': [], 'name': 'Erro'}

    # Nome do modulo
    name_m = re.search(r'\((?:module|footprint)\s+"?([^"\s)]+)"?', content)
    name = name_m.group(1) if name_m else 'Desconhecido'

    pads = []

    # ── Pads SMD (rect, roundrect, oval, circle) ───────────────────────────────
    # Suporta KiCad 5/6 (pad sem aspas) e KiCad 7/8 (pad "1" com aspas)
    _smd_any = re.compile(
        r'\(pad\s+"?(\w+)"?\s+smd\s+(rect|roundrect|oval|circle)\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _smd_any.finditer(content):
        raw_shape = m.group(2)  # rect | roundrect | oval | circle
        pads.append({'num': m.group(1), 'x': float(m.group(3)), 'y': float(m.group(4)),
                     'w': float(m.group(5)), 'h': float(m.group(6)),
                     'shape': f'smd_{raw_shape}', 'drill': 0})

    # ── Pads THT circulares ────────────────────────────────────────────────────
    _tht_circ = re.compile(
        r'\(pad\s+"?(\w+)"?\s+thru_hole\s+circle\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(drill\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _tht_circ.finditer(content):
        pads.append({'num': m.group(1), 'x': float(m.group(2)), 'y': float(m.group(3)),
                     'w': float(m.group(4)), 'h': float(m.group(5)),
                     'shape': 'tht_circle', 'drill': float(m.group(6))})

    # ── Pads THT retangulares (pino 1 quadrado) ────────────────────────────────
    _tht_rect = re.compile(
        r'\(pad\s+"?(\w+)"?\s+thru_hole\s+rect\s+'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+[\-\d.]+)?\)\s*'
        r'\(size\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(drill\s+([\-\d.]+)\)',
        re.DOTALL)
    for m in _tht_rect.finditer(content):
        pads.append({'num': m.group(1), 'x': float(m.group(2)), 'y': float(m.group(3)),
                     'w': float(m.group(4)), 'h': float(m.group(5)),
                     'shape': 'tht_rect', 'drill': float(m.group(6))})

    # ── fp_line (KiCad 5/6 e 7/8) ─────────────────────────────────────────────
    # v5/6: (fp_line (start X Y) (end X Y) (layer F.SilkS) (width 0.12))
    # v7+ : (fp_line (start X Y) (end X Y) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
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
                lines.append({'x1': float(m.group(1)), 'y1': float(m.group(2)),
                              'x2': float(m.group(3)), 'y2': float(m.group(4)),
                              'layer': m.group(5)})

    # ── fp_arc (KiCad 5/6: center=start, endpoint=end, angle=angle) ───────────
    # Formato: (fp_arc (start Cx Cy) (end Ex Ey) (angle A) (layer L))
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
        angle  = float(m.group(5))   # extensao do arco em graus
        layer  = m.group(6)
        r = ((ex-cx)**2 + (ey-cy)**2) ** 0.5
        # angulo inicial: do centro ao ponto end
        import math
        a1 = math.degrees(math.atan2(-(ey - cy), ex - cx))   # Y invertido
        a2 = a1 + angle
        arcs.append({'cx': cx, 'cy': cy, 'r': r, 'a1': a1, 'a2': a2, 'layer': layer})

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
        r = ((ex-cx)**2 + (ey-cy)**2) ** 0.5
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

    return {'pads': pads, 'lines': lines, 'arcs': arcs,
            'circles': circles, 'polys': polys, 'name': name}


# =============================================================================
# Canvas matplotlib
# =============================================================================
class FootprintCanvas(InteractiveCanvas):
    """Canvas matplotlib com tema escuro para renderizar o footprint.

    Inherits scroll-zoom, middle/right-button pan, keyboard navigation,
    and fit_all from :class:`InteractiveCanvas`.  Only rendering and
    domain-specific styling are defined here.
    """

    # Fracao do espaco Y reservada para a legenda abaixo do plot
    _LEGEND_BOTTOM_FRAC = 0.13

    def __init__(self, parent=None):
        super().__init__(
            parent,
            xlabel="X (mm)",
            ylabel="Y (mm)",
            bottom=self._LEGEND_BOTTOM_FRAC,
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Layer visibility state — toggled from the toolbar
        self._layer_vis = {
            'F.Cu':    True,
            'F.SilkS': True,
            'F.Fab':   True,
            'F.CrtYd': True,
            'Pads':    True,
            'Pin 1':   True,
        }

    # ── Styling (domain-specific overrides) ──────────────────────────

    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=7)
        ax.set_xlabel('X (mm)', color=TEXT_COLOR, fontsize=8)
        ax.set_ylabel('Y (mm)', color=TEXT_COLOR, fontsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor('#444466')
        ax.grid(True, color=GRID_COLOR, linewidth=0.4, linestyle='-')
        ax.set_aspect('equal')

    # ── Coordinate transform (Y inverted for KiCad footprints) ───────

    def _transform_display_coords(self, x, y):
        """KiCad footprints use Y-down; negate Y for the status bar."""
        return x, -y

    # ── Rendering ────────────────────────────────────────────────────

    def render(self, data: dict):
        """Limpa e redesenha o footprint a partir dos dados parseados."""
        self.ax.clear()
        self._style_axes()

        pads    = data.get('pads', [])
        lines   = data.get('lines', [])
        arcs    = data.get('arcs', [])
        circles = data.get('circles', [])
        polys   = data.get('polys', [])
        name    = data.get('name', '')

        # --- Linhas fp_line ---
        for line in lines:
            layer = line['layer']
            if not self._layer_vis.get(layer, True):
                continue
            style = LAYER_STYLE.get(layer, {'color': '#FFFFFF', 'lw': 0.6, 'ls': '-', 'zorder': 1})
            self.ax.plot(
                [line['x1'], line['x2']], [-line['y1'], -line['y2']],
                color=style['color'], linewidth=style['lw'],
                linestyle=style['ls'], zorder=style['zorder'],
                solid_capstyle='round',
            )

        # --- Arcos fp_arc ---
        for arc in arcs:
            layer = arc['layer']
            if not self._layer_vis.get(layer, True):
                continue
            style = LAYER_STYLE.get(layer, {'color': '#FFFFFF', 'lw': 0.6, 'zorder': 1})
            patch = Arc(
                (arc['cx'], -arc['cy']),
                width=arc['r']*2, height=arc['r']*2,
                angle=0,
                theta1=min(arc['a1'], arc['a2']),
                theta2=max(arc['a1'], arc['a2']),
                color=style['color'],
                linewidth=style['lw'],
                zorder=style.get('zorder', 2),
            )
            self.ax.add_patch(patch)

        # --- Circulos fp_circle ---
        for circ in circles:
            layer = circ['layer']
            if not self._layer_vis.get(layer, True):
                continue
            style = LAYER_STYLE.get(layer, {'color': '#FFFFFF', 'lw': 0.6, 'zorder': 1})
            patch = Circle(
                (circ['cx'], -circ['cy']), circ['r'],
                fill=False,
                edgecolor=style['color'],
                linewidth=style['lw'],
                linestyle=style.get('ls', '-'),
                zorder=style.get('zorder', 2),
            )
            self.ax.add_patch(patch)

        # --- Poligonos fp_poly ---
        for poly in polys:
            layer = poly['layer']
            if not self._layer_vis.get(layer, True):
                continue
            style = LAYER_STYLE.get(layer, {'color': '#FFFFFF', 'lw': 0.6, 'zorder': 1})
            pts_inv = [(x, -y) for x, y in poly['pts']]
            patch = Polygon(
                pts_inv, closed=True,
                fill=False,
                edgecolor=style['color'],
                linewidth=style['lw'],
                zorder=style.get('zorder', 2),
            )
            self.ax.add_patch(patch)

        # --- Pads ---
        show_pads = self._layer_vis.get('Pads', True)
        show_fcu  = self._layer_vis.get('F.Cu', True)
        show_pin1 = self._layer_vis.get('Pin 1', True)

        tht_count = 0
        for pad in pads:
            num    = pad['num']
            x, y   = pad['x'], pad['y']
            w, h   = pad['w'], pad['h']
            shape  = pad.get('shape', 'smd_rect')
            drill  = pad.get('drill', 0)
            is_p1  = (num == '1')

            # Skip entire pad if Pads layer is off
            if not show_pads:
                if shape.startswith('tht'):
                    tht_count += 1
                continue

            # Skip F.Cu copper drawing if layer is off
            if not show_fcu and not is_p1:
                if shape.startswith('tht'):
                    tht_count += 1
                continue

            # Skip pin-1 highlight if Pin 1 layer is off (draw as normal pad)
            use_pin1_color = is_p1 and show_pin1
            fc_smd = PIN1_FACECOLOR if use_pin1_color else PAD_FACECOLOR
            fc_tht = '#7CFC00' if use_pin1_color else PAD_FACECOLOR

            if shape == 'smd_rect':
                # Pad SMD retangular
                rx = x - w / 2
                ry = -y - h / 2
                self.ax.add_patch(FancyBboxPatch(
                    (rx, ry), w, h, boxstyle='square,pad=0',
                    facecolor=fc_smd, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))

            elif shape == 'smd_roundrect':
                # Pad SMD roundrect — cantos arredondados
                rx = x - w / 2
                ry = -y - h / 2
                rpad = min(w, h) * 0.25  # raio proporcional
                self.ax.add_patch(FancyBboxPatch(
                    (rx + rpad, ry + rpad), w - 2*rpad, h - 2*rpad,
                    boxstyle=f'round,pad={rpad}',
                    facecolor=fc_smd, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))

            elif shape == 'smd_oval':
                # Pad SMD oval — elipse
                self.ax.add_patch(Ellipse(
                    (x, -y), w, h,
                    facecolor=fc_smd, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))

            elif shape == 'smd_circle':
                # Pad SMD circular
                self.ax.add_patch(Circle(
                    (x, -y), w / 2,
                    facecolor=fc_smd, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))

            elif shape == 'tht_circle':
                # Pad PTH circular: anel de cobre + furo central
                tht_count += 1
                # Anel exterior (cobre)
                self.ax.add_patch(Circle(
                    (x, -y), w / 2,
                    facecolor=fc_tht, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))
                # Furo (drill hole)
                if drill > 0:
                    self.ax.add_patch(Circle(
                        (x, -y), drill / 2,
                        facecolor=BG_COLOR, edgecolor='#AAAACC',
                        linewidth=0.5, alpha=1.0, zorder=6))

            elif shape == 'tht_rect':
                # Pad PTH retangular (pino 1): quadrado de cobre + furo circular
                tht_count += 1
                rx = x - w / 2
                ry = -y - h / 2
                self.ax.add_patch(FancyBboxPatch(
                    (rx, ry), w, h, boxstyle='square,pad=0',
                    facecolor=fc_tht, edgecolor=PAD_EDGECOLOR,
                    linewidth=0.8, alpha=PAD_ALPHA, zorder=5))
                # Furo circular no centro
                if drill > 0:
                    self.ax.add_patch(Circle(
                        (x, -y), drill / 2,
                        facecolor=BG_COLOR, edgecolor='#AAAACC',
                        linewidth=0.5, alpha=1.0, zorder=6))

            # Numero do pad
            fs = 4.5 if len(str(num)) <= 2 else 3.5
            self.ax.text(
                x, -y, str(num),
                ha='center', va='center',
                fontsize=fs, color='white', fontweight='bold',
                zorder=7,
                path_effects=[pe.withStroke(linewidth=1, foreground='black')],
            )

        # --- Legenda ---
        legend_elements = [
            Line2D([0],[0], color=PAD_FACECOLOR,      lw=6,   label='F.Cu (SMD)'),
            Line2D([0],[0], color=PAD_FACECOLOR,      lw=6,   label='F.Cu (THT)',
                   markerfacecolor=BG_COLOR, marker='o', markersize=5),
            Line2D([0],[0], color=PIN1_FACECOLOR,     lw=6,   label='Pin 1'),
            Line2D([0],[0], color='#FFD700',          lw=1.5, label='F.SilkS'),
            Line2D([0],[0], color='#4FC3F7',          lw=1.2, label='F.Fab'),
            Line2D([0],[0], color='#FF9800', ls='--', lw=1,   label='F.CrtYd'),
        ]
        self.ax.legend(
            handles=legend_elements,
            loc='upper center', bbox_to_anchor=(0.5, -0.06),
            bbox_transform=self.ax.transAxes,
            ncol=6, fontsize=7,
            facecolor='#2D2D4E', edgecolor='#555577',
            labelcolor=TEXT_COLOR, handlelength=1.8,
            handleheight=1.0, borderpad=0.6,
            columnspacing=0.8, framealpha=0.9,
        )

        # --- Titulo ---
        n_tht = tht_count
        n_smd = sum(1 for p in pads if p.get('shape','smd_rect').startswith('smd_'))
        tipo_info = f"{n_smd} SMD" if n_tht == 0 else (f"{n_tht} PTH" if n_smd == 0 else f"{n_smd} SMD + {n_tht} PTH")
        self.ax.set_title(
            f'Footprint 2D  |  {name}  |  {len(pads)} pads ({tipo_info})',
            color=TEXT_COLOR, fontsize=9, pad=6,
        )

        # Auto-zoom com margem
        self.ax.autoscale()
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        mx = max((x1 - x0) * 0.08, 0.5)
        my = max((y1 - y0) * 0.08, 0.5)
        self.ax.set_xlim(x0 - mx, x1 + mx)
        self.ax.set_ylim(y0 - my, y1 + my)
        self._full_xlim = self.ax.get_xlim()
        self._full_ylim = self.ax.get_ylim()

        self.fig.canvas.draw_idle()


# =============================================================================
# Widget principal: FootprintViewer2D
# =============================================================================
class FootprintViewer2D(QWidget):
    """
    Widget completo com:
    - Barra de status (arquivo, pad count)
    - Canvas matplotlib com footprint renderizado
    - Barra de ferramentas matplotlib (zoom, pan, salvar)
    - QFileSystemWatcher para auto-reload
    """

    sigFileChanged = pyqtSignal(str)   # emitido quando o arquivo é recarregado

    def __init__(self, filepath: str = '', parent=None):
        super().__init__(parent)
        self._filepath = filepath
        self._watcher  = QFileSystemWatcher(self)

        # Measurement tool state
        self._measure_mode = False
        self._measure_point_a = None      # (x, y) in data coords
        self._measure_artists = []        # matplotlib artists to clean up
        self._measure_cid = None          # matplotlib event connection id

        self._setup_ui()
        self._connect_signals()
        if filepath and os.path.isfile(filepath):
            self._add_to_watcher(filepath)
            self.reload_file()
        else:
            self._show_placeholder()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de status superior
        self.status_bar = QLabel('  Aguardando geração do footprint...  ')
        self.status_bar.setStyleSheet(
            'background:#12122A; color:#888AAA; font-size:11px; padding:4px 8px;'
        )
        self.status_bar.setFont(QFont('Consolas', 9))
        layout.addWidget(self.status_bar)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('background:#333355;')
        layout.addWidget(sep)

        # Canvas matplotlib
        self.canvas = FootprintCanvas(self)
        layout.addWidget(self.canvas)

        # Overlay "Gerando..." — hidden by default
        self._overlay = QLabel('⏳  Gerando...', self.canvas)
        self._overlay.setAlignment(Qt.AlignCenter)
        self._overlay.setStyleSheet(
            'background: rgba(30,30,46,200); color: #89B4FA; '
            'font-size: 16px; padding: 10px 20px; border-radius: 8px;'
        )
        self._overlay.setFixedSize(180, 50)
        self._overlay.hide()

        # Conectar callback de coordenadas: exibe X/Y no status bar
        self.canvas._coord_cb = self._show_coord

        # Barra de ferramentas matplotlib + botao Home customizado
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(0)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet(
            'QToolBar { background:#1A1A2E; border:none; }'  
            'QToolButton { color:#CDD6F4; background:transparent; border:none; padding:3px; border-radius:3px; }'
            'QToolButton:hover { background:#313244; }'
        )
        toolbar_row.addWidget(self.toolbar)

        # Botao Home: volta para a vista completa do footprint
        self.btn_home = QPushButton('⌂  Fit All')
        self.btn_home.setToolTip('Resetar camera para vista completa  (Home)')
        self.btn_home.setStyleSheet(
            'QPushButton { background:#2D2D4E; color:#CDD6F4; border:none;'
            '  padding:4px 10px; border-radius:4px; font-size:11px; }'
            'QPushButton:hover { background:#45475A; }'
            'QPushButton:pressed { background:#585B70; }'
        )
        self.btn_home.clicked.connect(self.canvas.fit_all)

        # ── Layer visibility toggles ──────────────────────────────────
        self._layer_actions = {}
        _layer_toggle_defs = [
            ('F.Cu',    '#FF4444',  'Cobre (F.Cu)'),
            ('F.SilkS', '#FFD700',  'Silkscreen (F.SilkS)'),
            ('F.Fab',   '#4FC3F7',  'Fabrication (F.Fab)'),
            ('F.CrtYd', '#FF00FF',  'Courtyard (F.CrtYd)'),
            ('Pads',    '#C47722',  'Pads'),
            ('Pin 1',   '#7CFC00',  'Marcador Pin 1'),
        ]
        for layer_key, color, tooltip in _layer_toggle_defs:
            # Create 12×12 colored icon
            pix = QPixmap(12, 12)
            pix.fill(QColor(color))
            act = QAction(QIcon(pix), layer_key, self)
            act.setCheckable(True)
            act.setChecked(True)
            act.setToolTip(tooltip)
            act.toggled.connect(lambda checked, k=layer_key: self._on_layer_toggled(k, checked))
            self._layer_actions[layer_key] = act
            toolbar_row.addWidget(self._make_layer_toggle_btn(act))
        toolbar_row.addWidget(self.btn_home)

        # ── Export image button (📷) ──────────────────────────────────
        self.btn_export = QPushButton('📷')
        self.btn_export.setToolTip('Exportar imagem (PNG / SVG / PDF)')
        self.btn_export.setStyleSheet(
            'QPushButton { background:#2D2D4E; color:#CDD6F4; border:none;'
            '  padding:4px 10px; border-radius:4px; font-size:13px; }'
            'QPushButton:hover { background:#45475A; }'
            'QPushButton:pressed { background:#585B70; }'
        )
        self.btn_export.clicked.connect(self._export_image)
        toolbar_row.addWidget(self.btn_export)

        # ── Measurement tool button (📏) ──────────────────────────────
        self.btn_measure = QPushButton('📏')
        self.btn_measure.setToolTip('Ferramenta de medição (clique 2 pontos para medir distância)')
        self.btn_measure.setCheckable(True)
        self.btn_measure.setStyleSheet(
            'QPushButton { background:#2D2D4E; color:#CDD6F4; border:none;'
            '  padding:4px 10px; border-radius:4px; font-size:13px; }'
            'QPushButton:hover { background:#45475A; }'
            'QPushButton:pressed { background:#585B70; }'
            'QPushButton:checked { background:#45475A; border:1px solid #89DCEB; }'
        )
        self.btn_measure.toggled.connect(self._toggle_measure_mode)
        toolbar_row.addWidget(self.btn_measure)

        toolbar_row.addStretch()

        container = QWidget()
        container.setLayout(toolbar_row)
        container.setStyleSheet('background:#1A1A2E;')
        layout.addWidget(container)

        self.setMinimumWidth(300)

    # ------------------------------------------------------------------
    # Layer toggle helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_layer_toggle_btn(action):
        """Create a small styled QPushButton bound to a checkable QAction."""
        btn = QPushButton()
        btn.setText(action.text())
        btn.setIcon(action.icon())
        btn.setCheckable(True)
        btn.setChecked(action.isChecked())
        btn.setToolTip(action.toolTip())
        # Sync button ↔ action
        btn.toggled.connect(action.toggle)
        action.toggled.connect(btn.setChecked)
        btn.setStyleSheet(
            'QPushButton { background:#2D2D4E; color:#CDD6F4; border:none;'
            '  padding:2px 6px; border-radius:3px; font-size:10px; }'
            'QPushButton:hover { background:#45475A; }'
            'QPushButton:checked { background:#45475A; border:1px solid #89DCEB; }'
            'QPushButton:!checked { background:#1A1A2E; color:#555577; }'
        )
        return btn

    def _on_layer_toggled(self, layer_key: str, visible: bool):
        """Toggle a layer and re-render with current data."""
        self.canvas._layer_vis[layer_key] = visible
        self.reload_file()

    def _connect_signals(self):
        self._watcher.fileChanged.connect(self._on_file_changed)

    # ------------------------------------------------------------------
    # Watcher
    # ------------------------------------------------------------------
    def _add_to_watcher(self, path: str):
        if path and path not in self._watcher.files():
            self._watcher.addPath(path)

    def _on_file_changed(self, path: str):
        # Alguns editores deletam e recriam o arquivo → re-adicionar ao watcher
        self._add_to_watcher(path)
        self.reload_file()

    # ------------------------------------------------------------------
    # Reload / render
    # ------------------------------------------------------------------
    def set_file(self, filepath: str):
        """Define um novo arquivo para monitorar."""
        self._filepath = filepath
        self._add_to_watcher(filepath)
        self.reload_file()

    def _show_coord(self, x: float, y: float):
        """Atualiza a barra de status com as coordenadas do cursor."""
        self.status_bar.setText(
            f'  X: {x:+.3f} mm   Y: {y:+.3f} mm  '
            f'|  Scroll: zoom  |  Btn-meio/direito: pan  |  Home: fit all  |  Setas: mover'
        )

    def _center_overlay(self):
        """Center the overlay label on the canvas."""
        cw = self.canvas.width()
        ch = self.canvas.height()
        ow = self._overlay.width()
        oh = self._overlay.height()
        self._overlay.move((cw - ow) // 2, (ch - oh) // 2)

    def reload_file(self, *args):
        """Parseia e redesenha o footprint do arquivo atual."""
        path = self._filepath
        if not path or not os.path.isfile(path):
            self._show_placeholder()
            return

        # Show "Gerando..." overlay
        self._center_overlay()
        self._overlay.show()
        self._overlay.repaint()

        try:
            data = parse_kicad_mod(path)
            self.canvas.render(data)
            pad_count = len(data['pads'])
            fname = os.path.basename(path)
            self.status_bar.setText(
                f'  {fname}  |  {pad_count} pads  |  '
                f'{len(data["lines"])} linhas  |  '
                f'Scroll: zoom centrado no cursor  |  Clique  pan/zoom na toolbar'
            )
            self.status_bar.setStyleSheet(
                'background:#0D2137; color:#4FC3F7; font-size:11px; padding:4px 8px;'
            )
            self.sigFileChanged.emit(path)
        except Exception as e:
            self.status_bar.setText(f'  Erro ao renderizar: {e}')
            self.status_bar.setStyleSheet(
                'background:#2D0000; color:#FF5555; font-size:11px; padding:4px 8px;'
            )
        finally:
            self._overlay.hide()

    def _show_placeholder(self):
        self.canvas.ax.clear()
        self.canvas.ax.set_facecolor(BG_COLOR)
        self.canvas.ax.text(
            0.5, 0.5,
            'Edite o YAML e pressione Ctrl+Enter\npara gerar o footprint',
            ha='center', va='center',
            transform=self.canvas.ax.transAxes,
            color='#666688', fontsize=12,
            style='italic',
        )

        self.canvas.ax.set_xticks([])
        self.canvas.ax.set_yticks([])
        self.canvas.fig.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Export image (PNG / SVG / PDF)
    # ------------------------------------------------------------------
    def _export_image(self):
        """Export the current 2D view as PNG, SVG, or PDF."""
        path, _ = QFileDialog.getSaveFileName(
            self, 'Exportar Imagem', '',
            'PNG (*.png);;SVG (*.svg);;PDF (*.pdf)'
        )
        if path:
            self.canvas.figure.savefig(
                path, dpi=300,
                facecolor='#1A1A2E', bbox_inches='tight'
            )
            self.status_bar.setText(f'  Imagem exportada: {os.path.basename(path)}')
            self.status_bar.setStyleSheet(
                'background:#0D2137; color:#A6E3A1; font-size:11px; padding:4px 8px;'
            )

    # ------------------------------------------------------------------
    # Measurement tool
    # ------------------------------------------------------------------
    def _toggle_measure_mode(self, checked: bool):
        """Toggle measurement mode on/off."""
        self._measure_mode = checked
        if checked:
            self._measure_point_a = None
            self._clear_measurement()
            self._measure_cid = self.canvas.mpl_connect(
                'button_press_event', self._on_measure_click
            )
            self.status_bar.setText(
                '  📏 Modo medição: clique no primeiro ponto (A)'
            )
            self.status_bar.setStyleSheet(
                'background:#1A2D1A; color:#89DCEB; font-size:11px; padding:4px 8px;'
            )
        else:
            if self._measure_cid is not None:
                self.canvas.mpl_disconnect(self._measure_cid)
                self._measure_cid = None
            self._clear_measurement()
            self._measure_point_a = None
            self.reload_file()

    def _on_measure_click(self, event):
        """Handle clicks during measurement mode."""
        if event.inaxes != self.canvas.ax:
            return
        if event.button != 1:  # only left click
            return

        x, y = event.xdata, event.ydata

        if self._measure_point_a is None:
            # First click: store point A
            self._measure_point_a = (x, y)
            marker, = self.canvas.ax.plot(
                x, y, 'o', color='#89DCEB', markersize=6, zorder=20
            )
            self._measure_artists.append(marker)
            self.canvas.draw_idle()
            self.status_bar.setText(
                f'  📏 Ponto A: ({x:+.3f}, {-y:+.3f}) mm  —  clique no ponto B'
            )
        else:
            # Second click: draw measurement
            ax_pt, ay_pt = self._measure_point_a
            bx, by = x, y

            # Distance in mm (data coords = mm)
            dist = math.sqrt((bx - ax_pt)**2 + (by - ay_pt)**2)

            # Draw dashed line
            line, = self.canvas.ax.plot(
                [ax_pt, bx], [ay_pt, by],
                '--', color='#89DCEB', linewidth=1.5, zorder=20
            )
            self._measure_artists.append(line)

            # Draw point B marker
            marker_b, = self.canvas.ax.plot(
                bx, by, 'o', color='#89DCEB', markersize=6, zorder=20
            )
            self._measure_artists.append(marker_b)

            # Label centered on the line
            mid_x = (ax_pt + bx) / 2
            mid_y = (ay_pt + by) / 2
            label = self.canvas.ax.text(
                mid_x, mid_y, f'  {dist:.3f} mm',
                ha='left', va='bottom',
                fontsize=9, color='#FFFFFF', fontweight='bold',
                zorder=21,
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor='#1A1A2E', edgecolor='#89DCEB',
                          alpha=0.9)
            )
            self._measure_artists.append(label)

            self.canvas.draw_idle()
            self.status_bar.setText(
                f'  📏 Distância: {dist:.3f} mm  '
                f'(A: {ax_pt:+.3f},{-ay_pt:+.3f}  →  B: {bx:+.3f},{-by:+.3f})'
            )
            self.status_bar.setStyleSheet(
                'background:#0D2137; color:#89DCEB; font-size:11px; padding:4px 8px;'
            )

            # Reset for next measurement (keep drawing visible)
            self._measure_point_a = None

    def _clear_measurement(self):
        """Remove all measurement artists from the canvas."""
        for artist in self._measure_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._measure_artists.clear()
        self.canvas.draw_idle()

    def keyPressEvent(self, event):
        """Handle Escape to exit measurement mode."""
        if event.key() == Qt.Key_Escape and self._measure_mode:
            self.btn_measure.setChecked(False)  # triggers _toggle_measure_mode(False)
            return
        super().keyPressEvent(event)
