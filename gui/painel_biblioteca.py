# =============================================================================
# painel_biblioteca.py
# Painel de biblioteca de componentes — lista todos os YAMLs com ícone por tipo
# Duplo-clique → carrega YAML no editor e dispara geração
# =============================================================================
import os
import shutil
import yaml

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QLineEdit,
    QPushButton, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QFileSystemWatcher
from PyQt5.QtGui import QFont, QColor, QIcon

# Ícone (emoji) por tipo de componente
TIPO_ICON = {
    'castellated':     '📡',
    'diodo_pth':       '🔺',
    'resistor_pth':    '🟧',
    'ci_dip':          '🔲',
    'ci_soic':         '▫️',
    'conector_pth':    '🔌',
    'led_pth':         '💡',
    'capacitor_pth':   '🔋',
    'transistor_to92': '🔷',
    'crystal_hc49':    '📶',
    'custom':          '⚙️',
}

class BibliotecaPanel(QWidget):
    """
    Painel de biblioteca de componentes.
    Sinais:
        sigComponenteSelecionado(yaml_path): emitido ao dar duplo-clique num componente
    """
    sigComponenteSelecionado = pyqtSignal(str)  # str = caminho do YAML
    sigPreviewSolicitado     = pyqtSignal(str)  # str = caminho do YAML (single-click)

    def __init__(self, modulos_dir: str, parent=None):
        super().__init__(parent)
        self._modulos_dir = modulos_dir
        self._watcher = QFileSystemWatcher(self)
        self._setup_ui()
        self._conectar_sinais()
        self._carregar_componentes()
        self._watcher.addPath(modulos_dir)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Título
        titulo = QLabel('  📚  Biblioteca de Componentes')
        titulo.setStyleSheet(
            'background:#12122A; color:#89B4FA; font-size:12px; '
            'font-weight:bold; padding:6px 8px; border-bottom:1px solid #313244;'
        )
        layout.addWidget(titulo)

        # Campo de busca
        self.busca = QLineEdit()
        self.busca.setPlaceholderText('🔍  Buscar componente...')
        self.busca.setStyleSheet(
            'QLineEdit { background:#1E1E2E; color:#CDD6F4; border:none; '
            'border-bottom:1px solid #313244; padding:5px 8px; font-size:11px; }'
        )
        layout.addWidget(self.busca)

        # Árvore de componentes
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            'QTreeWidget { background:#1A1A2E; color:#CDD6F4; border:none; '
            'font-size:11px; outline:0; }'
            'QTreeWidget::item { padding:3px 4px; }'
            'QTreeWidget::item:hover { background:#252540; }'
            'QTreeWidget::item:selected { background:#313244; color:#89B4FA; }'
            'QTreeWidget::branch { background:#1A1A2E; }'
        )
        self.tree.setIndentation(16)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.tree, stretch=1)

        # Barra de status
        self.status = QLabel('')
        self.status.setStyleSheet(
            'background:#181825; color:#6C7086; font-size:10px; padding:3px 8px;'
        )
        layout.addWidget(self.status)

        self.setMinimumWidth(200)

    def _conectar_sinais(self):
        self.tree.itemDoubleClicked.connect(self._on_duplo_clique)
        self.tree.itemClicked.connect(self._on_clique)
        self.busca.textChanged.connect(self._filtrar)
        self._watcher.directoryChanged.connect(lambda _: self._carregar_componentes())

    def _carregar_componentes(self):
        """Lê todos os YAMLs da pasta e popula a árvore."""
        self.tree.clear()
        self._itens = {}  # yaml_path → QTreeWidgetItem

        grupos = {}  # tipo → QTreeWidgetItem pai

        yamls = sorted([
            f for f in os.listdir(self._modulos_dir)
            if f.endswith(('.yaml', '.yml')) and not f.startswith('_')
        ])

        total = 0
        for yaml_file in yamls:
            path = os.path.join(self._modulos_dir, yaml_file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    dados = yaml.safe_load(f)
                if not isinstance(dados, dict):
                    continue
                nome = dados.get('nome', yaml_file)
                tipo = dados.get('tipo', 'custom')
                kicad = dados.get('kicad', {})
                desc  = kicad.get('descricao', '') if isinstance(kicad, dict) else ''
                tags  = kicad.get('tags', '')    if isinstance(kicad, dict) else ''
                icone = TIPO_ICON.get(tipo, '⚙️')

                # Criar grupo pai se não existir
                if tipo not in grupos:
                    grupo_item = QTreeWidgetItem(self.tree)
                    grupo_item.setText(0, f'{icone}  {tipo}')
                    grupo_item.setForeground(0, QColor('#89B4FA'))
                    grupo_item.setFont(0, QFont('Consolas', 10, QFont.Bold))
                    grupo_item.setExpanded(True)
                    grupo_item.setData(0, Qt.UserRole, None)  # grupo, não abre YAML
                    grupos[tipo] = grupo_item

                # Criar item filho
                item = QTreeWidgetItem(grupos[tipo])
                item.setText(0, f'  {nome}')
                item.setToolTip(0, f'{desc}\n{tags}\n{path}')
                item.setForeground(0, QColor('#CDD6F4'))
                item.setData(0, Qt.UserRole,     path)              # caminho do YAML
                item.setData(0, Qt.UserRole + 1, f'{desc} {tags}') # metadados para busca
                self._itens[path] = item
                total += 1

            except Exception:
                continue

        self.status.setText(f'  {total} componentes  |  {len(grupos)} tipos')

    def _on_duplo_clique(self, item, _col):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.sigComponenteSelecionado.emit(path)

    def _on_clique(self, item, _col):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.sigPreviewSolicitado.emit(path)

    # ── Context Menu (right-click) ───────────────────────────────────────
    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if not path:  # grupo, nao componente
            return

        from PyQt5.QtWidgets import QMenu, QAction, QInputDialog, QMessageBox
        menu = QMenu(self)
        menu.setStyleSheet(
            'QMenu { background:#252540; color:#CDD6F4; border:1px solid #444466; }'
            'QMenu::item:selected { background:#313244; }')

        act_rename = QAction('✏️  Renomear', menu)
        act_delete = QAction('🗑️  Excluir', menu)
        act_dup    = QAction('📋  Duplicar', menu)
        menu.addAction(act_rename)
        menu.addAction(act_dup)
        menu.addSeparator()
        menu.addAction(act_delete)

        act_rename.triggered.connect(lambda: self._renomear(path))
        act_delete.triggered.connect(lambda: self._excluir(path))
        act_dup.triggered.connect(lambda: self._duplicar(path))

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _renomear(self, path):
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        nome_atual = os.path.basename(path)
        novo_nome, ok = QInputDialog.getText(self, 'Renomear', 'Novo nome:', text=nome_atual)
        if ok and novo_nome and novo_nome != nome_atual:
            novo_path = os.path.join(os.path.dirname(path), novo_nome)
            try:
                os.rename(path, novo_path)
                self._carregar_componentes()
            except Exception as e:
                QMessageBox.warning(self, 'Erro', f'Erro ao renomear: {e}')

    def _excluir(self, path):
        from PyQt5.QtWidgets import QMessageBox
        resp = QMessageBox.question(self, 'Confirmar exclusao',
            f'Excluir {os.path.basename(path)}?\nEsta acao nao pode ser desfeita.',
            QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            try:
                os.remove(path)
                self._carregar_componentes()
            except Exception as e:
                QMessageBox.warning(self, 'Erro', f'Erro ao excluir: {e}')

    def _duplicar(self, path):
        base = os.path.basename(path)
        nome, ext = os.path.splitext(base)
        novo = os.path.join(os.path.dirname(path), f'{nome}_copia{ext}')
        try:
            shutil.copy2(path, novo)
            self._carregar_componentes()
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Erro', f'Erro ao duplicar: {e}')

    def _filtrar(self, texto):
        """Filtra por nome, tags e descricao (case-insensitive)."""
        texto = texto.lower().strip()
        for path, item in self._itens.items():
            if not texto:
                item.setHidden(False)
            else:
                nome_txt = item.text(0).lower()
                meta_txt = (item.data(0, Qt.UserRole + 1) or '').lower()
                path_txt = path.lower()
                encontrou = (texto in nome_txt or
                             texto in meta_txt or
                             texto in path_txt)
                item.setHidden(not encontrou)
        # Mostrar/ocultar grupos vazios
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            grupo = root.child(i)
            todos_ocultos = all(
                grupo.child(j).isHidden() for j in range(grupo.childCount())
            )
            grupo.setHidden(todos_ocultos)

    def refresh(self):
        """Recarregar a lista de componentes."""
        self._carregar_componentes()
