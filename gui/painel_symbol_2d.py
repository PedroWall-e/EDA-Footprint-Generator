# =============================================================================
# painel_symbol_2d.py
# Widget Qt com visualizador 2D de símbolos KiCad (.kicad_sym) usando matplotlib.
# Parseia o arquivo .kicad_sym e renderiza retângulos, polylines, círculos e pinos.
# Sistema de coordenadas KiCad símbolo: Y cresce para CIMA (igual ao matplotlib padrão).
# Auto-atualiza via QFileSystemWatcher quando o arquivo muda.
# =============================================================================

import re
import os
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, QFileSystemWatcher, pyqtSignal
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch, Arc
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection

from gui.canvas_base import InteractiveCanvas


# =============================================================================
# Paleta de cores (tema escuro)
# =============================================================================
BG_COLOR       = '#1A1A2E'
GRID_COLOR     = '#2D2D4E'
TEXT_COLOR     = '#E0E0E0'
BODY_EDGE      = '#4FC3F7'      # azul — contorno do corpo
BODY_FILL      = '#1E2D3E'      # azul-escuro — preenchimento background
POLY_COLOR     = '#4FC3F7'      # azul — polylines gerais
FILL_COLOR     = '#4FC3F7'      # azul — preenchimento 'filled'
PIN_COLOR      = '#FFD700'      # amarelo — linha do stub
PIN_NUM_COLOR  = '#FF9800'      # laranja — número do pino
PIN_NAME_COLOR = '#A5D6A7'      # verde-claro — nome do pino
REF_COLOR      = '#EF9A9A'      # rosa — referência
VAL_COLOR      = '#80CBC4'      # teal — valor
CIRCLE_COLOR   = '#4FC3F7'      # círculos (transistor body)
ARC_COLOR      = '#4FC3F7'      # arcos


# =============================================================================
# Parser do .kicad_sym
# =============================================================================

def _xy_pairs(text: str) -> list:
    """Extrai todas as coordenadas (xy x y) de um bloco de texto."""
    return [
        (float(x), float(y))
        for x, y in re.findall(r'\(xy\s+([\-\d.]+)\s+([\-\d.]+)\)', text)
    ]


def parse_kicad_sym(filepath: str) -> dict:
    """
    Parseia um arquivo .kicad_sym e retorna dicionário com:
      name       : str
      rects      : list of {x1, y1, x2, y2, fill}
      polys      : list of {pts:[(x,y),...], fill}
      circles    : list of {cx, cy, r, fill}
      arcs       : list of {cx, cy, r, a1, a2, fill}
      pins       : list of {x, y, angle, length, name, number, ptype}
      properties : list of {key, value, x, y, angle, fontsize, hidden}
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return {'name': 'Erro', 'rects': [], 'polys': [], 'circles': [],
                'arcs': [], 'pins': [], 'properties': []}

    # Nome do símbolo (primeiro ocorrência sem sufixo _0_1 / _1_1)
    names = re.findall(r'\(symbol\s+"([^"]+)"', content)
    name = next((n for n in names if not n.endswith('_0_1') and
                                     not n.endswith('_1_1')), 'Desconhecido')

    # Retângulos
    rects = []
    for m in re.finditer(
        r'\(rectangle\s*\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)'
        r'.*?\(fill\s*\(type\s+(\w+)\)\)',
        content, re.DOTALL
    ):
        rects.append({
            'x1': float(m.group(1)), 'y1': float(m.group(2)),
            'x2': float(m.group(3)), 'y2': float(m.group(4)),
            'fill': m.group(5),
        })

    # Polylines — captura pts + fill
    polys = []
    for m in re.finditer(
        r'\(polyline\s*(.*?)\(fill\s*\(type\s+(\w+)\)\)',
        content, re.DOTALL
    ):
        pts = _xy_pairs(m.group(1))
        if pts:
            polys.append({'pts': pts, 'fill': m.group(2)})

    # Círculos
    circles = []
    for m in re.finditer(
        r'\(circle\s*\(center\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(radius\s+([\-\d.]+)\)'
        r'.*?\(fill\s*\(type\s+(\w+)\)\)',
        content, re.DOTALL
    ):
        circles.append({
            'cx': float(m.group(1)), 'cy': float(m.group(2)),
            'r':  float(m.group(3)), 'fill': m.group(4),
        })

    # Arcos — KiCad 7+ formato: (arc (start X Y) (mid X Y) (end X Y))
    arcs = []
    for m in re.finditer(
        r'\(arc\s*\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(mid\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)'
        r'.*?\(fill\s*\(type\s+(\w+)\)\)',
        content, re.DOTALL
    ):
        sx, sy = float(m.group(1)), float(m.group(2))
        mx, my = float(m.group(3)), float(m.group(4))
        ex, ey = float(m.group(5)), float(m.group(6))
        fill = m.group(7)
        # Calcular centro e raio a partir de 3 pontos (start, mid, end)
        ax_v = sx - mx;  ay_v = sy - my
        bx_v = ex - mx;  by_v = ey - my
        D = 2.0 * (ax_v * by_v - ay_v * bx_v)
        if abs(D) > 1e-10:
            ux = (by_v * (ax_v**2 + ay_v**2) - ay_v * (bx_v**2 + by_v**2)) / D
            uy = (ax_v * (bx_v**2 + by_v**2) - bx_v * (ax_v**2 + ay_v**2)) / D
            cx = mx + ux;  cy = my + uy
            r = math.hypot(sx - cx, sy - cy)
            a_start = math.degrees(math.atan2(sy - cy, sx - cx))
            a_mid   = math.degrees(math.atan2(my - cy, mx - cx))
            a_end   = math.degrees(math.atan2(ey - cy, ex - cx))
            # Garantir que o arco passa pelo ponto mid
            def _normalize(a):
                return a % 360.0
            a_s = _normalize(a_start)
            a_m = _normalize(a_mid)
            a_e = _normalize(a_end)
            # Determinar direção: se mid está entre start→end no sentido anti-horário
            def _arc_contains(a1, a2, am):
                """Checa se am está no arco a1→a2 anti-horário."""
                if a1 <= a2:
                    return a1 <= am <= a2
                else:
                    return am >= a1 or am <= a2
            if _arc_contains(a_s, a_e, a_m):
                arcs.append({'cx': cx, 'cy': cy, 'r': r,
                             'a1': a_s, 'a2': a_e, 'fill': fill})
            else:
                arcs.append({'cx': cx, 'cy': cy, 'r': r,
                             'a1': a_e, 'a2': a_s, 'fill': fill})

    # Arcos — KiCad 5/6 formato: (arc (start X Y) (end X Y) (angle N))
    for m in re.finditer(
        r'\(arc\s*\(start\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(end\s+([\-\d.]+)\s+([\-\d.]+)\)\s*'
        r'\(angle\s+([\-\d.]+)\)'
        r'.*?\(fill\s*\(type\s+(\w+)\)\)',
        content, re.DOTALL
    ):
        # No KiCad 5/6 symbol arcs: start=center, end=endpoint, angle=sweep
        cx, cy = float(m.group(1)), float(m.group(2))
        ex, ey = float(m.group(3)), float(m.group(4))
        angle_sweep = float(m.group(5))
        fill = m.group(6)
        r = math.hypot(ex - cx, ey - cy)
        a1 = math.degrees(math.atan2(ey - cy, ex - cx))
        a2 = a1 + angle_sweep
        arcs.append({'cx': cx, 'cy': cy, 'r': r,
                     'a1': a1, 'a2': a2, 'fill': fill})

    # Pinos
    pins = []
    for m in re.finditer(
        r'\(pin\s+(\w+)\s+(\w+)\s*'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)\s+(\d+)\)\s*'
        r'\(length\s+([\-\d.]+)\).*?'
        r'\(name\s+"([^"]*)".*?'
        r'\(number\s+"([^"]*)"',
        content, re.DOTALL
    ):
        pins.append({
            'ptype':  m.group(1),
            'style':  m.group(2),
            'x':      float(m.group(3)),
            'y':      float(m.group(4)),
            'angle':  int(m.group(5)),
            'length': float(m.group(6)),
            'name':   m.group(7),
            'number': m.group(8),
        })

    # Properties (Reference, Value) — extrair posição e texto
    properties = []
    for m in re.finditer(
        r'\(property\s+"(Reference|Value)"\s+"([^"]*)"\s*'
        r'\(at\s+([\-\d.]+)\s+([\-\d.]+)(?:\s+([\-\d.]+))?\)',
        content, re.DOTALL
    ):
        key = m.group(1)
        value = m.group(2)
        px, py = float(m.group(3)), float(m.group(4))
        angle = float(m.group(5)) if m.group(5) else 0.0
        # Verificar se está oculto (hide) — procurar "hide" logo após o property
        # Capturar um trecho do conteúdo após o match para verificar 'hide'
        end_pos = m.end()
        snippet = content[end_pos:end_pos+200]
        hidden = bool(re.search(r'\bhide\b', snippet))
        properties.append({
            'key': key, 'value': value,
            'x': px, 'y': py, 'angle': angle,
            'hidden': hidden,
        })

    return {'name': name, 'rects': rects, 'polys': polys,
            'circles': circles, 'arcs': arcs, 'pins': pins,
            'properties': properties}


# =============================================================================
# Canvas matplotlib
# =============================================================================

class SymbolCanvas(InteractiveCanvas):
    """Canvas matplotlib com tema escuro para renderizar o símbolo.

    Inherits scroll-zoom, middle/right-button pan, keyboard navigation,
    and fit_all from :class:`InteractiveCanvas`.  Only rendering and
    domain-specific styling are defined here.
    """

    def __init__(self, parent=None):
        super().__init__(
            parent,
            xlabel="X (mm)",
            ylabel="Y (mm)",
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ── Styling (domain-specific overrides) ──────────────────────────

    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=7)
        ax.set_xlabel('X (mm)', color=TEXT_COLOR, fontsize=8)
        ax.set_ylabel('Y (mm)', color=TEXT_COLOR, fontsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor('#444466')
        ax.grid(True, color=GRID_COLOR, linewidth=0.4)
        ax.set_aspect('equal')

    # ── Rendering ────────────────────────────────────────────────────

    def render(self, data: dict):
        """Limpa e redesenha o símbolo a partir dos dados parseados."""
        self.ax.clear()
        self._style_axes()

        rects      = data.get('rects', [])
        polys      = data.get('polys', [])
        circles    = data.get('circles', [])
        arcs       = data.get('arcs', [])
        pins       = data.get('pins', [])
        props      = data.get('properties', [])
        name       = data.get('name', '')

        # ── Retângulos ────────────────────────────────────────────────
        for r in rects:
            x_min = min(r['x1'], r['x2'])
            y_min = min(r['y1'], r['y2'])
            w = abs(r['x2'] - r['x1'])
            h = abs(r['y2'] - r['y1'])
            fc = BODY_FILL if r['fill'] == 'background' else \
                 (FILL_COLOR if r['fill'] == 'filled' else 'none')
            rect_patch = Rectangle(
                (x_min, y_min), w, h,
                facecolor=fc, edgecolor=BODY_EDGE,
                linewidth=1.2, zorder=2
            )
            self.ax.add_patch(rect_patch)

        # ── Polylines ─────────────────────────────────────────────────
        for poly in polys:
            pts = poly['pts']
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            
            fill_type = poly.get('fill', 'none')
            fc = BODY_FILL if fill_type == 'background' else \
                 (FILL_COLOR if fill_type == 'filled' else 'none')
                 
            if fill_type in ('filled', 'background') and pts[0] == pts[-1]:
                # Polígono fechado preenchido
                self.ax.fill(xs, ys, facecolor=fc, edgecolor=POLY_COLOR,
                             linewidth=1.2, zorder=3)
            else:
                self.ax.plot(xs, ys, color=POLY_COLOR, linewidth=1.2,
                             solid_capstyle='round', zorder=3)

        # ── Círculos ──────────────────────────────────────────────────
        for c in circles:
            fc = BODY_FILL if c['fill'] == 'background' else \
                 (FILL_COLOR if c['fill'] == 'filled' else 'none')
            circ = Circle((c['cx'], c['cy']), c['r'],
                          facecolor=fc, edgecolor=CIRCLE_COLOR,
                          linewidth=1.2, zorder=2)
            self.ax.add_patch(circ)

        # ── Arcos ─────────────────────────────────────────────────────
        for a in arcs:
            arc_patch = Arc(
                (a['cx'], a['cy']),
                width=a['r'] * 2, height=a['r'] * 2,
                angle=0,
                theta1=min(a['a1'], a['a2']),
                theta2=max(a['a1'], a['a2']),
                color=ARC_COLOR,
                linewidth=1.2, zorder=3,
            )
            self.ax.add_patch(arc_patch)

        # ── Pinos ─────────────────────────────────────────────────────
        for pin in pins:
            x0, y0   = pin['x'], pin['y']
            angle_rad = math.radians(pin['angle'])
            dx = math.cos(angle_rad)
            dy = math.sin(angle_rad)
            length = pin['length']

            # Stub do pino (fio externo → corpo)
            x1 = x0 + dx * length
            y1 = y0 + dy * length
            self.ax.plot([x0, x1], [y0, y1],
                         color=PIN_COLOR, linewidth=1.0, zorder=4)

            # Ponto de conexão externo
            self.ax.plot(x0, y0, 'o', color=PIN_COLOR,
                         markersize=2.5, zorder=5)

            # Número do pino (pequeno, perto do ponto externo)
            num_offset = 0.8
            nx = x0 - dx * num_offset
            ny = y0 - dy * num_offset
            self.ax.text(nx, ny, pin['number'],
                         ha='center', va='center',
                         fontsize=5.5, color=PIN_NUM_COLOR,
                         fontweight='bold', zorder=6)

            # Nome do pino (dentro do corpo, na ponta interna do stub)
            # Só mostra se não for '~' (oculto/anônimo)
            pname = pin['name']
            if pname and pname not in ('~', ''):
                # Posição: 0.5mm além da ponta interna do stub
                label_offset = 0.6
                lx = x1 + dx * label_offset
                ly = y1 + dy * label_offset

                # Alinhamento dependendo da direção
                ha_map = {0: 'left',  90: 'center', 180: 'right', 270: 'center'}
                va_map = {0: 'center', 90: 'bottom', 180: 'center', 270: 'top'}
                ha = ha_map.get(pin['angle'], 'center')
                va = va_map.get(pin['angle'], 'center')

                self.ax.text(lx, ly, pname,
                             ha=ha, va=va,
                             fontsize=5.5, color=PIN_NAME_COLOR,
                             zorder=6)

        # ── Properties (Reference, Value) ─────────────────────────────
        for prop in props:
            if prop.get('hidden', False):
                continue
            color = REF_COLOR if prop['key'] == 'Reference' else VAL_COLOR
            rot = prop.get('angle', 0)
            self.ax.text(
                prop['x'], prop['y'], prop['value'],
                ha='center', va='center',
                fontsize=7, color=color,
                rotation=rot,
                fontweight='bold', zorder=7,
            )

        # ── Título ────────────────────────────────────────────────────
        n_arcs = len(arcs)
        self.ax.set_title(
            f'Simbolo Esquematico  |  {name}  |  {len(pins)} pinos'
            + (f'  |  {n_arcs} arcos' if n_arcs else ''),
            color=TEXT_COLOR, fontsize=9, pad=6
        )

        # ── Legenda de camadas ────────────────────────────────────────
        legend_elements = [
            Line2D([0], [0], color=BODY_EDGE,      lw=1.5, label='Corpo'),
            Line2D([0], [0], color=POLY_COLOR,     lw=1.2, label='Linhas'),
            Line2D([0], [0], color=ARC_COLOR,      lw=1.2, label='Arcos',
                   linestyle='--'),
            Line2D([0], [0], color=PIN_COLOR,      lw=1.0, label='Pinos'),
            Line2D([0], [0], color=PIN_NAME_COLOR, lw=0,
                   marker='_', markersize=10, label='Nomes'),
            Line2D([0], [0], color=REF_COLOR,      lw=0,
                   marker='s', markersize=4, label='Ref'),
            Line2D([0], [0], color=VAL_COLOR,      lw=0,
                   marker='s', markersize=4, label='Val'),
        ]
        self.ax.legend(
            handles=legend_elements, loc='upper right',
            fontsize=6, facecolor='#2D2D4E',
            edgecolor='#444466', labelcolor=TEXT_COLOR,
        )

        # Auto-zoom com margem
        self.ax.autoscale()
        x0l, x1l = self.ax.get_xlim()
        y0l, y1l = self.ax.get_ylim()
        mx = max((x1l - x0l) * 0.12, 1.0)
        my = max((y1l - y0l) * 0.12, 1.0)
        self.ax.set_xlim(x0l - mx, x1l + mx)
        self.ax.set_ylim(y0l - my, y1l + my)
        self._full_xlim = self.ax.get_xlim()
        self._full_ylim = self.ax.get_ylim()

        self.fig.canvas.draw_idle()


# =============================================================================
# Widget principal: SymbolViewer2D
# =============================================================================

class SymbolViewer2D(QWidget):
    """
    Widget com visualizador de símbolo KiCad (.kicad_sym):
    - Barra de status (arquivo, contagem de pinos)
    - Canvas matplotlib com símbolo renderizado
    - Barra de ferramentas matplotlib (zoom, pan, salvar)
    - QFileSystemWatcher para auto-reload
    """

    sigFileChanged = pyqtSignal(str)

    def __init__(self, filepath: str = '', parent=None):
        super().__init__(parent)
        self._filepath = filepath
        self._watcher  = QFileSystemWatcher(self)
        self._setup_ui()
        self._connect_signals()
        if filepath and os.path.isfile(filepath):
            self._watcher.addPath(filepath)
            self.reload_file()
        else:
            self._show_placeholder()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra de status superior
        self.status_bar = QLabel('  Aguardando geração do símbolo...  ')
        self.status_bar.setStyleSheet(
            'background:#12122A; color:#888AAA; font-size:11px; padding:4px 8px;'
        )
        self.status_bar.setFont(QFont('Consolas', 9))
        layout.addWidget(self.status_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('background:#333355;')
        layout.addWidget(sep)

        self.canvas = SymbolCanvas(self)
        layout.addWidget(self.canvas)

        # Conectar callback de coordenadas: exibe X/Y no status bar
        self.canvas._coord_cb = self._show_coord

        # Barra de ferramentas matplotlib + botão Fit All
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(0)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet(
            'QToolBar { background:#1A1A2E; border:none; }'
            'QToolButton { color:#CDD6F4; background:transparent; border:none;'
            '  padding:3px; border-radius:3px; }'
            'QToolButton:hover { background:#313244; }'
        )
        toolbar_row.addWidget(self.toolbar)

        # Botão Fit All: volta para a vista completa do símbolo
        self.btn_home = QPushButton('⌂  Fit All')
        self.btn_home.setToolTip('Resetar câmera para vista completa  (Home)')
        self.btn_home.setStyleSheet(
            'QPushButton { background:#2D2D4E; color:#CDD6F4; border:none;'
            '  padding:4px 10px; border-radius:4px; font-size:11px; }'
            'QPushButton:hover { background:#45475A; }'
            'QPushButton:pressed { background:#585B70; }'
        )
        self.btn_home.clicked.connect(self.canvas.fit_all)
        toolbar_row.addWidget(self.btn_home)
        toolbar_row.addStretch()

        container = QWidget()
        container.setLayout(toolbar_row)
        container.setStyleSheet('background:#1A1A2E;')
        layout.addWidget(container)

        self.setMinimumWidth(300)

    def _connect_signals(self):
        self._watcher.fileChanged.connect(self._on_file_changed)

    # ------------------------------------------------------------------
    def _on_file_changed(self, path: str):
        if path and path not in self._watcher.files():
            self._watcher.addPath(path)
        self.reload_file()

    def set_file(self, filepath: str):
        """Define um novo arquivo para monitorar e renderiza."""
        self._filepath = filepath
        if filepath and filepath not in self._watcher.files():
            self._watcher.addPath(filepath)
        self.reload_file()

    def _show_coord(self, x: float, y: float):
        """Atualiza a barra de status com as coordenadas do cursor."""
        self.status_bar.setText(
            f'  X: {x:+.3f} mm   Y: {y:+.3f} mm  '
            f'|  Scroll: zoom  |  Btn-meio/direito: pan  |  Home: fit all  |  Setas: mover'
        )

    def reload_file(self, *_):
        """Parseia e redesenha o símbolo do arquivo atual."""
        path = self._filepath
        if not path or not os.path.isfile(path):
            self._show_placeholder()
            return

        try:
            data = parse_kicad_sym(path)
            self.canvas.render(data)
            n_pins = len(data['pins'])
            n_arcs = len(data.get('arcs', []))
            fname  = os.path.basename(path)
            self.status_bar.setText(
                f'  {fname}  |  {n_pins} pinos  |  '
                f'{len(data["rects"])} rects  {len(data["polys"])} polys  '
                f'{len(data["circles"])} circles  {n_arcs} arcs'
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

    def _show_placeholder(self):
        self.canvas.ax.clear()
        self.canvas.ax.set_facecolor(BG_COLOR)
        self.canvas.ax.text(
            0.5, 0.5,
            'Edite o YAML e pressione Ctrl+Enter\npara gerar o símbolo',
            ha='center', va='center',
            transform=self.canvas.ax.transAxes,
            color='#666688', fontsize=12, style='italic',
        )
        self.canvas.ax.set_xticks([])
        self.canvas.ax.set_yticks([])
        self.canvas.fig.canvas.draw_idle()
