# =============================================================================
# gui/wizard_componente.py
# Wizard de criação de componente — Plataforma CAM-CAD Data Frontier
#
# QWizard com 4 páginas:
#   1. Tipo do componente
#   2. Dimensões (campos dinâmicos conforme tipo)
#   3. Pinagem (tabela editável)
#   4. Revisão (preview YAML + salvar)
# =============================================================================

import os
import yaml

from PyQt5.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QRadioButton, QButtonGroup, QDoubleSpinBox, QSpinBox,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QFileDialog, QPushButton, QGroupBox, QHeaderView,
    QAbstractItemView, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


# ── Estilos ──────────────────────────────────────────────────────────────────
_WIZARD_STYLE = '''
QWizard {
    background-color: #1E1E2E;
}
QWizardPage {
    background-color: #1E1E2E;
    color: #CDD6F4;
}
QLabel {
    color: #CDD6F4;
    font-size: 12px;
}
QRadioButton {
    color: #CDD6F4;
    font-size: 12px;
    spacing: 8px;
    padding: 4px 0;
}
QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 2px solid #45475A;
    border-radius: 9px;
    background: #181825;
}
QRadioButton::indicator:checked {
    background: #89B4FA;
    border-color: #89B4FA;
}
QRadioButton::indicator:hover {
    border-color: #89B4FA;
}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    font-family: Consolas, monospace;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #89B4FA;
}
QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #181825;
    color: #CDD6F4;
    selection-background-color: #313244;
    border: 1px solid #45475A;
}
QTextEdit {
    background-color: #181825;
    color: #A6E3A1;
    border: 1px solid #45475A;
    border-radius: 4px;
    font-family: Consolas, monospace;
    font-size: 11px;
    padding: 8px;
}
QTableWidget {
    background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    gridline-color: #313244;
    font-size: 11px;
    font-family: Consolas, monospace;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background-color: #313244;
}
QHeaderView::section {
    background-color: #313244;
    color: #CDD6F4;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #45475A;
    border-bottom: 1px solid #45475A;
    font-size: 11px;
    font-weight: bold;
}
QGroupBox {
    color: #89B4FA;
    border: 1px solid #45475A;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 18px;
    font-size: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #45475A;
}
QPushButton:pressed {
    background-color: #585B70;
}
'''


# ── Definições de tipos de componente ────────────────────────────────────────

COMPONENT_TYPES = [
    ('smd_passivo',  'SMD Passivo (0402–1206)'),
    ('ci_dip',       'CI DIP'),
    ('ci_soic',      'CI SOIC / SSOP'),
    ('sot23',        'SOT-23'),
    ('qfn_qfp',      'QFN / QFP'),
    ('bga',          'BGA'),
    ('conector_pth', 'Conector PTH'),
    ('custom',       'Custom'),
]

# Campos de dimensão por tipo: (key, label, default, decimals, min, max)
_DIM_FIELDS = {
    'smd_passivo': [
        ('largura',        'Largura (mm)',          1.0,  2, 0.1,  50.0),
        ('comprimento',    'Comprimento (mm)',      0.5,  2, 0.1,  50.0),
        ('pad_largura',    'Pad Largura (mm)',      0.6,  2, 0.1,  20.0),
        ('pad_comprimento','Pad Comprimento (mm)',  0.5,  2, 0.1,  20.0),
        ('afastamento',    'Afastamento (mm)',      0.8,  2, 0.0,  50.0),
    ],
    'ci_dip': [
        ('total_pinos', 'Total de Pinos',                8,    0, 2,   64),
        ('pitch',       'Pitch (mm)',                    2.54,  2, 0.5, 5.08),
        ('largura',     'Largura Corpo (mm)',            6.35,  2, 1.0, 30.0),
        ('afastamento', 'Afastamento Fileiras (mm)',     7.62,  2, 2.0, 30.0),
    ],
    'ci_soic': [
        ('total_pinos', 'Total de Pinos',               16,    0, 4,   64),
        ('pitch',       'Pitch (mm)',                    1.27,  2, 0.4, 2.54),
        ('largura',     'Largura Corpo (mm)',            3.9,   2, 1.0, 20.0),
        ('afastamento', 'Afastamento (mm)',              5.9,   2, 2.0, 20.0),
    ],
    'sot23': [
        ('total_pinos',    'Total de Pinos',             3,    0, 3,   8),
        ('pitch',          'Pitch (mm)',                 0.95, 2, 0.5, 2.0),
        ('pad_largura',    'Pad Largura (mm)',           0.6,  2, 0.1, 5.0),
        ('pad_comprimento','Pad Comprimento (mm)',       1.0,  2, 0.1, 5.0),
    ],
    'qfn_qfp': [
        ('total_pinos',    'Total de Pinos',            32,    0, 4,   256),
        ('pitch',          'Pitch (mm)',                 0.5,  2, 0.2, 1.27),
        ('corpo',          'Corpo (mm)',                 5.0,  2, 1.0, 40.0),
        ('pad_largura',    'Pad Largura (mm)',           0.3,  2, 0.1, 5.0),
        ('pad_comprimento','Pad Comprimento (mm)',       0.8,  2, 0.1, 5.0),
        ('exposed_pad',   'Exposed Pad (mm)',            3.0,  2, 0.0, 30.0),
    ],
    'bga': [
        ('linhas',    'Linhas',                          6,    0, 2,   40),
        ('colunas',   'Colunas',                         6,    0, 2,   40),
        ('pitch',     'Pitch (mm)',                      0.8,  2, 0.3, 1.5),
        ('corpo',     'Corpo (mm)',                      5.0,  2, 1.0, 60.0),
        ('ball_diam', 'Diâmetro Ball (mm)',              0.4,  2, 0.1, 2.0),
    ],
    'conector_pth': [
        ('total_pinos', 'Total de Pinos',               10,   0, 1,   200),
        ('fileiras',    'Fileiras',                      2,    0, 1,   4),
        ('pitch',       'Pitch (mm)',                    2.54, 2, 0.5, 5.08),
        ('furo_diam',   'Diâmetro Furo (mm)',            1.0,  2, 0.3, 3.0),
        ('pad_diam',    'Diâmetro Pad (mm)',             1.7,  2, 0.5, 5.0),
    ],
    'custom': [
        ('total_pinos', 'Total de Pinos',                4,    0, 1,   500),
        ('pitch',       'Pitch (mm)',                    1.27, 2, 0.1, 10.0),
        ('largura',     'Largura Corpo (mm)',            5.0,  2, 0.1, 200.0),
        ('comprimento', 'Comprimento Corpo (mm)',        5.0,  2, 0.1, 200.0),
    ],
}

# Presets de pinagem
_PIN_TYPES = ['I/O', 'Input', 'Output', 'Power', 'GND', 'Clock', 'NC', 'Analog']

_PIN_PRESETS = {
    'ic': {
        'label': 'IC (VCC/GND)',
        'mapping': lambda n: [
            ('VCC' if i == 0 else 'GND' if i == n - 1 else f'P{i}',
             'Power' if i == 0 or i == n - 1 else 'I/O')
            for i in range(n)
        ],
    },
    'transistor': {
        'label': 'Transistor (B/C/E)',
        'mapping': lambda n: [
            ('Base', 'Input'),
            ('Coletor', 'Output'),
            ('Emissor', 'Power'),
        ][:n],
    },
    'passivo': {
        'label': 'Passivo (1/2)',
        'mapping': lambda n: [
            (str(i + 1), 'I/O') for i in range(n)
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Page 1 — Tipo do Componente
# ═══════════════════════════════════════════════════════════════════════════════

class PageTipo(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Tipo do Componente')
        self.setSubTitle('Selecione a categoria do componente que deseja criar.')

        lay = QVBoxLayout(self)
        lay.setSpacing(6)
        lay.setContentsMargins(24, 16, 24, 16)

        self._btn_group = QButtonGroup(self)
        self._radios = {}

        for idx, (key, label) in enumerate(COMPONENT_TYPES):
            rb = QRadioButton(label)
            rb.setFont(QFont('Segoe UI', 11))
            self._btn_group.addButton(rb, idx)
            self._radios[key] = rb
            lay.addWidget(rb)

        # ── Símbolo esquemático ──
        lay.addSpacing(12)
        simbolo_lay = QHBoxLayout()
        lbl_simbolo = QLabel('Símbolo Esquemático:')
        lbl_simbolo.setFont(QFont('Segoe UI', 11))
        simbolo_lay.addWidget(lbl_simbolo)

        self._combo_simbolo = QComboBox()
        self._combo_simbolo.setMinimumWidth(220)
        _SIMBOLO_OPTIONS = [
            ('(auto-detectar)',  '(auto-detectar)'),
            ('resistor',        'Resistor (retângulo passivo)'),
            ('capacitor',       'Capacitor (placas paralelas)'),
            ('diodo',           'Diodo (triângulo + barra)'),
            ('diodo_zener',     'Diodo Zener'),
            ('diodo_schottky',  'Diodo Schottky'),
            ('led',             'LED (diodo + setas)'),
            ('transistor',      'Transistor NPN'),
            ('mosfet_n',        'MOSFET Canal N'),
            ('mosfet_p',        'MOSFET Canal P'),
            ('regulador',       'Regulador de Tensão (IN/GND/OUT)'),
            ('opamp',           'Amplificador Operacional'),
            ('indutor',         'Indutor/Bobina'),
            ('fusivel',         'Fusível'),
            ('bateria',         'Bateria'),
            ('antena',          'Antena'),
            ('crystal',         'Cristal/Oscilador'),
            ('conector',        'Conector'),
            ('ci',              'CI Genérico'),
            ('bga',             'BGA (4 lados)'),
        ]
        for key, label in _SIMBOLO_OPTIONS:
            self._combo_simbolo.addItem(label, key)
        simbolo_lay.addWidget(self._combo_simbolo)
        simbolo_lay.addStretch()
        lay.addLayout(simbolo_lay)

        lay.addStretch()

        # Selecionar primeiro por padrão
        self._radios['smd_passivo'].setChecked(True)

    def get_tipo_key(self):
        idx = self._btn_group.checkedId()
        if 0 <= idx < len(COMPONENT_TYPES):
            return COMPONENT_TYPES[idx][0]
        return 'custom'

    def get_simbolo_key(self):
        """Retorna a chave do símbolo selecionado, ou None para auto-detectar."""
        key = self._combo_simbolo.currentData()
        if key == '(auto-detectar)':
            return None
        return key

    def validatePage(self):
        return self._btn_group.checkedId() >= 0


# ═══════════════════════════════════════════════════════════════════════════════
#  Page 2 — Dimensões
# ═══════════════════════════════════════════════════════════════════════════════

class PageDimensoes(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Dimensões do Componente')
        self.setSubTitle('Defina as dimensões físicas do componente.')

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(24, 16, 24, 16)

        # Label de diagrama simples
        self._diagram_label = QLabel()
        self._diagram_label.setAlignment(Qt.AlignCenter)
        self._diagram_label.setStyleSheet(
            'color:#89DCEB; font-family:Consolas; font-size:11px; '
            'background:#181825; border:1px solid #45475A; border-radius:6px; '
            'padding:12px; margin-bottom:8px;'
        )
        self._main_layout.addWidget(self._diagram_label)

        # Grupo de dimensões (será recriado ao initializePage)
        self._dims_group = QGroupBox('Dimensões')
        self._dims_layout = QGridLayout(self._dims_group)
        self._dims_layout.setSpacing(8)
        self._main_layout.addWidget(self._dims_group)
        self._main_layout.addStretch()

        self._spinboxes = {}

    def initializePage(self):
        tipo = self.wizard()._page_tipo.get_tipo_key()
        fields = _DIM_FIELDS.get(tipo, _DIM_FIELDS['custom'])

        # Limpar widgets anteriores
        while self._dims_layout.count():
            item = self._dims_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._spinboxes.clear()

        # Criar campos
        for row, (key, label, default, decimals, vmin, vmax) in enumerate(fields):
            lbl = QLabel(label)
            if decimals > 0:
                sb = QDoubleSpinBox()
                sb.setDecimals(decimals)
                sb.setRange(vmin, vmax)
                sb.setValue(default)
                sb.setSuffix('')
            else:
                sb = QSpinBox()
                sb.setRange(int(vmin), int(vmax))
                sb.setValue(int(default))
            sb.setMinimumWidth(120)
            self._dims_layout.addWidget(lbl, row, 0)
            self._dims_layout.addWidget(sb, row, 1)
            self._spinboxes[key] = sb

        # Diagrama simples
        diagrams = {
            'smd_passivo':  '┌───────┐\n│  PAD  │──gap──│  PAD  │\n└───────┘',
            'ci_dip':       '  ┌──U──┐\n  │1    N│\n  │2  N-1│\n  │...  .│\n  └──────┘',
            'ci_soic':      '  ┌──U──┐\n  ╶1    N╶\n  ╶2  N-1╶\n  └──────┘',
            'sot23':        '   ┌─┐\n  1┤ ├2\n   └┬┘\n    3',
            'qfn_qfp':      '  ┌──────┐\n ─┤      ├─\n ─┤  EP  ├─\n  └──┬┬──┘',
            'bga':          '  ● ● ● ●\n  ● ● ● ●\n  ● ● ● ●\n  ● ● ● ●',
            'conector_pth': '  ○ ○ ○ ○\n  ○ ○ ○ ○',
            'custom':       '  ┌──────┐\n  │Custom│\n  └──────┘',
        }
        self._diagram_label.setText(diagrams.get(tipo, ''))

    def get_dimensions(self):
        return {key: sb.value() for key, sb in self._spinboxes.items()}


# ═══════════════════════════════════════════════════════════════════════════════
#  Page 3 — Pinagem
# ═══════════════════════════════════════════════════════════════════════════════

class PagePinagem(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Pinagem')
        self.setSubTitle('Configure os pinos do componente.')

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)

        # Toolbar de presets
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('Preset:'))
        for preset_key, preset_info in _PIN_PRESETS.items():
            btn = QPushButton(preset_info['label'])
            btn.clicked.connect(lambda checked, k=preset_key: self._apply_preset(k))
            toolbar.addWidget(btn)
        toolbar.addStretch()

        btn_add = QPushButton('+ Adicionar Pino')
        btn_add.clicked.connect(self._add_row)
        btn_remove = QPushButton('− Remover Pino')
        btn_remove.clicked.connect(self._remove_row)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_remove)
        lay.addLayout(toolbar)

        # Tabela
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(['Número', 'Nome', 'Tipo'])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            self._table.styleSheet() +
            'QTableWidget { alternate-background-color: #1E1E2E; }'
        )
        lay.addWidget(self._table)

    def initializePage(self):
        dims = self.wizard()._page_dims.get_dimensions()
        tipo = self.wizard()._page_tipo.get_tipo_key()

        # Determinar quantidade de pinos
        if tipo == 'smd_passivo':
            n_pins = 2
        elif tipo == 'bga':
            n_pins = dims.get('linhas', 6) * dims.get('colunas', 6)
        elif tipo == 'sot23':
            n_pins = int(dims.get('total_pinos', 3))
        else:
            n_pins = int(dims.get('total_pinos', 4))

        # Auto-populate
        self._table.setRowCount(0)
        for i in range(n_pins):
            self._add_row(num=i + 1, name=f'P{i + 1}', pin_type='I/O')

    def _add_row(self, num=None, name='', pin_type='I/O'):
        row = self._table.rowCount()
        self._table.insertRow(row)

        if num is None:
            num = row + 1

        # Número
        item_num = QTableWidgetItem(str(num))
        item_num.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 0, item_num)

        # Nome
        item_name = QTableWidgetItem(name)
        self._table.setItem(row, 1, item_name)

        # Tipo (dropdown)
        combo = QComboBox()
        combo.addItems(_PIN_TYPES)
        if pin_type in _PIN_TYPES:
            combo.setCurrentText(pin_type)
        self._table.setCellWidget(row, 2, combo)

    def _remove_row(self):
        rows = set(idx.row() for idx in self._table.selectedIndexes())
        for row in sorted(rows, reverse=True):
            self._table.removeRow(row)

    def _apply_preset(self, preset_key):
        n = self._table.rowCount()
        if n == 0:
            n = 4
        mapping = _PIN_PRESETS[preset_key]['mapping'](n)

        self._table.setRowCount(0)
        for i, (name, ptype) in enumerate(mapping):
            self._add_row(num=i + 1, name=name, pin_type=ptype)

    def get_pins(self):
        pins = []
        for row in range(self._table.rowCount()):
            item_num = self._table.item(row, 0)
            item_name = self._table.item(row, 1)
            combo = self._table.cellWidget(row, 2)
            pins.append({
                'numero': int(item_num.text()) if item_num else row + 1,
                'nome':   item_name.text() if item_name else f'P{row + 1}',
                'tipo':   combo.currentText() if combo else 'I/O',
            })
        return pins


# ═══════════════════════════════════════════════════════════════════════════════
#  Page 4 — Revisão
# ═══════════════════════════════════════════════════════════════════════════════

class PageRevisao(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Revisão e Exportação')
        self.setSubTitle('Revise a configuração e salve o componente.')

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)

        # Nome do componente
        name_lay = QHBoxLayout()
        name_lay.addWidget(QLabel('Nome do Componente:'))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('ex: MeuComponente_SOIC16')
        name_lay.addWidget(self._name_edit)
        lay.addLayout(name_lay)

        # Diretório de saída
        dir_lay = QHBoxLayout()
        dir_lay.addWidget(QLabel('Diretório de Saída:'))
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText('modulos_config')
        dir_lay.addWidget(self._dir_edit)
        btn_browse = QPushButton('...')
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_dir)
        dir_lay.addWidget(btn_browse)
        lay.addLayout(dir_lay)

        # Preview YAML
        lbl_preview = QLabel('Preview YAML:')
        lbl_preview.setStyleSheet('font-weight:bold; color:#89B4FA; margin-top:8px;')
        lay.addWidget(lbl_preview)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFont(QFont('Consolas', 10))
        lay.addWidget(self._preview)

    def initializePage(self):
        wizard = self.wizard()
        tipo_key = wizard._page_tipo.get_tipo_key()

        # Sugerir nome
        tipo_label = dict(COMPONENT_TYPES).get(tipo_key, 'Custom')
        suggested = tipo_label.replace(' ', '_').replace('/', '-')
        if not self._name_edit.text():
            self._name_edit.setText(suggested)

        # Diretório padrão
        if not self._dir_edit.text():
            default_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'modulos_config'
            )
            self._dir_edit.setText(default_dir)

        # Gerar preview
        data = self._build_yaml_data()
        yaml_str = yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        self._preview.setPlainText(yaml_str)

    def _build_yaml_data(self):
        wizard = self.wizard()
        tipo_key = wizard._page_tipo.get_tipo_key()
        dims = wizard._page_dims.get_dimensions()
        pins = wizard._page_pins.get_pins()
        comp_name = self._name_edit.text() or 'SemNome'
        tipo_label = dict(COMPONENT_TYPES).get(tipo_key, tipo_key)

        # ── Build flat YAML matching generator expected format ──
        data = {
            'nome': comp_name,
            'tipo': tipo_key,
        }

        # ── Símbolo esquemático (apenas se selecionado) ──
        simbolo = wizard._page_tipo.get_simbolo_key()
        if simbolo:
            data['simbolo'] = simbolo

        # ── Pinos section ──
        pinos = {}
        total_pinos = dims.pop('total_pinos', None)
        if total_pinos is not None:
            pinos['total'] = int(total_pinos)
        pitch = dims.pop('pitch', None)
        if pitch is not None:
            pinos['pitch'] = pitch
        # Pad dimensions
        pad_largura = dims.pop('pad_largura', None)
        pad_comprimento = dims.pop('pad_comprimento', None)
        if pad_largura is not None or pad_comprimento is not None:
            tamanho_pad = {}
            if pad_largura is not None:
                tamanho_pad['largura'] = pad_largura
            if pad_comprimento is not None:
                tamanho_pad['altura'] = pad_comprimento
            pinos['tamanho_pad'] = tamanho_pad
        # Drill / pad diameters (THT)
        furo_diam = dims.pop('furo_diam', None)
        pad_diam = dims.pop('pad_diam', None)
        if furo_diam is not None:
            pinos['diametro_furo'] = furo_diam
        if pad_diam is not None:
            pinos['diametro_pad'] = pad_diam
        # SMD passive spacing
        afastamento = dims.pop('afastamento', None)
        if afastamento is not None:
            pinos['espacamento'] = afastamento
        if pinos:
            data['pinos'] = pinos

        # ── Corpo section (remaining dims) ──
        corpo = {}
        for k, v in dims.items():
            corpo[k] = v
        if corpo:
            data['corpo'] = corpo

        # ── Margens (defaults) ──
        data['margens'] = {
            'courtyard': 0.25,
            'silkscreen': 0.12,
            'fab_line': 0.10,
        }

        # ── KiCad metadata ──
        # Infer reference designator prefix from type
        ref_map = {
            'smd_passivo': 'R?', 'ci_dip': 'U?', 'ci_soic': 'U?',
            'sot23': 'Q?', 'qfn_qfp': 'U?', 'bga': 'U?',
            'conector_pth': 'J?', 'custom': 'X?',
        }
        data['kicad'] = {
            'referencia': ref_map.get(tipo_key, 'X?'),
            'valor': comp_name,
            'descricao': f'{tipo_label} — {comp_name}',
            'tags': f'{tipo_key} {comp_name.lower().replace("_", " ")}',
        }

        # ── Pin names & types ──
        if pins:
            pin_names = {}
            pin_types = {}
            type_map = {
                'I/O': 'bidirectional', 'Input': 'input',
                'Output': 'output', 'Power': 'power_in',
                'GND': 'power_in', 'Clock': 'input',
                'NC': 'no_connect', 'Analog': 'passive',
            }
            for p in pins:
                num = p['numero']
                pin_names[num] = p['nome']
                pin_types[num] = type_map.get(p['tipo'], 'passive')
            data['pin_names'] = pin_names
            data['pin_types'] = pin_types

        return data

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, 'Selecionar Diretório de Saída')
        if d:
            self._dir_edit.setText(d)

    def get_output_path(self):
        name = self._name_edit.text().strip() or 'componente'
        name = name.replace(' ', '_')
        if not name.endswith('.yaml'):
            name += '.yaml'
        directory = self._dir_edit.text().strip()
        if not directory:
            directory = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'modulos_config'
            )
        return os.path.join(directory, name)

    def get_yaml_data(self):
        return self._build_yaml_data()

    def validatePage(self):
        if not self._name_edit.text().strip():
            QMessageBox.warning(
                self, 'Nome Obrigatório',
                'Informe um nome para o componente.'
            )
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  WizardComponente — Wizard principal
# ═══════════════════════════════════════════════════════════════════════════════

class WizardComponente(QWizard):
    """Wizard completo para criação de novos componentes."""

    sigComponenteCriado = pyqtSignal(str)   # caminho do .yaml criado

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Novo Componente — Wizard')
        self.setMinimumSize(680, 560)
        self.setStyleSheet(_WIZARD_STYLE)
        self.setWizardStyle(QWizard.ModernStyle)

        # Estilizar botões do wizard
        for btn_role in [QWizard.BackButton, QWizard.NextButton,
                         QWizard.FinishButton, QWizard.CancelButton]:
            btn = self.button(btn_role)
            if btn:
                btn.setStyleSheet(
                    'QPushButton { background:#313244; color:#CDD6F4; '
                    'border:1px solid #45475A; border-radius:4px; '
                    'padding:6px 18px; font-size:12px; }'
                    'QPushButton:hover { background:#45475A; }'
                    'QPushButton:pressed { background:#585B70; }'
                )

        # Traduzir botões
        self.setButtonText(QWizard.NextButton,   'Próximo ▸')
        self.setButtonText(QWizard.BackButton,   '◂ Voltar')
        self.setButtonText(QWizard.FinishButton, '✓ Criar Componente')
        self.setButtonText(QWizard.CancelButton, 'Cancelar')

        # Páginas
        self._page_tipo = PageTipo()
        self._page_dims = PageDimensoes()
        self._page_pins = PagePinagem()
        self._page_review = PageRevisao()

        self.addPage(self._page_tipo)
        self.addPage(self._page_dims)
        self.addPage(self._page_pins)
        self.addPage(self._page_review)

    def accept(self):
        """Ao clicar em Finalizar: salva o .yaml e emite sinal."""
        output_path = self._page_review.get_output_path()
        yaml_data = self._page_review.get_yaml_data()

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    yaml_data, f, default_flow_style=False,
                    allow_unicode=True, sort_keys=False
                )
            self.sigComponenteCriado.emit(output_path)
            super().accept()
        except Exception as e:
            QMessageBox.critical(
                self, 'Erro ao Salvar',
                f'Não foi possível salvar o componente:\n\n{type(e).__name__}: {e}'
            )
