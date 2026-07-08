"""Diálogo de configuração para geração de relatório técnico."""
import os
import yaml
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QCheckBox, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QComboBox, QDoubleSpinBox, QFileDialog, QProgressBar,
    QButtonGroup, QDialogButtonBox, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont


# =============================================================================
# Stylesheet — Dark Catppuccin Mocha
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
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-size: 12px;
    font-weight: bold;
    color: #CDD6F4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89B4FA;
}
QRadioButton, QCheckBox {
    color: #CDD6F4;
    spacing: 6px;
    font-size: 12px;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #45475A;
    border-radius: 3px;
    background: #181825;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QRadioButton::indicator:checked {
    background: #89B4FA;
    border-color: #89B4FA;
}
QCheckBox::indicator:checked {
    background: #89B4FA;
    border-color: #89B4FA;
}
QListWidget {
    background: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    font-size: 12px;
    alternate-background-color: #1E1E2E;
}
QListWidget::item {
    padding: 4px 6px;
}
QListWidget::item:selected {
    background: #313244;
}
QComboBox {
    background: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    min-width: 160px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #181825;
    color: #CDD6F4;
    selection-background-color: #313244;
    border: 1px solid #45475A;
}
QDoubleSpinBox {
    background: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QLineEdit {
    background: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QPushButton {
    background: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 5px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background: #45475A;
}
QPushButton:pressed {
    background: #585B70;
}
QPushButton#btn_gerar {
    background: #89B4FA;
    color: #1E1E2E;
    border: none;
    font-weight: bold;
    font-size: 13px;
    padding: 8px 28px;
    border-radius: 6px;
}
QPushButton#btn_gerar:hover {
    background: #B4BEFE;
}
QPushButton#btn_gerar:pressed {
    background: #74C7EC;
}
QPushButton#btn_cancelar {
    background: #313244;
    color: #CDD6F4;
}
QProgressBar {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    text-align: center;
    color: #CDD6F4;
    font-size: 11px;
    height: 18px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #89B4FA, stop:1 #B4BEFE);
    border-radius: 3px;
}
QFrame#separator {
    background: #313244;
    max-height: 1px;
}
"""


class DialogoRelatorio(QDialog):
    """Diálogo para configurar e gerar relatório técnico."""

    def __init__(self, yaml_editor=None, modulos_dir='', saida_dir='', parent=None):
        super().__init__(parent)
        self.yaml_editor = yaml_editor
        self.modulos_dir = modulos_dir
        self.saida_dir = saida_dir
        self._yaml_files = []

        self.setWindowTitle('Gerar Relatório Técnico')
        self.setMinimumSize(600, 700)
        self.setStyleSheet(_STYLE)
        self._setup_ui()
        self._load_yaml_list()
        self._connect_signals()

    # --------------------------------------------------------------------- UI
    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(18, 18, 18, 14)
        main_lay.setSpacing(12)

        # Title
        title = QLabel('🖨️  Gerar Relatório Técnico')
        title.setStyleSheet(
            'font-size:16px; font-weight:bold; color:#89B4FA; padding-bottom:2px;'
        )
        main_lay.addWidget(title)

        # ── Section 1: Mode ──────────────────────────────────────────────
        grp_modo = QGroupBox('Modo de Geração')
        lay_modo = QVBoxLayout(grp_modo)

        self.radio_atual = QRadioButton('Componente atual')
        self.radio_biblioteca = QRadioButton('Biblioteca inteira')
        self.radio_selecionar = QRadioButton('Selecionar componentes...')
        self.radio_atual.setChecked(True)

        self._modo_group = QButtonGroup(self)
        self._modo_group.addButton(self.radio_atual, 0)
        self._modo_group.addButton(self.radio_biblioteca, 1)
        self._modo_group.addButton(self.radio_selecionar, 2)

        lay_modo.addWidget(self.radio_atual)
        lay_modo.addWidget(self.radio_biblioteca)
        lay_modo.addWidget(self.radio_selecionar)
        main_lay.addWidget(grp_modo)

        # ── Section 2: Component list ────────────────────────────────────
        self.grp_lista = QGroupBox('Componentes')
        lay_lista = QVBoxLayout(self.grp_lista)

        self.list_yamls = QListWidget()
        self.list_yamls.setAlternatingRowColors(True)
        self.list_yamls.setMinimumHeight(110)
        lay_lista.addWidget(self.list_yamls)

        btn_row = QHBoxLayout()
        self.btn_sel_all = QPushButton('Selecionar Todos')
        self.btn_sel_none = QPushButton('Limpar Seleção')
        btn_row.addWidget(self.btn_sel_all)
        btn_row.addWidget(self.btn_sel_none)
        btn_row.addStretch()
        lay_lista.addLayout(btn_row)

        self.grp_lista.setEnabled(False)
        main_lay.addWidget(self.grp_lista)

        # ── Section 3: Content options ───────────────────────────────────
        grp_conteudo = QGroupBox('Conteúdo do Relatório')
        lay_cont = QVBoxLayout(grp_conteudo)

        self.chk_footprint = QCheckBox('Footprint 2D com réguas')
        self.chk_footprint.setChecked(True)

        self.chk_modelo3d = QCheckBox('Modelo 3D')
        self.chk_modelo3d.setChecked(True)

        # Sub-option for 3D mode
        lay_3d = QHBoxLayout()
        lay_3d.setContentsMargins(26, 0, 0, 0)
        self.lbl_3d_modo = QLabel('Modo:')
        self.cmb_3d_modo = QComboBox()
        self.cmb_3d_modo.addItem('Captura da viewport', 'viewport')
        self.cmb_3d_modo.addItem('Renderização offline', 'offline')
        lay_3d.addWidget(self.lbl_3d_modo)
        lay_3d.addWidget(self.cmb_3d_modo)
        lay_3d.addStretch()

        self.chk_simbolo = QCheckBox('Símbolo esquemático')
        self.chk_simbolo.setChecked(True)

        self.chk_specs = QCheckBox('Tabela de especificações')
        self.chk_specs.setChecked(True)

        self.chk_pinagem = QCheckBox('Tabela de pinagem')
        self.chk_pinagem.setChecked(True)

        self.chk_validacao = QCheckBox('Validação IPC / DRC')
        self.chk_validacao.setChecked(True)

        lay_cont.addWidget(self.chk_footprint)
        lay_cont.addWidget(self.chk_modelo3d)
        lay_cont.addLayout(lay_3d)
        lay_cont.addWidget(self.chk_simbolo)
        lay_cont.addWidget(self.chk_specs)
        lay_cont.addWidget(self.chk_pinagem)
        lay_cont.addWidget(self.chk_validacao)
        main_lay.addWidget(grp_conteudo)

        # ── Section 4: Output options ────────────────────────────────────
        grp_saida = QGroupBox('Opções de Saída')
        lay_saida = QVBoxLayout(grp_saida)

        # Format
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel('Formato:'))
        self.cmb_formato = QComboBox()
        self.cmb_formato.addItem('PDF + HTML', 'ambos')
        self.cmb_formato.addItem('Somente PDF', 'pdf')
        self.cmb_formato.addItem('Somente HTML', 'html')
        row_fmt.addWidget(self.cmb_formato)
        row_fmt.addStretch()
        lay_saida.addLayout(row_fmt)

        # Scale
        row_esc = QHBoxLayout()
        row_esc.addWidget(QLabel('Escala:'))
        self.spn_escala = QDoubleSpinBox()
        self.spn_escala.setRange(0.5, 10.0)
        self.spn_escala.setSingleStep(0.5)
        self.spn_escala.setValue(1.0)
        self.spn_escala.setDecimals(1)
        row_esc.addWidget(self.spn_escala)
        self.lbl_escala = QLabel('Escala 1:1')
        self.lbl_escala.setStyleSheet('color:#A6ADC8; font-size:11px; padding-left:6px;')
        row_esc.addWidget(self.lbl_escala)
        row_esc.addStretch()
        lay_saida.addLayout(row_esc)

        # Output path
        row_path = QHBoxLayout()
        row_path.addWidget(QLabel('Saída:'))
        self.txt_output = QLabel(os.path.join(self.saida_dir, 'relatorio'))
        self.txt_output.setStyleSheet(
            'background:#181825; border:1px solid #313244; border-radius:4px;'
            'padding:4px 8px; font-size:11px; color:#BAC2DE;'
        )
        self.txt_output.setMinimumWidth(300)
        row_path.addWidget(self.txt_output, 1)
        self.btn_browse = QPushButton('...')
        self.btn_browse.setFixedWidth(36)
        row_path.addWidget(self.btn_browse)
        lay_saida.addLayout(row_path)

        main_lay.addWidget(grp_saida)

        # ── Section 5: Buttons & progress ────────────────────────────────
        sep = QFrame()
        sep.setObjectName('separator')
        sep.setFrameShape(QFrame.HLine)
        main_lay.addWidget(sep)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        main_lay.addWidget(self.progress)

        btn_lay = QHBoxLayout()
        btn_lay.addStretch()

        self.btn_cancelar = QPushButton('Cancelar')
        self.btn_cancelar.setObjectName('btn_cancelar')

        self.btn_gerar = QPushButton('Gerar Relatório')
        self.btn_gerar.setObjectName('btn_gerar')

        btn_lay.addWidget(self.btn_cancelar)
        btn_lay.addWidget(self.btn_gerar)
        main_lay.addLayout(btn_lay)

    # ---------------------------------------------------------- Load list
    def _load_yaml_list(self):
        """Carrega a lista de arquivos YAML do diretório de módulos."""
        self.list_yamls.clear()
        self._yaml_files = []

        if not self.modulos_dir or not os.path.isdir(self.modulos_dir):
            return

        for fname in sorted(os.listdir(self.modulos_dir)):
            if not fname.lower().endswith(('.yaml', '.yml')):
                continue
            low = fname.lower()
            if '_preset_' in low or '_template' in low:
                continue

            fpath = os.path.join(self.modulos_dir, fname)
            self._yaml_files.append(fpath)

            item = QListWidgetItem(fname)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, fpath)
            self.list_yamls.addItem(item)

    # ---------------------------------------------------------- Signals
    def _connect_signals(self):
        self._modo_group.buttonClicked.connect(self._on_modo_changed)
        self.btn_sel_all.clicked.connect(self._select_all)
        self.btn_sel_none.clicked.connect(self._select_none)
        self.chk_modelo3d.toggled.connect(self._on_3d_toggled)
        self.spn_escala.valueChanged.connect(self._on_escala_changed)
        self.btn_browse.clicked.connect(self._on_browse)
        self.btn_gerar.clicked.connect(self._on_gerar)
        self.btn_cancelar.clicked.connect(self.reject)

    def _on_modo_changed(self, btn):
        is_select = (btn == self.radio_selecionar)
        self.grp_lista.setEnabled(is_select)

    def _select_all(self):
        for i in range(self.list_yamls.count()):
            self.list_yamls.item(i).setCheckState(Qt.Checked)

    def _select_none(self):
        for i in range(self.list_yamls.count()):
            self.list_yamls.item(i).setCheckState(Qt.Unchecked)

    def _on_3d_toggled(self, checked):
        self.cmb_3d_modo.setEnabled(checked)
        self.lbl_3d_modo.setEnabled(checked)

    def _on_escala_changed(self, value):
        self.lbl_escala.setText(f'Escala 1:{value:g}')

    def _on_browse(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, 'Selecionar diretório de saída', self.saida_dir
        )
        if dir_path:
            self.txt_output.setText(os.path.join(dir_path, 'relatorio'))

    # ---------------------------------------------------------- Config
    def get_config(self):
        """Retorna dicionário com todas as opções selecionadas."""
        # Determine mode
        if self.radio_atual.isChecked():
            modo = 'atual'
        elif self.radio_biblioteca.isChecked():
            modo = 'biblioteca'
        else:
            modo = 'selecionar'

        # Determine selected YAMLs
        yaml_paths = []
        if modo == 'atual':
            if self.yaml_editor and hasattr(self.yaml_editor, 'yaml_path'):
                current = getattr(self.yaml_editor, 'yaml_path', '')
                if current:
                    yaml_paths = [current]
        elif modo == 'biblioteca':
            yaml_paths = list(self._yaml_files)
        else:
            for i in range(self.list_yamls.count()):
                item = self.list_yamls.item(i)
                if item.checkState() == Qt.Checked:
                    yaml_paths.append(item.data(Qt.UserRole))

        # Format
        formato = self.cmb_formato.currentData()

        # Output path
        output_base = self.txt_output.text()

        return {
            'modo': modo,
            'yaml_paths': yaml_paths,
            'formato': formato,
            'footprint_2d': self.chk_footprint.isChecked(),
            'cotas': self.chk_footprint.isChecked(),
            'modelo_3d': self.chk_modelo3d.isChecked(),
            'modelo_3d_modo': self.cmb_3d_modo.currentData(),
            'simbolo': self.chk_simbolo.isChecked(),
            'specs': self.chk_specs.isChecked(),
            'pinagem': self.chk_pinagem.isChecked(),
            'validacao': self.chk_validacao.isChecked(),
            'escala': self.spn_escala.value(),
            'output_path': output_base,
            'saida_dir': self.saida_dir,
        }

    # ---------------------------------------------------------- Generate
    def _on_gerar(self):
        """Valida configuração e dispara a geração do relatório."""
        config = self.get_config()

        # Validate: at least 1 YAML
        if not config['yaml_paths']:
            QMessageBox.warning(
                self,
                'Nenhum componente selecionado',
                'Selecione ao menos um componente YAML para gerar o relatório.',
            )
            return

        # Show progress
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.btn_gerar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)

        try:
            from core.gerador_relatorio import gerar_relatorio

            total = len(config['yaml_paths'])
            resultados = {'ok': 0, 'erros': []}

            for idx, ypath in enumerate(config['yaml_paths'], 1):
                self.progress.setValue(int((idx - 1) / total * 100))
                # Force UI update
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()

                try:
                    gerar_relatorio(ypath, config)
                    resultados['ok'] += 1
                except Exception as ex:
                    resultados['erros'].append(
                        f'{os.path.basename(ypath)}: {type(ex).__name__}: {ex}'
                    )

            self.progress.setValue(100)

            # Show results
            if resultados['erros']:
                erros_txt = '\n'.join(resultados['erros'])
                QMessageBox.warning(
                    self,
                    'Relatório Gerado com Avisos',
                    f'✅  Relatórios gerados: {resultados["ok"]}\n'
                    f'❌  Erros: {len(resultados["erros"])}\n\n'
                    f'Detalhes:\n{erros_txt}',
                )
            else:
                QMessageBox.information(
                    self,
                    'Relatório Gerado',
                    f'✅  Todos os {resultados["ok"]} relatórios foram gerados com sucesso!\n\n'
                    f'Diretório de saída:\n{config["output_path"]}',
                )

            self.accept()

        except ImportError as ex:
            self.progress.setVisible(False)
            QMessageBox.critical(
                self,
                'Módulo não encontrado',
                f'❌  Não foi possível importar o gerador de relatórios:\n\n{ex}\n\n'
                f'Verifique se o módulo core/gerador_relatorio.py existe.',
            )
        except Exception as ex:
            self.progress.setVisible(False)
            QMessageBox.critical(
                self,
                'Erro ao Gerar Relatório',
                f'❌  Erro inesperado:\n\n{type(ex).__name__}: {ex}',
            )
        finally:
            self.btn_gerar.setEnabled(True)
            self.btn_cancelar.setEnabled(True)
