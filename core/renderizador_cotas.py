"""Renderizador de cotas dimensionais estilo CAD para matplotlib.

Desenha réguas com setas, linhas de extensão e texto de dimensão
para footprints em folhas de relatório técnico.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import numpy as np

# Style constants for print (white background)
COTA_COLOR = '#1565C0'        # blue for dimensions
COTA_LINE_WIDTH = 0.6
COTA_FONT_SIZE = 7
COTA_ARROW_STYLE = 'Simple,head_width=3,head_length=3,tail_width=0.3'
EXTENSION_COLOR = '#90CAF9'   # light blue for extension lines
EXTENSION_DASH = (0, (3, 3))  # dotted


class DesenhadorCotas:
    """Desenha cotas dimensionais no matplotlib Axes."""

    def __init__(self, ax, escala=1.0):
        self.ax = ax
        self.escala = escala  # for 1:1 scale calculation

    def cota_horizontal(self, x1, x2, y, offset=1.5, label=None):
        """Draws horizontal dimension line with arrows at both ends.

        Args:
            x1, x2: start and end X coordinates
            y: Y coordinate of the dimension line
            offset: distance from the object to the dimension line
            label: text to show (auto-calculated if None)
        """
        # Draw the dimension value in mm
        dist = abs(x2 - x1)
        if label is None:
            label = f'{dist:.2f} mm'

        y_line = y + offset

        # Extension lines (vertical dashed lines from object to dim line)
        self.ax.plot([x1, x1], [y, y_line + 0.3],
                     color=EXTENSION_COLOR, lw=0.4,
                     linestyle=EXTENSION_DASH, zorder=15)
        self.ax.plot([x2, x2], [y, y_line + 0.3],
                     color=EXTENSION_COLOR, lw=0.4,
                     linestyle=EXTENSION_DASH, zorder=15)

        # Arrow line (left to right)
        arrow = FancyArrowPatch(
            (x1, y_line), (x2, y_line),
            arrowstyle='<->', mutation_scale=8,
            color=COTA_COLOR, lw=COTA_LINE_WIDTH, zorder=16
        )
        self.ax.add_patch(arrow)

        # Text centered on the line
        mid_x = (x1 + x2) / 2
        self.ax.text(mid_x, y_line + 0.25, label,
                     ha='center', va='bottom',
                     fontsize=COTA_FONT_SIZE, color=COTA_COLOR,
                     fontfamily='sans-serif', fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.15',
                               facecolor='white', edgecolor='none', alpha=0.85),
                     zorder=17)

    def cota_vertical(self, y1, y2, x, offset=1.5, label=None):
        """Draws vertical dimension line with arrows."""
        dist = abs(y2 - y1)
        if label is None:
            label = f'{dist:.2f} mm'

        x_line = x + offset

        # Extension lines
        self.ax.plot([x, x_line + 0.3], [y1, y1],
                     color=EXTENSION_COLOR, lw=0.4,
                     linestyle=EXTENSION_DASH, zorder=15)
        self.ax.plot([x, x_line + 0.3], [y2, y2],
                     color=EXTENSION_COLOR, lw=0.4,
                     linestyle=EXTENSION_DASH, zorder=15)

        arrow = FancyArrowPatch(
            (x_line, y1), (x_line, y2),
            arrowstyle='<->', mutation_scale=8,
            color=COTA_COLOR, lw=COTA_LINE_WIDTH, zorder=16
        )
        self.ax.add_patch(arrow)

        mid_y = (y1 + y2) / 2
        self.ax.text(x_line + 0.25, mid_y, label,
                     ha='left', va='center',
                     fontsize=COTA_FONT_SIZE, color=COTA_COLOR,
                     fontfamily='sans-serif', fontweight='bold',
                     rotation=90,
                     bbox=dict(boxstyle='round,pad=0.15',
                               facecolor='white', edgecolor='none', alpha=0.85),
                     zorder=17)

    def cota_pitch(self, x1, y1, x2, y2, offset=0.8, label=None):
        """Draws pitch dimension between two adjacent pads."""
        dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if label is None:
            label = f'pitch {dist:.2f}'

        # Small arrow between two points
        if abs(y2 - y1) < 0.01:  # horizontal
            self.cota_horizontal(x1, x2, y1, offset=offset, label=label)
        elif abs(x2 - x1) < 0.01:  # vertical
            self.cota_vertical(y1, y2, x1, offset=offset, label=label)
        else:
            # Angled - draw direct
            arrow = FancyArrowPatch(
                (x1, y1 - offset), (x2, y2 - offset),
                arrowstyle='<->', mutation_scale=6,
                color=COTA_COLOR, lw=0.5, zorder=16
            )
            self.ax.add_patch(arrow)
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2 - offset
            self.ax.text(mid_x, mid_y - 0.3, label,
                         ha='center', va='top',
                         fontsize=COTA_FONT_SIZE - 1, color=COTA_COLOR,
                         bbox=dict(boxstyle='round,pad=0.1',
                                   facecolor='white', edgecolor='none', alpha=0.85),
                         zorder=17)

    def label_pad(self, x, y, w, h, drill=None):
        """Adds pad size label near a pad."""
        text = f'{w:.1f}\u00d7{h:.1f}'
        if drill:
            text += f'\n\u2300{drill:.1f}'
        self.ax.text(x, y - h / 2 - 0.4, text,
                     ha='center', va='top',
                     fontsize=COTA_FONT_SIZE - 1, color='#616161',
                     fontfamily='sans-serif',
                     zorder=17)

    def escala_bar(self, x, y, length_mm=5.0):
        """Draws a scale bar (reference ruler) at position."""
        # Main bar
        self.ax.plot([x, x + length_mm], [y, y],
                     color='#212121', lw=2, zorder=18)
        # End ticks
        tick_h = 0.4
        self.ax.plot([x, x], [y - tick_h, y + tick_h],
                     color='#212121', lw=1.5, zorder=18)
        self.ax.plot([x + length_mm, x + length_mm], [y - tick_h, y + tick_h],
                     color='#212121', lw=1.5, zorder=18)
        # Middle ticks (1mm intervals)
        for i in range(1, int(length_mm)):
            h = tick_h * 0.6 if i % 5 != 0 else tick_h
            self.ax.plot([x + i, x + i], [y - h, y + h],
                         color='#212121', lw=0.5, zorder=18)
        # Label
        self.ax.text(x + length_mm / 2, y + tick_h + 0.2,
                     f'{length_mm:.0f} mm',
                     ha='center', va='bottom',
                     fontsize=COTA_FONT_SIZE, fontweight='bold',
                     color='#212121', zorder=18)

    def auto_cotas(self, pads, corpo=None):
        """Automatically add dimensions based on pad layout.

        Args:
            pads: list of dicts with keys: x, y, w, h, num, drill (optional)
            corpo: dict with keys: x0, y0, x1, y1 (body bounds)
        """
        if not pads:
            return

        xs = [p['x'] for p in pads]
        ys = [-p['y'] for p in pads]  # Y inverted for display

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Passo de empilhamento das cotas. As cotas "de cima" (pitch e largura
        # do corpo) caem quase na mesma altura numa peça pequena (0402): o texto
        # tem tamanho fixo em pontos e os offsets são em mm, então elas se
        # sobrepõem. O passo proporcional (com piso) garante separação legível
        # tanto num 0402 quanto num DIP.
        span = max(max_x - min_x, max_y - min_y, 1.0)
        step = max(1.3, span * 0.12)

        top = max(max_y, -corpo['y0'] if corpo else max_y,
                  -corpo['y1'] if corpo else max_y)

        # Overall width (abaixo)
        if max_x - min_x > 0.1:
            self.cota_horizontal(min_x, max_x, min_y, offset=-step * 1.4)

        # Overall height (à direita)
        if max_y - min_y > 0.1:
            self.cota_vertical(min_y, max_y, max_x, offset=step * 1.4)

        # Pitch (topo, junto à fileira de pads)
        sorted_by_x = sorted(pads, key=lambda p: (round(-p['y'], 2), p['x']))
        if len(sorted_by_x) >= 2:
            p1 = sorted_by_x[0]
            p2 = sorted_by_x[1]
            dx = abs(p2['x'] - p1['x'])
            dy = abs(p2['y'] - p1['y'])
            if 0.1 < dx < 10 and dy < 0.1:  # horizontal pitch
                self.cota_pitch(p1['x'], -p1['y'], p2['x'], -p2['y'],
                                offset=step, label=f'pitch {dx:.2f}')
            elif 0.1 < dy < 10 and dx < 0.1:  # vertical pitch
                self.cota_pitch(p1['x'], -p1['y'], p2['x'], -p2['y'],
                                offset=step, label=f'pitch {dy:.2f}')

        # Body dimensions if provided — largura empilhada ACIMA do pitch
        if corpo:
            bx0, by0, bx1, by1 = corpo['x0'], -corpo['y0'], corpo['x1'], -corpo['y1']
            bw = abs(bx1 - bx0)
            bh = abs(by1 - by0)
            if bw > 0.1:
                self.cota_horizontal(bx0, bx1, top, offset=step * 2.4,
                                     label=f'corpo {bw:.1f}')
            if bh > 0.1:
                self.cota_vertical(min(by0, by1), max(by0, by1), min(bx0, bx1),
                                   offset=-step * 1.4, label=f'corpo {bh:.1f}')

        # Pad size label on first pad
        if pads:
            p = pads[0]
            self.label_pad(p['x'], -p['y'], p['w'], p['h'],
                           p.get('drill'))

        # Scale bar in bottom-right
        margin = 1.5
        bar_len = 5.0
        if max_x - min_x < 8:
            bar_len = 2.0
        elif max_x - min_x < 15:
            bar_len = 5.0
        else:
            bar_len = 10.0
        self.escala_bar(max_x - bar_len + margin, min_y - 3.5, bar_len)
