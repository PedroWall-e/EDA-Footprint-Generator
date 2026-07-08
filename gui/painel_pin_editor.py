# =============================================================================
# painel_pin_editor.py
# Janela QDialog para edição visual de pin_names e pin_types.
#
# Permite ao usuário:
#   - Visualizar todos os pinos com posição, lado e tipo
#   - Editar nomes e tipos elétricos
#   - Auto-numerar, colar do Excel, preencher NC, inverter ordem
#   - Salvar alterações diretamente no arquivo YAML
# =============================================================================

import yaml

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QComboBox,
    QPushButton, QRadioButton, QButtonGroup,
    QFrame, QHeaderView, QApplication, QMessageBox,
    QAbstractItemView, QWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from geometria_pads import calcular_pads


# =============================================================================
# Mapa de lados: interno → exibição
# =============================================================================
_LADO_DISPLAY = {
    'esquerdo': 'Esquerdo',
    'base':     'Base',
    'direito':  'Direito',
    'topo':     'Topo',
}

# Tipos elétricos disponíveis para o ComboBox
_TIPOS_ELETRICOS = [
    'bidirectional',
    'input',
    'output',
    'power_in',
    'power_out',
    'passive',
    'unspecified',
]


# =============================================================================
# Stylesheet global do diálogo
# =============================================================================
_STYLE = """
QDialog {
    background: #1E1E2E;
    color: #CDD6F4;
}
QLabel {
    color: #CDD6F4;
    font-size: 12px;
}
QLabel#lbl_titulo {
    font-size: 15px;
    font-weight: bold;
    color: #89B4FA;
    padding: 4px 0;
}
QLabel#lbl_secao {
    font-size: 11px;
    color: #A6ADC8;
    padding: 2px 0;
}
QRadioButton {
    color: #CDD6F4;
    spacing: 6px;
    font-size: 12px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid #585B70;
    border-radius: 8px;
    background: #1E1E2E;
}
QRadioButton::indicator:checked {
    background: #89B4FA;
    border-color: #89B4FA;
}
QRadioButton::indicator:hover {
    border-color: #89B4FA;
}
QTableWidget {
    background: #1E1E2E;
    alternate-background-color: #252540;
    color: #CDD6F4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
    font-size: 12px;
    selection-background-color: #45475A;
    selection-color: #CDD6F4;
}
QTableWidget::item {
    padding: 3px 6px;
}
QHeaderView::section {
    background: #181825;
    color: #89B4FA;
    font-weight: bold;
    font-size: 11px;
    padding: 5px 8px;
    border: none;
    border-bottom: 2px solid #313244;
    border-right: 1px solid #252540;
}
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #45475A;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #585B70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #181825;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #45475A;
    min-width: 30px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #585B70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QPushButton {
    background: #313244;
    color: #CDD6F4;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
    min-width: 80px;
}
QPushButton:hover {
    background: #45475A;
}
QPushButton:pressed {
    background: #585B70;
}
QPushButton#btn_salvar {
    background: #1E6640;
    color: #A6E3A1;
}
QPushButton#btn_salvar:hover {
    background: #27804F;
}
QPushButton#btn_fechar {
    background: #5C2020;
    color: #F38BA8;
}
QPushButton#btn_fechar:hover {
    background: #7A2A2A;
}
QComboBox {
    background: #252540;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    min-width: 100px;
}
QComboBox:hover {
    border-color: #89B4FA;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #89B4FA;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #252540;
    color: #CDD6F4;
    selection-background-color: #45475A;
    border: 1px solid #313244;
    outline: 0;
}
QLineEdit {
    background: #252540;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #89B4FA;
}
QFrame#separador {
    background: #313244;
    max-height: 1px;
}
"""


# =============================================================================
# PinEditorDialog
# =============================================================================
class PinEditorDialog(QDialog):
    """
    Diálogo para edição visual de pin_names e pin_types.

    Parâmetros
    ----------
    dados : dict
        Dicionário YAML do componente (já parseado).
    filepath : str
        Caminho do arquivo YAML no disco.
    parent : QWidget, opcional
        Widget pai.
    """

    def __init__(self, dados: dict, filepath: str, parent=None):
        super().__init__(parent)
        self._dados    = dados
        self._filepath = filepath
        self._pads     = []           # lista de PadInfo
        self._crescente = True        # direção de numeração

        self.setWindowTitle('📌  Editor de Pinagem')
        self.setMinimumSize(700, 500)
        self.resize(900, 620)
        self.setStyleSheet(_STYLE)

        self._setup_ui()
        self._carregar_pads()

    # =========================================================================
    # UI
    # =========================================================================
    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(14, 10, 14, 10)
        main.setSpacing(8)

        # ── Título ───────────────────────────────────────────────────────────
        titulo = QLabel('📌  Editor de Pinagem')
        titulo.setObjectName('lbl_titulo')
        titulo.setFont(QFont('Segoe UI', 14, QFont.Bold))
        main.addWidget(titulo)

        # ── Seção de Configuração ────────────────────────────────────────────
        cfg_frame = QFrame()
        cfg_frame.setStyleSheet(
            'QFrame { background: #181825; border: 1px solid #313244;'
            '         border-radius: 6px; padding: 8px; }')
        cfg_layout = QVBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(10, 6, 10, 6)
        cfg_layout.setSpacing(4)

        # Total de pinos
        self.lbl_total = QLabel('Total de pinos: —')
        self.lbl_total.setObjectName('lbl_secao')
        cfg_layout.addWidget(self.lbl_total)

        # Pinos por lado
        self.lbl_lados = QLabel('Pinos por lado: E=0  B=0  D=0  T=0')
        self.lbl_lados.setObjectName('lbl_secao')
        cfg_layout.addWidget(self.lbl_lados)

        # Separador interno
        sep_cfg = QFrame()
        sep_cfg.setObjectName('separador')
        sep_cfg.setFrameShape(QFrame.HLine)
        cfg_layout.addWidget(sep_cfg)

        # Direção
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(10)
        lbl_dir = QLabel('Direção:')
        lbl_dir.setStyleSheet('font-weight: bold; color: #89B4FA;')
        dir_layout.addWidget(lbl_dir)

        self.radio_crescente  = QRadioButton('Crescente (1→N)')
        self.radio_decrescente = QRadioButton('Decrescente (N→1)')
        self.radio_crescente.setChecked(True)

        self._dir_group = QButtonGroup(self)
        self._dir_group.addButton(self.radio_crescente, 0)
        self._dir_group.addButton(self.radio_decrescente, 1)
        self._dir_group.buttonClicked.connect(self._on_direcao_changed)

        dir_layout.addWidget(self.radio_crescente)
        dir_layout.addWidget(self.radio_decrescente)
        dir_layout.addStretch()
        cfg_layout.addLayout(dir_layout)

        main.addWidget(cfg_frame)

        # ── Separador ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName('separador')
        sep.setFrameShape(QFrame.HLine)
        main.addWidget(sep)

        # ── Tabela ───────────────────────────────────────────────────────────
        self.tabela = QTableWidget()
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels([
            'Pin', 'Nome', 'Lado', 'Tipo Elétrico', 'Posição (mm)',
        ])
        self.tabela.setFont(QFont('Consolas', 10))
        self.tabela.verticalHeader().setVisible(False)

        # Larguras das colunas
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.tabela.setColumnWidth(0, 50)
        self.tabela.setColumnWidth(2, 80)
        self.tabela.setColumnWidth(3, 150)
        self.tabela.setColumnWidth(4, 140)

        main.addWidget(self.tabela, stretch=1)

        # ── Botões de Ação ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_salvar = QPushButton('💾  Salvar no YAML')
        self.btn_salvar.setObjectName('btn_salvar')
        self.btn_salvar.setToolTip('Escreve pin_names e pin_types no arquivo YAML')
        self.btn_salvar.clicked.connect(self._salvar_yaml)

        self.btn_auto = QPushButton('🔄  Auto-numerar')
        self.btn_auto.setToolTip('Preenche nomes como Pin_1, Pin_2, ...')
        self.btn_auto.clicked.connect(self._auto_numerar)

        self.btn_colar = QPushButton('📋  Colar do Excel')
        self.btn_colar.setToolTip('Lê clipboard no formato "nome\\ttipo" por linha')
        self.btn_colar.clicked.connect(self._colar_excel)

        self.btn_nc = QPushButton('📑  Preencher NC')
        self.btn_nc.setToolTip('Preenche campos de nome vazios com "NC"')
        self.btn_nc.clicked.connect(self._preencher_nc)

        self.btn_inverter = QPushButton('🔀  Inverter ordem')
        self.btn_inverter.setToolTip('Inverte a numeração dos pinos')
        self.btn_inverter.clicked.connect(self._inverter_ordem)

        self.btn_fechar = QPushButton('❌  Fechar')
        self.btn_fechar.setObjectName('btn_fechar')
        self.btn_fechar.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_salvar)
        btn_layout.addWidget(self.btn_auto)
        btn_layout.addWidget(self.btn_colar)
        btn_layout.addWidget(self.btn_nc)
        btn_layout.addWidget(self.btn_inverter)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_fechar)

        main.addLayout(btn_layout)

    # =========================================================================
    # Carregar pads e preencher tabela
    # =========================================================================
    def _carregar_pads(self):
        """Calcula pads via geometria_pads e preenche a tabela."""
        try:
            self._pads = calcular_pads(self._dados)
        except Exception as e:
            QMessageBox.warning(
                self, 'Erro ao calcular pads',
                f'Não foi possível calcular a geometria de pads:\n\n{e}')
            self._pads = []

        # Contar lados
        n_por_lado = {'esquerdo': 0, 'base': 0, 'direito': 0, 'topo': 0}
        for p in self._pads:
            n_por_lado[p.lado] = n_por_lado.get(p.lado, 0) + 1

        total = len(self._pads)
        self.lbl_total.setText(f'Total de pinos: {total}')
        self.lbl_lados.setText(
            f'Pinos por lado:  E={n_por_lado["esquerdo"]}  '
            f'B={n_por_lado["base"]}  '
            f'D={n_por_lado["direito"]}  '
            f'T={n_por_lado["topo"]}')

        # Nomes e tipos existentes no YAML
        pin_names = self._dados.get('pin_names', {})
        pin_types = self._dados.get('pin_types', {})

        self._preencher_tabela(pin_names, pin_types)

    def _preencher_tabela(self, pin_names: dict, pin_types: dict):
        """Popula as linhas da tabela com os dados de pads."""
        pads = self._pads
        if not self._crescente:
            pads = list(reversed(pads))

        self.tabela.setRowCount(len(pads))

        for row, pad in enumerate(pads):
            num_str = str(pad.num)

            # ── Col 0: Pin (read-only) ───────────────────────────────────
            item_pin = QTableWidgetItem(num_str)
            item_pin.setFlags(item_pin.flags() & ~Qt.ItemIsEditable)
            item_pin.setTextAlignment(Qt.AlignCenter)
            item_pin.setForeground(QColor('#89B4FA'))
            item_pin.setFont(QFont('Consolas', 10, QFont.Bold))
            self.tabela.setItem(row, 0, item_pin)

            # ── Col 1: Nome (editável) ───────────────────────────────────
            nome = str(pin_names.get(num_str, pin_names.get(pad.num, '')))
            item_nome = QTableWidgetItem(nome)
            item_nome.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.tabela.setItem(row, 1, item_nome)

            # ── Col 2: Lado (read-only) ──────────────────────────────────
            lado_txt = _LADO_DISPLAY.get(pad.lado, pad.lado)
            item_lado = QTableWidgetItem(lado_txt)
            item_lado.setFlags(item_lado.flags() & ~Qt.ItemIsEditable)
            item_lado.setTextAlignment(Qt.AlignCenter)
            item_lado.setForeground(QColor('#A6ADC8'))
            self.tabela.setItem(row, 2, item_lado)

            # ── Col 3: Tipo Elétrico (ComboBox) ──────────────────────────
            tipo_atual = str(pin_types.get(num_str, pin_types.get(pad.num, 'bidirectional')))
            combo = QComboBox()
            combo.addItems(_TIPOS_ELETRICOS)
            idx = combo.findText(tipo_atual)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentText('bidirectional')
            self.tabela.setCellWidget(row, 3, combo)

            # ── Col 4: Posição (read-only) ───────────────────────────────
            pos_txt = f'x={pad.x:.2f}, y={pad.y:.2f} mm'
            item_pos = QTableWidgetItem(pos_txt)
            item_pos.setFlags(item_pos.flags() & ~Qt.ItemIsEditable)
            item_pos.setTextAlignment(Qt.AlignCenter)
            item_pos.setForeground(QColor('#6C7086'))
            self.tabela.setItem(row, 4, item_pos)

            # Altura das linhas
            self.tabela.setRowHeight(row, 30)

    # =========================================================================
    # Ler dados atuais da tabela
    # =========================================================================
    def _ler_tabela(self):
        """Retorna (nomes, tipos) lidos da tabela."""
        nomes = {}
        tipos = {}
        for row in range(self.tabela.rowCount()):
            pin_item = self.tabela.item(row, 0)
            if not pin_item:
                continue
            num = pin_item.text()

            # Nome
            nome_item = self.tabela.item(row, 1)
            nome = nome_item.text().strip() if nome_item else ''
            if nome:
                nomes[num] = nome

            # Tipo
            combo = self.tabela.cellWidget(row, 3)
            tipo = combo.currentText() if combo else 'bidirectional'
            tipos[num] = tipo

        return nomes, tipos

    # =========================================================================
    # Ações
    # =========================================================================
    def _salvar_yaml(self):
        """Escreve pin_names e pin_types no arquivo YAML."""
        nomes, tipos = self._ler_tabela()

        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                conteudo = yaml.safe_load(f)

            conteudo['pin_names'] = {
                str(num): nome for num, nome in nomes.items() if nome
            }
            conteudo['pin_types'] = {
                str(num): tipo for num, tipo in tipos.items()
                if tipo != 'bidirectional'
            }

            with open(self._filepath, 'w', encoding='utf-8') as f:
                yaml.dump(conteudo, f,
                          allow_unicode=True,
                          default_flow_style=False,
                          sort_keys=False)

            QMessageBox.information(
                self, 'Salvo',
                f'pin_names ({len(conteudo["pin_names"])}) e '
                f'pin_types ({len(conteudo["pin_types"])}) '
                f'salvos em:\n{self._filepath}')

        except Exception as e:
            QMessageBox.critical(
                self, 'Erro ao salvar',
                f'Não foi possível salvar no YAML:\n\n{e}')

    def _auto_numerar(self):
        """Preenche nomes como Pin_1, Pin_2, ..."""
        for row in range(self.tabela.rowCount()):
            pin_item = self.tabela.item(row, 0)
            if pin_item:
                num = pin_item.text()
                nome_item = self.tabela.item(row, 1)
                if nome_item:
                    nome_item.setText(f'Pin_{num}')

    def _colar_excel(self):
        """Lê clipboard no formato 'nome\\ttipo' por linha."""
        texto = QApplication.clipboard().text()
        if not texto or not texto.strip():
            QMessageBox.information(
                self, 'Colar do Excel',
                'A área de transferência está vazia.\n\n'
                'Copie do Excel no formato:\n'
                '  nome<TAB>tipo\n'
                '(uma linha por pino)')
            return

        linhas = texto.strip().split('\n')
        colados = 0
        for i, linha in enumerate(linhas):
            if i >= self.tabela.rowCount():
                break
            partes = linha.strip().split('\t')
            nome = partes[0].strip() if len(partes) >= 1 else ''
            tipo = partes[1].strip() if len(partes) >= 2 else ''

            # Nome
            nome_item = self.tabela.item(i, 1)
            if nome_item and nome:
                nome_item.setText(nome)
                colados += 1

            # Tipo (se fornecido e válido)
            if tipo:
                combo = self.tabela.cellWidget(i, 3)
                if combo:
                    idx = combo.findText(tipo)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

        QMessageBox.information(
            self, 'Colar do Excel',
            f'Colados {colados} nomes de {len(linhas)} linhas do clipboard.')

    def _preencher_nc(self):
        """Preenche campos de nome vazios com 'NC'."""
        preenchidos = 0
        for row in range(self.tabela.rowCount()):
            nome_item = self.tabela.item(row, 1)
            if nome_item and not nome_item.text().strip():
                nome_item.setText('NC')
                preenchidos += 1

        QMessageBox.information(
            self, 'Preencher NC',
            f'{preenchidos} pinos preenchidos com "NC".')

    def _inverter_ordem(self):
        """Inverte a numeração dos nomes na tabela."""
        nomes, tipos = self._ler_tabela()

        # Inverter associação: pin N recebe o nome do pin 1, etc.
        pins = sorted(nomes.keys(), key=lambda x: int(x))
        valores_nomes = [nomes.get(p, '') for p in pins]
        valores_nomes.reverse()

        pins_tipos = sorted(tipos.keys(), key=lambda x: int(x))
        valores_tipos = [tipos.get(p, 'bidirectional') for p in pins_tipos]
        valores_tipos.reverse()

        # Re-aplicar na tabela
        for row in range(self.tabela.rowCount()):
            if row < len(valores_nomes):
                nome_item = self.tabela.item(row, 1)
                if nome_item:
                    nome_item.setText(valores_nomes[row])
            if row < len(valores_tipos):
                combo = self.tabela.cellWidget(row, 3)
                if combo:
                    idx = combo.findText(valores_tipos[row])
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

    def _on_direcao_changed(self, button):
        """Altera a ordem de exibição na tabela."""
        self._crescente = (self._dir_group.id(button) == 0)
        # Re-ler dados atuais antes de reconstruir
        nomes_atuais, tipos_atuais = self._ler_tabela()
        self._preencher_tabela(nomes_atuais, tipos_atuais)


# =============================================================================
# Teste standalone
# =============================================================================
if __name__ == '__main__':
    import sys
    import os

    app = QApplication(sys.argv)

    # Tentar carregar um YAML de exemplo
    test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modulos_config')
    test_files = [f for f in os.listdir(test_dir)
                  if f.endswith('.yaml')] if os.path.isdir(test_dir) else []

    if test_files:
        test_path = os.path.join(test_dir, test_files[0])
        with open(test_path, 'r', encoding='utf-8') as f:
            dados = yaml.safe_load(f)
        dlg = PinEditorDialog(dados, test_path)
        dlg.exec_()
    else:
        print('Nenhum YAML encontrado em modulos_config/ para teste.')
        sys.exit(1)
