# -*- coding: utf-8 -*-
"""Splash screen com gradiente escuro desenhado via QPainter.

Não requer imagens externas — tudo é desenhado programaticamente.
"""

try:
    from core.version import __version__
except ImportError:
    __version__ = '3.0.0'

from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QPen, QBrush, QFontMetrics,
)
from PyQt5.QtCore import Qt, QRectF


class SplashScreen(QSplashScreen):
    """Splash screen personalizado com gradiente, título e barra de progresso."""

    # Paleta Catppuccin Mocha
    _BG_TOP    = QColor(24, 24, 37)     # #181825  Mantle
    _BG_BOTTOM = QColor(30, 30, 46)     # #1E1E2E  Base
    _ACCENT    = QColor(137, 180, 250)  # #89B4FA  Blue
    _GREEN     = QColor(166, 227, 161)  # #A6E3A1  Green
    _TEXT      = QColor(205, 214, 244)  # #CDD6F4  Text
    _SUBTEXT   = QColor(166, 173, 200)  # #A6ADC8  Subtext0
    _SURFACE   = QColor(49, 50, 68)     # #313244  Surface0
    _OVERLAY   = QColor(69, 71, 90)     # #45475A  Overlay0

    _WIDTH  = 500
    _HEIGHT = 300

    def __init__(self):
        # Criar pixmap base
        pixmap = QPixmap(self._WIDTH, self._HEIGHT)
        pixmap.fill(Qt.transparent)
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self._message = 'Inicializando…'
        self._percent = 0
        self._draw()

    # -----------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------
    def set_progress(self, message: str, percent: int):
        """Atualiza mensagem e percentual da barra de progresso."""
        self._message = message
        self._percent = max(0, min(100, percent))
        self._draw()
        # Garantir repaint
        self.repaint()
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    # -----------------------------------------------------------------
    # Desenho
    # -----------------------------------------------------------------
    def _draw(self):
        """Redesenha o pixmap inteiro."""
        pm = QPixmap(self._WIDTH, self._HEIGHT)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        W, H = self._WIDTH, self._HEIGHT
        margin = 0

        # --- Fundo com gradiente e borda arredondada ---
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, self._BG_TOP)
        grad.setColorAt(1.0, self._BG_BOTTOM)
        p.setBrush(QBrush(grad))
        p.setPen(QPen(self._OVERLAY, 1.5))
        p.drawRoundedRect(QRectF(margin, margin, W - 2*margin, H - 2*margin), 12, 12)

        # --- Linha decorativa no topo ---
        accent_grad = QLinearGradient(40, 0, W - 40, 0)
        accent_grad.setColorAt(0.0, QColor(137, 180, 250, 0))
        accent_grad.setColorAt(0.3, self._ACCENT)
        accent_grad.setColorAt(0.7, self._GREEN)
        accent_grad.setColorAt(1.0, QColor(166, 227, 161, 0))
        p.setPen(QPen(QBrush(accent_grad), 2.5))
        p.drawLine(40, 8, W - 40, 8)

        # --- Ícone / Logo placeholder ---
        # Desenhar um hexágono estilizado como logo
        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
        cx, cy, r = W / 2, 75, 28
        import math
        hex_points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            hex_points.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
        hex_poly = QPolygonF(hex_points)

        hex_grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        hex_grad.setColorAt(0.0, self._ACCENT)
        hex_grad.setColorAt(1.0, self._GREEN)
        p.setBrush(QBrush(hex_grad))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawPolygon(hex_poly)

        # Texto dentro do hexágono
        p.setPen(QPen(self._BG_TOP))
        font_logo = QFont('Consolas', 14, QFont.Bold)
        p.setFont(font_logo)
        p.drawText(QRectF(cx - r, cy - r, 2*r, 2*r), Qt.AlignCenter, 'CAD')

        # --- Título ---
        font_title = QFont('Segoe UI', 16, QFont.Bold)
        p.setFont(font_title)
        p.setPen(QPen(self._TEXT))
        p.drawText(QRectF(0, 115, W, 30), Qt.AlignCenter, 'Plataforma CAM-CAD Data Frontier')

        # --- Versão ---
        font_ver = QFont('Segoe UI', 10)
        p.setFont(font_ver)
        p.setPen(QPen(self._SUBTEXT))
        p.drawText(QRectF(0, 145, W, 20), Qt.AlignCenter, f'v{__version__}  —  Gerador de Footprints KiCad')

        # --- Linha separadora ---
        p.setPen(QPen(self._SURFACE, 1))
        p.drawLine(60, 180, W - 60, 180)

        # --- Mensagem de progresso ---
        font_msg = QFont('Segoe UI', 10)
        p.setFont(font_msg)
        p.setPen(QPen(self._SUBTEXT))
        p.drawText(QRectF(40, 195, W - 80, 20), Qt.AlignLeft | Qt.AlignVCenter, self._message)

        # Percentual à direita
        p.drawText(QRectF(40, 195, W - 80, 20), Qt.AlignRight | Qt.AlignVCenter, f'{self._percent}%')

        # --- Barra de progresso ---
        bar_x, bar_y, bar_w, bar_h = 40, 222, W - 80, 6
        # Fundo da barra
        p.setBrush(QBrush(self._SURFACE))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        # Preenchimento
        if self._percent > 0:
            fill_w = bar_w * (self._percent / 100.0)
            bar_grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            bar_grad.setColorAt(0.0, self._ACCENT)
            bar_grad.setColorAt(1.0, self._GREEN)
            p.setBrush(QBrush(bar_grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)

        # --- Créditos ---
        font_credit = QFont('Segoe UI', 8)
        p.setFont(font_credit)
        p.setPen(QPen(QColor(108, 112, 134)))  # Overlay1
        p.drawText(QRectF(0, H - 35, W, 20), Qt.AlignCenter, 'CAD-Data-Frontier  •  Powered by KiCad + CadQuery + PyQt5')

        p.end()
        self.setPixmap(pm)
