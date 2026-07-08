# -*- coding: utf-8 -*-
"""
canvas_base.py — Base interactive matplotlib canvas for CAM/CAD viewers.

Provides :class:`InteractiveCanvas`, a ``FigureCanvasQTAgg`` subclass with
cursor-centred zoom, middle/right-button pan, and keyboard navigation
(arrows, Home, +/−).  Intended to be subclassed by domain-specific canvases
(footprint viewer, symbol viewer, etc.) so that interaction behaviour is
defined in one place.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtCore import Qt

__all__ = ["InteractiveCanvas"]

# ── Colour constants (Catppuccin-inspired dark theme) ────────────────────
BG_COLOR: str = "#1A1A2E"
GRID_COLOR: str = "#2D2D4E"
TEXT_COLOR: str = "#E0E0E0"
SPINE_COLOR: str = "#444466"

# ── Interaction tuning ───────────────────────────────────────────────────
_SCROLL_FACTOR: float = 0.88
_PAN_STEP: float = 0.15          # fraction of visible range per arrow key
_ZOOM_IN_HALF: float = 0.44      # half-width factor for keyboard zoom-in
_ZOOM_OUT_HALF: float = 0.57     # half-width factor for keyboard zoom-out


class InteractiveCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas with dark-theme styling and mouse/keyboard navigation.

    Parameters
    ----------
    parent : QWidget or None
        Parent Qt widget.
    xlabel, ylabel : str
        Axis labels (default empty).
    coord_callback : callable or None
        ``cb(x, y)`` called on every mouse-move inside the axes so that an
        external status-bar / label can display live coordinates.
    left, right, top, bottom : float
        ``subplots_adjust`` margins.  Defaults give a comfortable fit for
        most use-cases; override per-consumer as needed.
    """

    def __init__(
        self,
        parent=None,
        *,
        xlabel: str = "",
        ylabel: str = "",
        coord_callback: Optional[Callable[[float, float], None]] = None,
        left: float = 0.10,
        right: float = 0.97,
        top: float = 0.93,
        bottom: float = 0.08,
    ) -> None:
        self.fig = Figure(facecolor=BG_COLOR)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=left, right=right, top=top, bottom=bottom)

        if xlabel:
            self.ax.set_xlabel(xlabel, color=TEXT_COLOR)
        if ylabel:
            self.ax.set_ylabel(ylabel, color=TEXT_COLOR)

        self._style_axes()

        # Coordinate display callback -----------------------------------------
        self._coord_cb = coord_callback

        # Pan state ------------------------------------------------------------
        self._pan_active: bool = False
        self._pan_x0: float = 0.0
        self._pan_y0: float = 0.0
        self._xlim0: Tuple[float, float] = (0.0, 1.0)
        self._ylim0: Tuple[float, float] = (0.0, 1.0)

        # Full-extent limits (set by subclass after drawing content) -----------
        self._full_xlim: Tuple[float, float] = self.ax.get_xlim()
        self._full_ylim: Tuple[float, float] = self.ax.get_ylim()

        # Connect matplotlib events -------------------------------------------
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._on_button_press)
        self.mpl_connect("button_release_event", self._on_button_release)
        self.mpl_connect("motion_notify_event", self._on_motion)

        self.setFocusPolicy(Qt.StrongFocus)

    # ── Styling ──────────────────────────────────────────────────────────

    def _style_axes(self) -> None:
        """Apply the dark colour scheme to the axes."""
        self.ax.set_facecolor(BG_COLOR)
        self.ax.tick_params(colors=TEXT_COLOR, which="both")
        self.ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        self.ax.set_aspect("equal", adjustable="datalim")
        for spine in self.ax.spines.values():
            spine.set_color(SPINE_COLOR)

    # ── Coordinate transform hook ──────────────────────────────────────

    def _transform_display_coords(
        self, x: float, y: float
    ) -> Tuple[float, float]:
        """Transform raw axis coords before passing to the coord callback.

        Subclasses override this to adapt to their coordinate convention.
        For example, the footprint viewer negates Y because KiCad footprints
        use a Y-down system while matplotlib's axis is Y-up.
        """
        return x, y

    # ── Scroll-to-zoom ───────────────────────────────────────────────────

    def _on_scroll(self, event) -> None:
        """Zoom centred on the cursor position."""
        if event.inaxes is not self.ax:
            return
        fator = _SCROLL_FACTOR if event.button == "up" else (1.0 / _SCROLL_FACTOR)
        xdata, ydata = event.xdata, event.ydata
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim([
            xdata + (xlim[0] - xdata) * fator,
            xdata + (xlim[1] - xdata) * fator,
        ])
        self.ax.set_ylim([
            ydata + (ylim[0] - ydata) * fator,
            ydata + (ylim[1] - ydata) * fator,
        ])
        self.fig.canvas.draw_idle()

    # ── Middle / right-button pan ────────────────────────────────────────

    def _on_button_press(self, event) -> None:
        if event.button not in (2, 3):
            return
        if event.inaxes is not self.ax:
            return
        self._pan_active = True
        self._pan_x0 = event.x
        self._pan_y0 = event.y
        self._xlim0 = self.ax.get_xlim()
        self._ylim0 = self.ax.get_ylim()
        self.setCursor(Qt.ClosedHandCursor)

    def _on_button_release(self, event) -> None:
        if event.button in (2, 3):
            self._pan_active = False
            self.setCursor(Qt.ArrowCursor)

    def _on_motion(self, event) -> None:
        # Live coordinate feedback
        if event.inaxes is self.ax and event.xdata is not None:
            if self._coord_cb:
                cx, cy = self._transform_display_coords(
                    event.xdata, event.ydata
                )
                self._coord_cb(cx, cy)
            if not self._pan_active:
                self.setCursor(Qt.OpenHandCursor)
        else:
            if not self._pan_active:
                self.setCursor(Qt.ArrowCursor)

        if not self._pan_active:
            return
        if event.x is None or event.y is None:
            return

        dx_px = event.x - self._pan_x0
        dy_px = event.y - self._pan_y0

        ax_pos = self.ax.get_position()
        fig_w, fig_h = self.fig.get_size_inches()
        dpi = self.fig.dpi
        ax_w_px = ax_pos.width * fig_w * dpi
        ax_h_px = ax_pos.height * fig_h * dpi

        xlim = self._xlim0
        ylim = self._ylim0
        dx_data = -dx_px * (xlim[1] - xlim[0]) / ax_w_px
        dy_data = -dy_px * (ylim[1] - ylim[0]) / ax_h_px

        self.ax.set_xlim(xlim[0] + dx_data, xlim[1] + dx_data)
        self.ax.set_ylim(ylim[0] + dy_data, ylim[1] + dy_data)
        self.fig.canvas.draw_idle()

    # ── Keyboard navigation ─────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:  # noqa: N802 — Qt naming
        key = event.key()
        xlim = list(self.ax.get_xlim())
        ylim = list(self.ax.get_ylim())
        dx = (xlim[1] - xlim[0]) * _PAN_STEP
        dy = (ylim[1] - ylim[0]) * _PAN_STEP

        if key == Qt.Key_Home:
            self.fit_all()
        elif key == Qt.Key_Left:
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.fig.canvas.draw_idle()
        elif key == Qt.Key_Right:
            self.ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
            self.fig.canvas.draw_idle()
        elif key == Qt.Key_Up:
            self.ax.set_ylim(ylim[0] + dy, ylim[1] + dy)
            self.fig.canvas.draw_idle()
        elif key == Qt.Key_Down:
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.fig.canvas.draw_idle()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            cx = (xlim[0] + xlim[1]) / 2
            cy = (ylim[0] + ylim[1]) / 2
            self.ax.set_xlim(
                cx - (xlim[1] - xlim[0]) * _ZOOM_IN_HALF,
                cx + (xlim[1] - xlim[0]) * _ZOOM_IN_HALF,
            )
            self.ax.set_ylim(
                cy - (ylim[1] - ylim[0]) * _ZOOM_IN_HALF,
                cy + (ylim[1] - ylim[0]) * _ZOOM_IN_HALF,
            )
            self.fig.canvas.draw_idle()
        elif key == Qt.Key_Minus:
            cx = (xlim[0] + xlim[1]) / 2
            cy = (ylim[0] + ylim[1]) / 2
            self.ax.set_xlim(
                cx - (xlim[1] - xlim[0]) * _ZOOM_OUT_HALF,
                cx + (xlim[1] - xlim[0]) * _ZOOM_OUT_HALF,
            )
            self.ax.set_ylim(
                cy - (ylim[1] - ylim[0]) * _ZOOM_OUT_HALF,
                cy + (ylim[1] - ylim[0]) * _ZOOM_OUT_HALF,
            )
            self.fig.canvas.draw_idle()
        else:
            super().keyPressEvent(event)

    # ── Fit-all (restore full extent) ────────────────────────────────────

    def fit_all(self) -> None:
        """Restore the viewport to the saved full extent."""
        self.ax.set_xlim(self._full_xlim)
        self.ax.set_ylim(self._full_ylim)
        self.fig.canvas.draw_idle()
