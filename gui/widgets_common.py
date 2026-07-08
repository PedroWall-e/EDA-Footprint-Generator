# -*- coding: utf-8 -*-
"""widgets_common.py — Widgets compartilhados (highlighters, editor com numeração de linhas)."""

from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit, QWidget
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextFormat,
)
from PyQt5.QtCore import Qt, QRect, QRegExp, QSize

__all__ = ["PythonHighlighter", "LineNumberArea", "CodeEditor"]


# =========================================================================
# Syntax Highlighter para Python / CadQuery
# =========================================================================

class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter básico para Python com destaque CadQuery.

    Colours follow the Catppuccin Mocha palette:

    * **Keywords** — ``#89B4FA`` (blue, bold)
    * **CadQuery names** — ``#F5C2E7`` (pink, bold)
    * **Numbers** — ``#FAB387`` (peach)
    * **Strings** — ``#A6E3A1`` (green)
    * **Comments** — ``#6C7086`` (overlay0, italic)

    Parameters
    ----------
    parent : QTextDocument or None
        Document to which the highlighter is attached.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        # --- Keywords Python ---
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#89B4FA"))
        kw_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class",
            "continue", "def", "del", "elif", "else", "except", "False",
            "finally", "for", "from", "global", "if", "import", "in",
            "is", "lambda", "None", "nonlocal", "not", "or", "pass",
            "raise", "return", "True", "try", "while", "with", "yield",
        ]
        for kw in keywords:
            pattern = QRegExp(r"\b" + kw + r"\b")
            self._rules.append((pattern, kw_fmt))

        # --- Funções / nomes CadQuery ---
        cq_fmt = QTextCharFormat()
        cq_fmt.setForeground(QColor("#F5C2E7"))
        cq_fmt.setFontWeight(QFont.Bold)
        cq_names = [
            "cq", "Workplane", "show_object", "Assembly", "Sketch",
            "Vector", "Location", "Color",
        ]
        for name in cq_names:
            pattern = QRegExp(r"\b" + name + r"\b")
            self._rules.append((pattern, cq_fmt))

        # --- Números ---
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#FAB387"))
        self._rules.append((QRegExp(r"\b[0-9]+\.?[0-9]*\b"), num_fmt))

        # --- Strings (aspas simples e duplas) ---
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#A6E3A1"))
        self._rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self._rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # --- Comentários ---
        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#6C7086"))
        self._comment_fmt.setFontItalic(True)

    def highlightBlock(self, text):
        """Apply syntax-highlighting rules to *text* (one block/line)."""
        # Aplicar regras normais
        for pattern, fmt in self._rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

        # Comentários — sobrescreve tudo depois de #
        comment_idx = text.find("#")
        if comment_idx >= 0:
            # Verificar se o # não está dentro de uma string
            in_str = False
            quote_char = None
            for i, ch in enumerate(text[:comment_idx]):
                if ch in ('"', "'") and (i == 0 or text[i - 1] != "\\"):
                    if not in_str:
                        in_str = True
                        quote_char = ch
                    elif ch == quote_char:
                        in_str = False
            if not in_str:
                self.setFormat(comment_idx, len(text) - comment_idx,
                               self._comment_fmt)


# =========================================================================
# Widget de numeração de linhas
# =========================================================================

class LineNumberArea(QWidget):
    """Widget lateral que exibe os números de linha do editor.

    Parameters
    ----------
    editor : CodeEditor
        The :class:`CodeEditor` instance this area belongs to.
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        """Return the preferred width based on the editor's digit count."""
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        """Delegate painting to the editor."""
        self._editor.line_number_area_paint(event)


# =========================================================================
# Editor de texto com numeração de linhas
# =========================================================================

class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit com numeração de linhas integrada.

    Features
    --------
    * Gutter with line numbers (painted by :class:`LineNumberArea`).
    * Current-line highlight using ``#2A2A3D``.
    * Automatic gutter resize on block-count changes.

    .. note::

       Uses ``QTextEdit.ExtraSelection`` (not
       ``QPlainTextEdit.ExtraSelection``) for PyQt5 compatibility.

    Parameters
    ----------
    parent : QWidget or None
        Parent widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_area = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_area_width(0)
        self._highlight_current_line()

    # --- Largura da área de linhas ---

    def line_number_area_width(self):
        """Calculate the pixel width needed for the line-number gutter."""
        digits = max(1, len(str(self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * (digits + 1)
        return space

    def _update_line_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(),
                                   self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event):
        """Reposition the line-number area on resize."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(
            QRect(cr.left(), cr.top(),
                  self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint(self, event):
        """Paint line numbers into the gutter area.

        Called by :meth:`LineNumberArea.paintEvent`.
        """
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor("#181825"))

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                    .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        painter.setFont(self.font())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_num + 1)
                painter.setPen(QColor("#6C7086"))
                painter.drawText(
                    0, top,
                    self._line_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight, number
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1

        painter.end()

    def _highlight_current_line(self):
        """Highlight the line containing the cursor with ``#2A2A3D``."""
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#2A2A3D"))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)
