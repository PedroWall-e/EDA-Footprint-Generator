# =============================================================================
# painel_yaml_editor.py
# Dock widget com editor de YAML integrado ao CQ-Editor.
# Editor com syntax highlighting, numero de linhas (toggle), validacao em
# tempo real e controles de geracao do footprint.
# =============================================================================

import os
import re
import json
import yaml
import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QTextEdit, QFrame, QToolBar, QAction, QFileDialog,
    QMessageBox, QInputDialog, QSizePolicy, QDialog, QDialogButtonBox,
    QLineEdit, QPushButton, QShortcut
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect, QSize
from PyQt5.QtGui import (
    QFont, QColor, QTextCharFormat, QTextFormat, QSyntaxHighlighter,
    QKeySequence, QFontMetrics, QPainter, QTextCursor
)

log = logging.getLogger('painel_yaml_editor')

# =============================================================================
# Syntax Highlighter para YAML
# =============================================================================
class YamlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = self._build_rules()

    @staticmethod
    def _fmt(color, bold=False, italic=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:   fmt.setFontWeight(700)
        if italic: fmt.setFontItalic(True)
        return fmt

    def _build_rules(self):
        return [
            (re.compile(r'#.*$'),                          self._fmt('#6A9955', italic=True)),
            (re.compile(r'^\s*[\w_-]+\s*:'),              self._fmt('#9CDCFE', bold=True)),
            (re.compile(r'"[^"]*"'),                       self._fmt('#CE9178')),
            (re.compile(r"'[^']*'"),                       self._fmt('#CE9178')),
            (re.compile(r'\b\d+\.?\d*\b'),                self._fmt('#B5CEA8')),
            (re.compile(r'\b(true|false|null|yes|no|on|off)\b', re.IGNORECASE),
                                                           self._fmt('#569CD6', bold=True)),
            (re.compile(r'^\s*-\s'),                      self._fmt('#DCDCAA')),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# =============================================================================
# Area de numero de linhas
# =============================================================================
class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor._line_num_width(), 0)

    def paintEvent(self, event):
        self._editor._paint_line_numbers(event)


# =============================================================================
# Editor com suporte a numero de linhas
# =============================================================================
class LineNumberEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_ln  = False
        self._ln_area  = _LineNumberArea(self)
        # Current-line highlight selections (coexist with error/search markers)
        self._curline_selections = []

        self.blockCountChanged.connect(self._update_ln_width)
        self.updateRequest.connect(self._update_ln_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_ln_width(0)
        self._highlight_current_line()

    # ------------------------------------------------------------------
    # Current-line highlighting (Fix 11)
    # ------------------------------------------------------------------
    def _highlight_current_line(self):
        """Highlight the line containing the cursor with a subtle background."""
        self._curline_selections = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor('#2A2A3E'))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            self._curline_selections = [sel]
        self._refresh_extra_selections()

    def _refresh_extra_selections(self):
        """Merge current-line highlight with owner-provided selections (error/search)."""
        owner_sels = getattr(self, '_owner_error_selections', lambda: [])()
        combined = list(self._curline_selections) + list(owner_sels)
        self.setExtraSelections(combined)

    # ------------------------------------------------------------------
    # Smart indent after colon (Fix 10)
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = len(line) - len(line.lstrip())
            # If line ends with ':', add extra indent
            if line.rstrip().endswith(':'):
                indent += 2
            super().keyPressEvent(event)
            cursor = self.textCursor()
            cursor.insertText(' ' * indent)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    def set_line_numbers(self, visible: bool):
        self._show_ln = visible
        self._ln_area.setVisible(visible)
        self._update_ln_width(0)

    def _line_num_width(self):
        if not self._show_ln:
            return 0
        digits = max(1, len(str(self.blockCount())))
        return 8 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_ln_width(self, _=None):
        self.setViewportMargins(self._line_num_width(), 0, 0, 0)

    def _update_ln_area(self, rect, dy):
        if dy:
            self._ln_area.scroll(0, dy)
        else:
            self._ln_area.update(0, rect.y(), self._ln_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_ln_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._ln_area.setGeometry(QRect(cr.left(), cr.top(),
                                        self._line_num_width(), cr.height()))

    def _paint_line_numbers(self, event):
        if not self._show_ln:
            return
        painter = QPainter(self._ln_area)
        painter.fillRect(event.rect(), QColor('#1A1A30'))

        block  = self.firstVisibleBlock()
        num    = block.blockNumber()
        top    = round(self.blockBoundingGeometry(block)
                       .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        h      = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor('#505075'))
                painter.setFont(self.font())
                painter.drawText(0, top,
                                 self._ln_area.width() - 4, h,
                                 Qt.AlignRight, str(num + 1))
            block  = block.next()
            top    = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num   += 1


# =============================================================================
# Barra de Find & Replace
# =============================================================================
class FindReplaceBar(QWidget):
    """Barra de busca e substituição embutida no editor YAML."""

    def __init__(self, editor: LineNumberEditor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._matches: list = []       # lista de posicoes (start, end)
        self._current_idx: int = -1
        self.setVisible(False)

        self._setup_ui()
        self._connect()

    # -----------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------
    def _setup_ui(self):
        self.setStyleSheet(
            'FindReplaceBar {'
            '  background: #1e1e1e;'
            '  border-top: 1px solid #313244;'
            '}'
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(4)

        # --- Campo de busca ---
        self.field_find = QLineEdit()
        self.field_find.setPlaceholderText('Buscar...')
        self.field_find.setMinimumWidth(140)
        self.field_find.setStyleSheet(self._input_style())

        # --- Campo de substituição ---
        self.field_replace = QLineEdit()
        self.field_replace.setPlaceholderText('Substituir por...')
        self.field_replace.setMinimumWidth(140)
        self.field_replace.setStyleSheet(self._input_style())

        # --- Botoes ---
        btn_css = self._btn_style()

        self.btn_prev = QPushButton('▲')
        self.btn_prev.setToolTip('Buscar anterior  (Shift+Enter / Shift+F3)')
        self.btn_prev.setStyleSheet(btn_css)
        self.btn_prev.setFixedWidth(28)

        self.btn_next = QPushButton('▼')
        self.btn_next.setToolTip('Buscar próximo  (Enter / F3)')
        self.btn_next.setStyleSheet(btn_css)
        self.btn_next.setFixedWidth(28)

        self.btn_replace = QPushButton('Substituir')
        self.btn_replace.setToolTip('Substituir ocorrência atual e ir para a próxima')
        self.btn_replace.setStyleSheet(btn_css)

        self.btn_replace_all = QPushButton('Substituir Tudo')
        self.btn_replace_all.setToolTip('Substituir todas as ocorrências')
        self.btn_replace_all.setStyleSheet(btn_css)

        self.btn_close = QPushButton('✕')
        self.btn_close.setToolTip('Fechar barra de busca  (Esc)')
        self.btn_close.setStyleSheet(btn_css)
        self.btn_close.setFixedWidth(28)

        # --- Label de contagem ---
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet('color:#6C7086; font-size:10px; padding:0 4px;')

        # Montar layout
        lay.addWidget(self.field_find)
        lay.addWidget(self.btn_prev)
        lay.addWidget(self.btn_next)
        lay.addWidget(self.lbl_count)
        lay.addWidget(self.field_replace)
        lay.addWidget(self.btn_replace)
        lay.addWidget(self.btn_replace_all)
        lay.addStretch()
        lay.addWidget(self.btn_close)

    @staticmethod
    def _input_style() -> str:
        return (
            'QLineEdit {'
            '  background: #252540;'
            '  color: #CDD6F4;'
            '  border: 1px solid #45475A;'
            '  border-radius: 3px;'
            '  padding: 3px 6px;'
            '  font-family: Consolas;'
            '  font-size: 11px;'
            '}'
            'QLineEdit:focus {'
            '  border-color: #89B4FA;'
            '}'
        )

    @staticmethod
    def _btn_style() -> str:
        return (
            'QPushButton {'
            '  background: #313244;'
            '  color: #CDD6F4;'
            '  border: none;'
            '  border-radius: 3px;'
            '  padding: 3px 10px;'
            '  font-size: 11px;'
            '}'
            'QPushButton:hover {'
            '  background: #45475A;'
            '}'
            'QPushButton:pressed {'
            '  background: #585B70;'
            '}'
        )

    # -----------------------------------------------------------------
    # Signals
    # -----------------------------------------------------------------
    def _connect(self):
        self.field_find.textChanged.connect(self._on_search_changed)
        self.btn_next.clicked.connect(self.find_next)
        self.btn_prev.clicked.connect(self.find_prev)
        self.btn_replace.clicked.connect(self._replace_current)
        self.btn_replace_all.clicked.connect(self._replace_all)
        self.btn_close.clicked.connect(self.hide_bar)

    # -----------------------------------------------------------------
    # Abrir / Fechar
    # -----------------------------------------------------------------
    def show_find(self):
        """Mostra a barra com foco no campo de busca."""
        self.setVisible(True)
        self.field_find.setFocus()
        self.field_find.selectAll()

    def show_replace(self):
        """Mostra a barra com ambos os campos visiveis."""
        self.setVisible(True)
        self.field_replace.setVisible(True)
        self.btn_replace.setVisible(True)
        self.btn_replace_all.setVisible(True)
        self.field_find.setFocus()
        self.field_find.selectAll()

    def hide_bar(self):
        """Esconde a barra e limpa os highlights."""
        self.setVisible(False)
        self._clear_highlights()
        self._matches.clear()
        self._current_idx = -1
        self.lbl_count.clear()
        self._editor.setFocus()

    # -----------------------------------------------------------------
    # Busca
    # -----------------------------------------------------------------
    def _on_search_changed(self, text: str):
        """Chamado sempre que o texto de busca muda — faz live search."""
        self._find_all(text)
        if self._matches:
            self._current_idx = 0
            self._go_to_match(0)
        else:
            self._current_idx = -1
        self._update_count_label()

    def _find_all(self, text: str):
        """Encontra todas as ocorrências (case-insensitive) e aplica highlights."""
        self._clear_highlights()
        self._matches.clear()
        if not text:
            return

        doc = self._editor.document()
        cursor = QTextCursor(doc)
        flags = doc.FindFlags(0)  # case-insensitive por padrão

        while True:
            cursor = doc.find(text, cursor, flags)
            if cursor.isNull():
                break
            self._matches.append((cursor.selectionStart(), cursor.selectionEnd()))

        self._apply_highlights()

    def _apply_highlights(self):
        """Aplica highlight amarelo sutil em todas as ocorrências."""
        selections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor('#3a3d2e'))

        for start, end in self._matches:
            sel = self._editor.ExtraSelection()
            sel.format = QTextCharFormat(fmt)
            cur = QTextCursor(self._editor.document())
            cur.setPosition(start)
            cur.setPosition(end, QTextCursor.KeepAnchor)
            sel.cursor = cur
            selections.append(sel)

        # Merge with error markers from the YamlEditorPanel
        error_sels = getattr(self._editor, '_owner_error_selections', lambda: [])() 
        self._editor.setExtraSelections(error_sels + selections)

    def _clear_highlights(self):
        # Preserve error markers when clearing search highlights
        error_sels = getattr(self._editor, '_owner_error_selections', lambda: [])()
        self._editor.setExtraSelections(error_sels)

    # -----------------------------------------------------------------
    # Navegação
    # -----------------------------------------------------------------
    def find_next(self):
        if not self._matches:
            return
        self._current_idx = (self._current_idx + 1) % len(self._matches)
        self._go_to_match(self._current_idx)
        self._update_count_label()

    def find_prev(self):
        if not self._matches:
            return
        self._current_idx = (self._current_idx - 1) % len(self._matches)
        self._go_to_match(self._current_idx)
        self._update_count_label()

    def _go_to_match(self, idx: int):
        """Move o cursor do editor para o match de indice `idx`."""
        if idx < 0 or idx >= len(self._matches):
            return
        start, end = self._matches[idx]
        cur = self._editor.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        self._editor.setTextCursor(cur)
        self._editor.centerCursor()
        self._highlight_current(idx)

    def _highlight_current(self, active_idx: int):
        """Reaplica highlights com a ocorrência ativa em laranja."""
        selections = []
        fmt_normal = QTextCharFormat()
        fmt_normal.setBackground(QColor('#3a3d2e'))
        fmt_active = QTextCharFormat()
        fmt_active.setBackground(QColor('#6B5B00'))

        for i, (start, end) in enumerate(self._matches):
            sel = self._editor.ExtraSelection()
            sel.format = QTextCharFormat(fmt_active if i == active_idx else fmt_normal)
            cur = QTextCursor(self._editor.document())
            cur.setPosition(start)
            cur.setPosition(end, QTextCursor.KeepAnchor)
            sel.cursor = cur
            selections.append(sel)

        # Merge with error markers from the YamlEditorPanel
        error_sels = getattr(self._editor, '_owner_error_selections', lambda: [])()
        self._editor.setExtraSelections(error_sels + selections)

    def _update_count_label(self):
        n = len(self._matches)
        if n == 0:
            text = self.field_find.text()
            self.lbl_count.setText('Nenhum resultado' if text else '')
        else:
            self.lbl_count.setText(f'{self._current_idx + 1} de {n}')

    # -----------------------------------------------------------------
    # Substituir
    # -----------------------------------------------------------------
    def _replace_current(self):
        """Substitui a ocorrência atual e avança para a próxima."""
        if not self._matches or self._current_idx < 0:
            return
        start, end = self._matches[self._current_idx]
        replacement = self.field_replace.text()

        cur = self._editor.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        cur.insertText(replacement)

        # Refazer busca (posicoes mudaram)
        search_text = self.field_find.text()
        self._find_all(search_text)
        if self._matches:
            self._current_idx = min(self._current_idx, len(self._matches) - 1)
            self._go_to_match(self._current_idx)
        else:
            self._current_idx = -1
        self._update_count_label()

    def _replace_all(self):
        """Substitui todas as ocorrências."""
        search_text = self.field_find.text()
        if not search_text:
            return
        replacement = self.field_replace.text()

        # Refaz busca para garantir lista atualizada
        self._find_all(search_text)
        count = len(self._matches)
        if count == 0:
            return

        # Substituir de trás para frente para manter posicoes
        cur = self._editor.textCursor()
        cur.beginEditBlock()
        for start, end in reversed(self._matches):
            cur.setPosition(start)
            cur.setPosition(end, QTextCursor.KeepAnchor)
            cur.insertText(replacement)
        cur.endEditBlock()

        # Atualizar estado
        self._find_all(search_text)  # deve retornar 0 agora
        self._current_idx = -1
        self._update_count_label()
        self.lbl_count.setText(f'{count} substituída(s)')

    # -----------------------------------------------------------------
    # Teclado interno
    # -----------------------------------------------------------------
    def keyPressEvent(self, event):
        """Atalhos dentro da barra de busca."""
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key_Escape:
            self.hide_bar()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mod & Qt.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            return
        if key == Qt.Key_F3:
            if mod & Qt.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            return

        super().keyPressEvent(event)


# =============================================================================
# Widget Editor YAML
# =============================================================================
class YamlEditorPanel(QWidget):
    """
    Editor YAML completo com syntax highlighting, numero de linhas toggleavel,
    validacao em tempo real e integração com o gerador universal.
    """

    sigGerarRequested    = pyqtSignal()
    sigSaved             = pyqtSignal(str)
    sigFileLoaded        = pyqtSignal(str)   # emite o caminho do arquivo carregado
    sigValidationChanged = pyqtSignal(bool)  # emite True se YAML válido, False se inválido

    # Esqueleto minimo para novo componente
    _NOVO_SKELETON = (
        '# Novo componente\n'
        '# Tipos disponiveis: castellated | diodo_pth | resistor_pth\n'
        '#\n'
        '# Variaveis em modelo_3d_python: cq, show_object, dados, nome, os, math\n'
        '\n'
        'nome: "NomeDoComponente"\n'
        'tipo: "diodo_pth"\n'
        '\n'
        '# --- Preencha os campos do seu componente abaixo ---\n'
        '\n'
        '# modelo_3d_python: |\n'
        '#   corpo = cq.Workplane("XY").cylinder(5.0, 1.5)\n'
        '#   show_object(corpo, name=f"Corpo - {nome}", options={"color": (30,30,30)})\n'
    )

    _TIPOS_YAML = [
        'castellated', 'diodo_pth', 'resistor_pth',
        'ci_dip', 'ci_soic', 'conector_pth',
        'led_pth', 'capacitor_pth', 'transistor_to92', 'crystal_hc49',
    ]

    def __init__(self, yaml_path: str = '', parent=None):
        super().__init__(parent)
        self._yaml_path   = yaml_path
        self._modified    = False
        self._valid_yaml  = True
        self._show_ln     = False
        self._is_auto_saving = False
        self._debounce    = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)

        self._proj_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # root
        self._estado_path = os.path.join(self._proj_dir, '_estado_atual.json')

        # Error marker selections (coexist with find/replace highlights)
        self._error_selections  = []
        self._search_selections = []

        self._setup_ui()
        self._connect_signals()

        # --- Drag & Drop ---
        self.setAcceptDrops(True)
        self._drag_over = False  # flag para feedback visual

        if yaml_path and os.path.isfile(yaml_path):
            self.load_file(yaml_path)

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from PyQt5.QtWidgets import QStyle
        # --- Ações (adicionadas à toolbar principal pela interface_dual.py) ---
        # ▶ Executar (gera preview temporário)
        self.act_gerar = QAction('▶  Executar', self)
        self.act_gerar.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.act_gerar.setShortcut(QKeySequence('Ctrl+Return'))
        self.act_gerar.setToolTip('Gerar preview do footprint 2D, símbolo e modelo 3D  (Ctrl+Enter / F5)')
        self.act_gerar.setEnabled(False)

        # 💾 Salvar Saída (copia preview → saida/ permanente)
        self.act_salvar_saida = QAction('💾  Salvar Saída', self)
        self.act_salvar_saida.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.act_salvar_saida.setShortcut(QKeySequence('Ctrl+Shift+S'))
        self.act_salvar_saida.setToolTip('Salvar os arquivos gerados (.kicad_mod, .kicad_sym, .step) na pasta saida/  (Ctrl+Shift+S)')
        self.act_salvar_saida.setEnabled(False)

        # Salvar (so habilitado com modificacoes)
        self.act_save = QAction('Salvar', self)
        self.act_save.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setToolTip('Salvar YAML  (Ctrl+S) — ativo quando ha modificacoes')
        self.act_save.setEnabled(False)

        # Salvar Como
        self.act_save_as = QAction('Como...', self)
        self.act_save_as.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        self.act_save_as.setToolTip('Salvar o YAML com outro nome')

        # Recarregar do disco
        self.act_reload = QAction('Recarregar', self)
        self.act_reload.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.act_reload.setToolTip('Descartar edicoes e recarregar do disco')

        # Abrir outro arquivo
        self.act_open = QAction('Abrir', self)
        self.act_open.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.act_open.setToolTip('Abrir outro arquivo YAML')

        # Exportar Biblioteca
        self.act_export_lib = QAction('Exportar Lib', self)
        self.act_export_lib.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self.act_export_lib.setToolTip(
            'Gerar todos os .kicad_mod da pasta modulos_config/ para a biblioteca KiCad')

        # Verificar Footprints
        self.act_verificar = QAction('Verificar', self)
        self.act_verificar.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.act_verificar.setShortcut(QKeySequence('Ctrl+Shift+V'))
        self.act_verificar.setToolTip(
            'Verificar todos os .kicad_mod gerados  (Ctrl+Shift+V)\n'
            'Valida estrutura, pads, courtyard, camadas SMD e furos.')

        # Novo Componente do zero
        self.act_novo = QAction('Novo', self)
        self.act_novo.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.act_novo.setShortcut(QKeySequence('Ctrl+N'))
        self.act_novo.setToolTip('Criar novo componente a partir do _template.yaml  (Ctrl+N)')

        # Duplicar componente atual
        self.act_duplicar = QAction('Duplicar', self)
        self.act_duplicar.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.act_duplicar.setShortcut(QKeySequence('Ctrl+D'))
        self.act_duplicar.setToolTip('Duplicar este componente com novo nome  (Ctrl+D)')
        self.act_duplicar.setEnabled(False)

        # Editor de Pinagem
        self.act_pin_editor = QAction('Pinos', self)
        self.act_pin_editor.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.act_pin_editor.setShortcut(QKeySequence('Ctrl+P'))
        self.act_pin_editor.setToolTip('Abrir editor de nomes e tipos dos pinos  (Ctrl+P)')
        self.act_pin_editor.setEnabled(False)

        # Editor CadQuery
        self.act_cq_editor = QAction('Motor 3D', self)
        self.act_cq_editor.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.act_cq_editor.setShortcut(QKeySequence('Ctrl+Q'))
        self.act_cq_editor.setToolTip('Ver/editar código CadQuery do modelo 3D  (Ctrl+Q)')
        self.act_cq_editor.setEnabled(False)

        # Desfazer / Refazer
        self.act_undo = QAction('Desfazer', self)
        self.act_undo.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setToolTip('Desfazer  (Ctrl+Z)')
        self.act_undo.setEnabled(False)

        self.act_redo = QAction('Refazer', self)
        self.act_redo.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.setToolTip('Refazer  (Ctrl+Y / Ctrl+Shift+Z)')
        self.act_redo.setEnabled(False)

        # Toggle numero de linhas
        self.act_ln = QAction('N°', self)
        self.act_ln.setCheckable(True)
        self.act_ln.setChecked(True)
        self.act_ln.setToolTip('Mostrar / Ocultar numero de linhas')

        # --- Separador ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('background:#313244; max-height:1px;')
        layout.addWidget(sep)

        # --- Editor de texto com numero de linhas ---
        self.editor = LineNumberEditor(self)
        font = QFont('Consolas', 10)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setStyleSheet(
            'LineNumberEditor {'
            '  background:#1E1E2E;'
            '  color:#CDD6F4;'
            '  border:none;'
            '  selection-background-color:#45475A;'
            '}'
        )
        metrics = QFontMetrics(font)
        self.editor.setTabStopDistance(metrics.horizontalAdvance(' ') * 2)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setPlaceholderText('Carregando configuracao YAML...')

        self._highlighter = YamlHighlighter(self.editor.document())
        layout.addWidget(self.editor, stretch=1)

        # --- Barra de Find & Replace (oculta por padrão) ---
        self.find_bar = FindReplaceBar(self.editor, self)
        layout.addWidget(self.find_bar)

        # --- Barra de status ---
        self.status_bar = QLabel('  Nenhum arquivo carregado')
        self.status_bar.setStyleSheet(
            'background:#181825; color:#6C7086; font-size:10px; padding:3px 8px;'
        )
        self.status_bar.setFont(QFont('Consolas', 8))
        layout.addWidget(self.status_bar)

        self.setMinimumWidth(280)

    def _connect_signals(self):
        self.editor.textChanged.connect(self._on_text_changed)
        self._debounce.timeout.connect(self._validate_yaml)
        self.act_gerar.triggered.connect(self._on_gerar)
        self.act_save.triggered.connect(self._save)
        self.act_reload.triggered.connect(self._reload)
        self.act_open.triggered.connect(self._open_dialog)
        self.act_novo.triggered.connect(self._novo_componente)
        self.act_duplicar.triggered.connect(self._duplicar)
        self.act_undo.triggered.connect(self.editor.undo)
        self.act_redo.triggered.connect(self.editor.redo)
        self.editor.undoAvailable.connect(self.act_undo.setEnabled)
        self.editor.redoAvailable.connect(self.act_redo.setEnabled)
        self.act_ln.toggled.connect(self._toggle_line_numbers)
        self.act_export_lib.triggered.connect(self._exportar_biblioteca)
        self.act_verificar.triggered.connect(self._verificar_footprints)
        self.act_save_as.triggered.connect(self._on_save_as)
        self.act_pin_editor.triggered.connect(self._on_pin_editor)
        self.act_cq_editor.triggered.connect(self._on_cq_editor)

        # Atalhos Find & Replace
        sc_find = QShortcut(QKeySequence('Ctrl+F'), self)
        sc_find.activated.connect(self._show_find_bar)
        sc_replace = QShortcut(QKeySequence('Ctrl+H'), self)
        sc_replace.activated.connect(self._show_replace_bar)
        sc_f3 = QShortcut(QKeySequence('F3'), self)
        sc_f3.activated.connect(lambda: self.find_bar.find_next())
        sc_sf3 = QShortcut(QKeySequence('Shift+F3'), self)
        sc_sf3.activated.connect(lambda: self.find_bar.find_prev())
        self.editor.textChanged.connect(self._on_text_changed_autocomplete)

        # Timer de debounce para autocomplete (400ms)
        self._ac_timer = QTimer(self)
        self._ac_timer.setSingleShot(True)
        self._ac_timer.setInterval(400)
        self._ac_timer.timeout.connect(self._show_autocomplete_popup)

        # Timer de auto-geração 2D (2s debounce após edição)
        self._auto_gen_timer = QTimer(self)
        self._auto_gen_timer.setSingleShot(True)
        self._auto_gen_timer.setInterval(2000)
        # Auto-geração desabilitada: usuário deve clicar ▶ explicitamente
        # self._auto_gen_timer.timeout.connect(self._auto_generate_2d)
        # self.editor.textChanged.connect(self._restart_auto_gen)

    # -------------------------------------------------------------------------
    # Find & Replace
    # -------------------------------------------------------------------------
    def _show_find_bar(self):
        self.find_bar.show_find()

    def _show_replace_bar(self):
        self.find_bar.show_replace()

    # -------------------------------------------------------------------------
    # Toggle numero de linhas
    # -------------------------------------------------------------------------
    def _toggle_line_numbers(self, checked: bool):
        self._show_ln = checked
        self.editor.set_line_numbers(checked)
        self.act_ln.setText('  ≡  N° ✓' if checked else '  ≡  N°')

    # -------------------------------------------------------------------------
    # Carregar / Salvar
    # -------------------------------------------------------------------------
    def load_file(self, path: str):
        self._yaml_path = path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self._set_modified(False)
            self.act_duplicar.setEnabled(True)
            self.act_pin_editor.setEnabled(True)
            self.act_cq_editor.setEnabled(True)
            self._validate_yaml()
            self._update_status(f'  {os.path.basename(path)}  —  {path}')
            self.sigFileLoaded.emit(path)
        except Exception as e:
            self._update_status(f'  Erro ao carregar: {e}', error=True)

    def _on_pin_editor(self):
        """Abre o editor de pinagem para o YAML atual."""
        if not self._yaml_path:
            return
        try:
            import yaml
            dados = yaml.safe_load(self.editor.toPlainText())
            if not isinstance(dados, dict):
                self._update_status('  YAML invalido para editor de pinagem', error=True)
                return
            from painel_pin_editor import PinEditorDialog
            dlg = PinEditorDialog(dados, self._yaml_path, parent=self)
            dlg.exec_()
            # Recarregar o YAML caso o editor tenha salvo alterações
            self.load_file(self._yaml_path)
        except Exception as e:
            self._update_status(f'  Erro ao abrir pinagem: {e}', error=True)

    def _on_cq_editor(self):
        """Abre o editor de código CadQuery para o YAML atual."""
        if not self._yaml_path:
            return
        try:
            import yaml
            dados = yaml.safe_load(self.editor.toPlainText())
            if not isinstance(dados, dict):
                self._update_status('  YAML invalido para editor CadQuery', error=True)
                return
            from painel_cadquery_editor import CadQueryEditorDialog
            dlg = CadQueryEditorDialog(dados, self._yaml_path, parent=self)
            dlg.exec_()
            # Recarregar o YAML caso o editor tenha salvo alterações
            self.load_file(self._yaml_path)
        except Exception as e:
            self._update_status(f'  Erro ao abrir CadQuery: {e}', error=True)

    def _save(self) -> bool:
        if not self._yaml_path:
            return self._save_as()
        if not self._valid_yaml:
            resp = QMessageBox.warning(
                self, 'YAML Invalido',
                'YAML contém erros de sintaxe. Salvar mesmo assim?\n'
                '(O footprint não será gerado até corrigir)',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resp != QMessageBox.Yes:
                return False
        try:
            with open(self._yaml_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self._set_modified(False)
            self.sigSaved.emit(self._yaml_path)
            self._update_status(f'  Salvo: {os.path.basename(self._yaml_path)}', saved=True)
            return True
        except Exception as e:
            self._update_status(f'  Erro ao salvar: {e}', error=True)
            return False

    def _save_as(self) -> bool:
        """Redireciona para _on_save_as (implementação principal)."""
        self._on_save_as()
        return not self._modified

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Salvar YAML Como...',
            self._yaml_path or os.path.join(self._proj_dir, 'modulos_config', 'novo.yaml'),
            'YAML Files (*.yaml *.yml);;All Files (*)')
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                self._yaml_path = path
                self._set_modified(False)
                self._update_status(f'  Salvo como: {os.path.basename(path)}', saved=True)
                self.sigFileLoaded.emit(path)
            except Exception as e:
                self._update_status(f'  Erro ao salvar: {e}', error=True)

    def _reload(self):
        if self._modified:
            resp = QMessageBox.question(
                self, 'Recarregar',
                'Descartar edicoes e recarregar do disco?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
        if self._yaml_path:
            self.load_file(self._yaml_path)

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Abrir Configuracao YAML',
            os.path.dirname(self._yaml_path or self._proj_dir),
            'YAML Files (*.yaml *.yml);;All Files (*)')
        if path:
            self.load_file(path)
            self._write_estado()

    def _novo_componente(self):
        """Novo componente: salva atual se necessario, cria arquivo a partir do _template.yaml."""

        # 1. Perguntar se salva o arquivo atual
        if self._modified and self._yaml_path:
            resp = QMessageBox.question(
                self, 'Salvar alteracoes?',
                f'O arquivo "{os.path.basename(self._yaml_path)}" tem modificacoes nao salvas.\n\n'
                'Deseja salvar antes de criar o novo componente?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save)
            if resp == QMessageBox.Cancel:
                return
            if resp == QMessageBox.Save:
                if not self._save():
                    return

        # 2. Carregar _template.yaml como ponto de partida (fallback: skeleton fixo)
        template_path = os.path.join(self._proj_dir, 'modulos_config', '_template.yaml')
        if os.path.isfile(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    skeleton = f.read()
            except Exception:
                skeleton = self._NOVO_SKELETON
        else:
            skeleton = self._NOVO_SKELETON

        # 3. Dialogo para escolher nome/caminho
        default_dir = os.path.join(self._proj_dir, 'modulos_config')
        os.makedirs(default_dir, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Novo Componente — Escolha o nome do arquivo',
            os.path.join(default_dir, 'novo_componente.yaml'),
            'YAML Files (*.yaml *.yml)')
        if not path:
            return

        # 4. Gravar template e abrir no editor
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(skeleton)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Nao foi possivel criar o arquivo:\n{e}')
            return

        self._yaml_path = path
        self.editor.blockSignals(True)
        self.editor.setPlainText(skeleton)
        self.editor.blockSignals(False)
        self._set_modified(False)
        self._validate_yaml()
        self._write_estado()
        self.act_duplicar.setEnabled(True)
        self._update_status(
            f'  Novo: {os.path.basename(path)}  —  baseado em _template.yaml. Edite e clique Atualizar 2D + 3D')

        # Posicionar cursor em "NomeDoComponente" para edicao imediata
        texto = self.editor.toPlainText()
        idx = texto.find('"NomeDoComponente"')
        if idx >= 0:
            cursor = self.editor.textCursor()
            cursor.setPosition(idx + 1)
            cursor.setPosition(idx + len('"NomeDoComponente"') - 1, cursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _duplicar(self):
        """Duplica o componente atual com um novo nome."""
        if not self._yaml_path or not os.path.isfile(self._yaml_path):
            QMessageBox.warning(self, 'Duplicar', 'Salve o componente antes de duplicar.')
            return

        nome_atual = os.path.basename(self._yaml_path).replace('.yaml', '')
        nome_novo, ok = QInputDialog.getText(
            self, 'Duplicar Componente',
            'Nome do novo componente (sem espacos):',
            text=f'{nome_atual}_copia')
        if not ok or not nome_novo.strip():
            return

        nome_novo = nome_novo.strip().replace(' ', '_')
        pasta = os.path.dirname(self._yaml_path)
        novo_path = os.path.join(pasta, f'{nome_novo}.yaml')

        if os.path.isfile(novo_path):
            QMessageBox.warning(self, 'Duplicar', f'Ja existe um arquivo chamado "{nome_novo}.yaml"!')
            return

        # Copiar e substituir o campo nome:
        try:
            with open(self._yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            import re as _re
            # Substitui nome: "Qualquer coisa" ou nome: Qualquer_coisa
            content = _re.sub(
                r'^(nome:\s*)("[^"]*"|[^\s#]+)',
                f'\\g<1>"{nome_novo}"',
                content, count=1, flags=_re.MULTILINE)
            with open(novo_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao duplicar:\n{e}')
            return

        self.load_file(novo_path)
        self._write_estado()
        self._update_status(f'  Duplicado: {nome_novo}.yaml  —  baseado em {nome_atual}.yaml')

    # -------------------------------------------------------------------------
    # Validacao e estado
    # -------------------------------------------------------------------------
    def _on_text_changed(self):
        self._set_modified(True)
        self._debounce.start()

    def _restart_auto_gen(self):
        """Reinicia timer de auto-geração 2D a cada edição."""
        if not self._is_auto_saving:
            self._auto_gen_timer.start()

    def _save_current(self) -> bool:
        """Salva o YAML atual em disco silenciosamente (sem diálogos)."""
        if not self._yaml_path or not self._valid_yaml:
            return False
        try:
            with open(self._yaml_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self._set_modified(False)
            return True
        except Exception as e:
            log.warning('Auto-save falhou: %s', e)
            return False

    def _auto_generate_2d(self):
        """Auto-gera footprint/symbol 2D após 2s sem digitar (se YAML válido)."""
        if not self._valid_yaml:
            return
        # Salvar o YAML para disco antes de gerar
        self._is_auto_saving = True
        try:
            self._save_current()
        finally:
            self._is_auto_saving = False
        self._write_estado()
        self.sigGerarRequested.emit()

    def _validate_yaml(self):
        text = self.editor.toPlainText()
        try:
            parsed = yaml.safe_load(text)
            self._valid_yaml = True
            self._clear_error_markers()
            self.sigValidationChanged.emit(True)
            keys = list(parsed.keys()) if isinstance(parsed, dict) else []
            fname = os.path.basename(self._yaml_path) if self._yaml_path else '?'
            mod = '●  ' if self._modified else ''
            self.status_bar.setText(
                f'  {mod}{fname}  —  YAML valido  —  '
                f'{len(keys)} chaves: {", ".join(keys[:4])}{"..." if len(keys) > 4 else ""}')
            self.status_bar.setStyleSheet(
                'background:#181825; color:#A6E3A1; font-size:10px; padding:3px 8px;')
            # Validacao semantica (nao bloqueia, apenas avisos)
            avisos = self._validate_semantics(parsed)
            if avisos:
                aviso_txt = ' | '.join(avisos[:2])  # max 2 avisos por vez
                if len(avisos) > 2:
                    aviso_txt += f' (+{len(avisos)-2} mais)'
                self.status_bar.setText(f'  {mod}{fname}  —  YAML valido  —  {aviso_txt}')
                self.status_bar.setStyleSheet(
                    'background:#2D2A18; color:#F5C542; font-size:10px; padding:3px 8px;')
        except yaml.YAMLError as e:
            self._valid_yaml = False
            self.sigValidationChanged.emit(False)
            msg = str(e).split('\n')[0][:80]
            self.status_bar.setText(f'  ⚠  YAML invalido: {msg}')
            self.status_bar.setStyleSheet(
                'background:#2D1B1B; color:#F38BA8; font-size:10px; padding:3px 8px;')
            # Highlight the error line if position info is available
            if hasattr(e, 'problem_mark') and e.problem_mark is not None:
                self._highlight_error_line(e.problem_mark.line, msg)
            else:
                self._clear_error_markers()

    # -------------------------------------------------------------------------
    # Error line markers
    # -------------------------------------------------------------------------
    def _highlight_error_line(self, line_number: int, message: str = ''):
        """Highlight the given line (0-indexed) with a subtle red background."""
        doc = self.editor.document()
        block = doc.findBlockByNumber(line_number)
        if not block.isValid():
            return

        sel = self.editor.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 50, 50, 40))
        fmt.setProperty(QTextCharFormat.FullWidthSelection, True)
        if message:
            fmt.setToolTip(message)
        sel.format = fmt
        cursor = QTextCursor(block)
        cursor.clearSelection()
        sel.cursor = cursor

        self._error_selections = [sel]
        self._apply_all_extra_selections()

    def _clear_error_markers(self):
        """Remove all error highlights."""
        if self._error_selections:
            self._error_selections = []
            self._apply_all_extra_selections()

    def _apply_all_extra_selections(self):
        """Merge error markers + search highlights and apply to editor."""
        combined = list(self._error_selections) + list(self._search_selections)
        self.editor.setExtraSelections(combined)
        # Expose a callback so FindReplaceBar can retrieve error selections
        self.editor._owner_error_selections = lambda: list(self._error_selections)

    def _validate_semantics(self, dados: dict) -> list:
        """Retorna lista de avisos semanticos (nao bloqueiam a geracao)."""
        avisos = []
        if not isinstance(dados, dict):
            return avisos

        nome = dados.get('nome', '')
        tipo = dados.get('tipo', '')

        # Nome com espacos
        if nome and ' ' in str(nome):
            avisos.append('⚠ nome nao pode ter espacos')

        # Tipo desconhecido
        if tipo and tipo not in self._TIPOS_YAML:
            avisos.append(f'⚠ tipo "{tipo}" desconhecido — validos: {sorted(self._TIPOS_YAML)}')

        # Validacoes especificas por tipo
        if tipo in ('diodo_pth', 'resistor_pth'):
            pinos = dados.get('pinos', {})
            corpo = dados.get('corpo', {})
            try:
                furo = float(pinos.get('diametro_furo', 0))
                pad  = float(pinos.get('diametro_pad', 1))
                if furo >= pad:
                    avisos.append('⚠ diametro_furo >= diametro_pad (furo maior que o pad!)')
            except (ValueError, TypeError):
                pass
            try:
                esp  = float(pinos.get('espacamento', 0))
                comp = float(corpo.get('comprimento', 0))
                if comp > esp:
                    avisos.append('⚠ corpo.comprimento > pinos.espacamento (corpo nao cabe!)')
            except (ValueError, TypeError):
                pass

        if tipo == 'ci_dip':
            pinos = dados.get('pinos', {})
            try:
                total = int(pinos.get('total', 0))
                if total % 2 != 0:
                    avisos.append('⚠ ci_dip: total de pinos deve ser par')
                if total > 64:
                    avisos.append('⚠ ci_dip: total de pinos muito alto (max 64)')
            except (ValueError, TypeError):
                pass

        # Verificar sintaxe do modelo_3d_python (se presente)
        codigo = dados.get('modelo_3d_python')
        if codigo:
            try:
                compile(str(codigo), '<modelo_3d_python>', 'exec')
            except SyntaxError as e:
                avisos.append(f'⚠ modelo_3d_python: erro de sintaxe Python — {e.msg} (linha {e.lineno})')

        return avisos

    # -------------------------------------------------------------------------
    # YAML key suggestions per context block (Fix 9)
    # -------------------------------------------------------------------------
    _YAML_KEY_SUGGESTIONS = {
        '_top_level': [
            'nome', 'tipo', 'padrao', 'pinos', 'corpo', 'margens',
            'kicad', 'modelo_3d_python', 'thermal_pad',
        ],
        'pinos': [
            'total', 'pitch', 'espacamento', 'diametro_pad', 'diametro_furo',
            'tamanho_pad', 'lados', 'linhas', 'colunas', 'excluir', 'afastamento',
        ],
        'corpo': [
            'largura', 'comprimento', 'altura', 'diametro', 'formato',
            'afastamento_colunas',
        ],
        'margens': ['courtyard', 'silkscreen', 'fab_line'],
        'kicad': ['referencia', 'descricao', 'tags', 'atributo'],
        'tamanho_pad': ['largura', 'altura'],
    }

    def _detect_yaml_context(self):
        """Detect the current YAML context block from cursor position.

        Returns (parent_key, typed_prefix):
        - parent_key: the parent block name (e.g. 'pinos', 'corpo') or '_top_level'
        - typed_prefix: what the user has typed so far on the current line
        """
        cursor = self.editor.textCursor()
        block = cursor.block()
        current_line = block.text()
        current_indent = len(current_line) - len(current_line.lstrip())

        # Extract the partial key typed so far on this line
        typed = current_line.lstrip()
        # If the line already has a colon with a value, it's not a key being typed
        if ':' in typed and not typed.endswith(':'):
            # Could still be typing a value for 'tipo:'
            return None, typed

        # Remove trailing colon if any
        prefix = typed.rstrip(':')

        if current_indent == 0:
            return '_top_level', prefix

        # Walk backwards to find the parent key
        prev = block.previous()
        while prev.isValid():
            prev_text = prev.text()
            prev_indent = len(prev_text) - len(prev_text.lstrip())
            prev_stripped = prev_text.strip()

            # Parent is a line with less indent that ends with ':'
            if prev_indent < current_indent and prev_stripped.endswith(':'):
                parent_key = prev_stripped.rstrip(':').strip()
                return parent_key, prefix
            # Stop searching if we reach top-level
            if prev_indent == 0 and prev_stripped:
                if prev_stripped.endswith(':'):
                    parent_key = prev_stripped.rstrip(':').strip()
                    return parent_key, prefix
                return '_top_level', prefix
            prev = prev.previous()

        return '_top_level', prefix

    def _on_text_changed_autocomplete(self):
        """Aciona timer de debounce para autocomplete (tipo: values + key suggestions)."""
        cursor = self.editor.textCursor()
        linha = cursor.block().text().strip()

        # Trigger for tipo: value autocomplete
        if linha.startswith('tipo:'):
            self._ac_timer.start()
            return

        # Trigger for key autocomplete: line has no colon yet or ends with colon
        # (user is typing a key name)
        if not linha or (':' not in linha) or linha.endswith(':'):
            self._ac_timer.start()
            return

        self._ac_timer.stop()

    def _show_autocomplete_popup(self):
        """Mostra autocomplete: tipo: values or context-aware key suggestions."""
        cursor = self.editor.textCursor()
        linha = cursor.block().text().strip()

        # --- tipo: value autocomplete (existing behavior) ---
        if linha.startswith('tipo:'):
            self._show_tipo_autocomplete(linha)
            return

        # --- Context-aware key autocomplete (Fix 9) ---
        context, prefix = self._detect_yaml_context()
        if context is None:
            return

        suggestions = self._YAML_KEY_SUGGESTIONS.get(context, [])
        if not suggestions:
            return

        # Filter by prefix already typed
        prefix_lower = prefix.lower()
        filtered = [k for k in suggestions if k.lower().startswith(prefix_lower)]
        # Don't show if nothing matches or prefix is already an exact match
        if not filtered or (prefix in suggestions and len(filtered) == 1):
            return

        # Show popup menu
        from PyQt5.QtWidgets import QMenu, QAction as _QA
        menu = QMenu(self.editor)
        menu.setStyleSheet(
            'QMenu { background:#252540; color:#CDD6F4; border:1px solid #444466; '
            'font-family:Consolas; font-size:11px; }'
            'QMenu::item { padding:4px 16px; }'
            'QMenu::item:selected { background:#313244; }')

        for key in filtered:
            act = _QA(key, menu)
            def _apply_key(k=key):
                c = self.editor.textCursor()
                c.select(c.LineUnderCursor)
                current_text = c.block().text()
                indent = len(current_text) - len(current_text.lstrip())
                c.insertText(' ' * indent + k + ': ')
            act.triggered.connect(_apply_key)
            menu.addAction(act)

        rect = self.editor.cursorRect()
        pos = self.editor.viewport().mapToGlobal(rect.bottomLeft())
        menu.exec_(pos)

    def _show_tipo_autocomplete(self, linha: str):
        """Autocomplete for tipo: values (original behavior preserved)."""
        apos = linha[5:].strip()  # texto depois de 'tipo:'
        # Remove surrounding quotes if partially typed
        apos = apos.strip('"').strip("'")
        if len(apos) > 10:  # usuario ja digitou algo longo, nao interferir
            return

        tipos_filtrados = [t for t in self._TIPOS_YAML if t.startswith(apos)]
        if not tipos_filtrados or apos in self._TIPOS_YAML:
            return

        from PyQt5.QtWidgets import QMenu, QAction as _QA
        menu = QMenu(self.editor)
        menu.setStyleSheet(
            'QMenu { background:#252540; color:#CDD6F4; border:1px solid #444466; }'
            'QMenu::item:selected { background:#313244; }')
        for tipo in tipos_filtrados:
            act = _QA(tipo, menu)
            def _apply(t=tipo):
                c = self.editor.textCursor()
                c.select(c.LineUnderCursor)
                indentacao = len(c.block().text()) - len(c.block().text().lstrip())
                c.insertText(' ' * indentacao + f'tipo: "{t}"')
            act.triggered.connect(_apply)
            menu.addAction(act)

        rect = self.editor.cursorRect()
        pos = self.editor.viewport().mapToGlobal(rect.bottomLeft())
        menu.exec_(pos)

    def _set_modified(self, modified: bool):
        self._modified = modified
        self.act_save.setEnabled(modified)
        self.act_save.setText('💾 Salvar ●' if modified else '💾 Salvar')
        self.act_gerar.setEnabled(True)

    def _update_status(self, text: str, error=False, saved=False):
        color = '#F38BA8' if error else ('#A6E3A1' if saved else '#6C7086')
        bg    = '#2D1B1B' if error else ('#1B2D1B' if saved else '#181825')
        self.status_bar.setText(text)
        self.status_bar.setStyleSheet(
            f'background:{bg}; color:{color}; font-size:10px; padding:3px 8px;')
        if saved:
            QTimer.singleShot(3000, self._validate_yaml)

    # -------------------------------------------------------------------------
    # Verificar Footprints
    # -------------------------------------------------------------------------
    def _verificar_footprints(self):
        """Roda verificar_kicad.py e exibe o resultado em uma janela scrollavel."""
        import subprocess, sys

        script = os.path.join(self._proj_dir, 'core', 'verificar_kicad.py')
        if not os.path.isfile(script):
            QMessageBox.warning(self, 'Verificar', 'verificar_kicad.py nao encontrado.')
            return

        self._update_status('  Verificando footprints...')
        try:
            r = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                cwd=self._proj_dir, timeout=60)
            saida = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            saida = '[ERRO] Timeout ao executar verificar_kicad.py (>60s)'
        except Exception as e:
            saida = f'[ERRO] {e}'

        # ── Contar resultados ────────────────────────────────────────────────
        ok_n   = saida.count('[OK]')
        warn_n = saida.count('[AVISO]')
        titulo = f'Verificar Footprints  —  {ok_n} OK  |  {warn_n} avisos'
        self._update_status(
            f'  Verificacao: {ok_n} OK  |  {warn_n} avisos',
            error=(warn_n > 0))

        # ── Dialog scrollavel ────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(titulo)
        dlg.resize(640, 440)
        dlg.setStyleSheet('background:#1E1E2E; color:#CDD6F4;')

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)

        txt = QPlainTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setFont(QFont('Consolas', 9))
        txt.setStyleSheet(
            'QPlainTextEdit { background:#181825; color:#CDD6F4; border:none; }'
            'QScrollBar:vertical { background:#181825; width:8px; }'
            'QScrollBar::handle:vertical { background:#45475A; border-radius:4px; }')

        # Colorir linhas OK / AVISO / ERRO
        linhas_coloridas = []
        for linha in saida.splitlines():
            if '[OK]' in linha:
                linhas_coloridas.append(f'\u2713 {linha}')
            elif '[AVISO]' in linha:
                linhas_coloridas.append(f'\u26a0 {linha}')
            else:
                linhas_coloridas.append(f'  {linha}')
        txt.setPlainText('\n'.join(linhas_coloridas))

        lay.addWidget(txt)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.setStyleSheet(
            'QPushButton { background:#313244; color:#CDD6F4; border:none; '
            'padding:5px 18px; border-radius:4px; }'
            'QPushButton:hover { background:#45475A; }')
        btn_box.accepted.connect(dlg.accept)
        lay.addWidget(btn_box)

        dlg.exec_()

    # -------------------------------------------------------------------------
    # Estado compartilhado
    # -------------------------------------------------------------------------
    def _write_estado(self, output_dir=None):
        try:
            estado = {}
            if os.path.isfile(self._estado_path):
                with open(self._estado_path, 'r', encoding='utf-8') as f:
                    estado = json.load(f)
            estado['yaml_path'] = self._yaml_path
            if output_dir:
                estado['output_dir'] = output_dir
            with open(self._estado_path, 'w', encoding='utf-8') as f:
                json.dump(estado, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning('Aviso estado: %s', e)

    # -------------------------------------------------------------------------
    # Gerar / Atualizar
    # -------------------------------------------------------------------------
    def _on_gerar(self):
        """Salva o YAML e gera preview temporário (saida/_preview/)."""
        log.debug('_on_gerar: modified=%s, yaml=%s', self._modified, self._yaml_path)
        if self._modified:
            if not self._save():
                log.debug('_on_gerar: _save() retornou False — abortando')
                return
        # Gerar em diretório de preview
        preview_dir = os.path.join(self._proj_dir, 'saida', '_preview')
        self._write_estado(output_dir=preview_dir)
        log.debug('_on_gerar: emitindo sigGerarRequested (preview: %s)', preview_dir)
        self.sigGerarRequested.emit()

    def _exportar_biblioteca(self):
        """Chama exportar_biblioteca.py via subprocess para gerar a biblioteca."""
        import subprocess
        script = os.path.join(self._proj_dir, 'core', 'exportar_biblioteca.py')
        if not os.path.isfile(script):
            QMessageBox.warning(self, 'Script nao encontrado',
                f'Arquivo nao encontrado:\n{script}\n\nCrie exportar_biblioteca.py primeiro.')
            return
        venv_python = os.path.join(self._proj_dir, '.venv', 'Scripts', 'python.exe')
        python_exe = venv_python if os.path.isfile(venv_python) else 'python'
        try:
            self._update_status('  Exportando biblioteca...', saved=False)
            resultado = subprocess.run(
                [python_exe, script],
                cwd=self._proj_dir,
                capture_output=True, text=True, timeout=60
            )
            if resultado.returncode == 0:
                self._update_status(
                    f'  Biblioteca exportada! {resultado.stdout.strip()[:80]}',
                    saved=True)
            else:
                self._update_status(
                    f'  Erro ao exportar: {resultado.stderr.strip()[:80]}',
                    error=True)
        except subprocess.TimeoutExpired:
            self._update_status('  Timeout ao exportar biblioteca', error=True)
        except Exception as e:
            self._update_status(f'  Erro: {e}', error=True)

    # -------------------------------------------------------------------------
    # Fechar com aviso de alterações não salvas
    # -------------------------------------------------------------------------
    def closeEvent(self, event):
        if self._modified:
            from PyQt5.QtWidgets import QMessageBox
            resp = QMessageBox.question(
                self, 'Alterações não salvas',
                'O YAML foi modificado. Deseja salvar antes de sair?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if resp == QMessageBox.Save:
                self._save()
                event.accept()
            elif resp == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    # -------------------------------------------------------------------------
    # Drag & Drop
    # -------------------------------------------------------------------------
    def dragEnterEvent(self, event):
        """Aceita drag se contém URLs terminando em .yaml ou .yml."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.yaml', '.yml')):
                    event.acceptProposedAction()
                    self._drag_over = True
                    self.setStyleSheet(self.styleSheet())
                    self.editor.setStyleSheet(
                        'LineNumberEditor {'
                        '  background:#1E1E2E;'
                        '  color:#CDD6F4;'
                        '  border: 2px solid #89B4FA;'
                        '  selection-background-color:#45475A;'
                        '}'
                    )
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        """Mantém aceitação durante o arrasto."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Remove feedback visual ao sair da área de drop."""
        self._drag_over = False
        self.editor.setStyleSheet(
            'LineNumberEditor {'
            '  background:#1E1E2E;'
            '  color:#CDD6F4;'
            '  border:none;'
            '  selection-background-color:#45475A;'
            '}'
        )
        event.accept()

    def dropEvent(self, event):
        """Carrega o arquivo YAML arrastado."""
        # Remover feedback visual
        self._drag_over = False
        self.editor.setStyleSheet(
            'LineNumberEditor {'
            '  background:#1E1E2E;'
            '  color:#CDD6F4;'
            '  border:none;'
            '  selection-background-color:#45475A;'
            '}'
        )

        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.yaml', '.yml')) and os.path.isfile(path):
                    self.load_file(path)
                    self._write_estado()
                    event.acceptProposedAction()
                    return
        event.ignore()

    # -------------------------------------------------------------------------
    # Propriedades
    # -------------------------------------------------------------------------
    @property
    def yaml_path(self) -> str:
        return self._yaml_path

    @property
    def is_modified(self) -> bool:
        return self._modified
