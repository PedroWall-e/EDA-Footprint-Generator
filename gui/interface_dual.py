# =============================================================================
# interface_dual.py
# Launcher principal da plataforma CAM/CAD.
#
# Layout:
#   [YAML Editor] | [Footprint 2D] | [3D Viewer CQ-Editor (motor invisivel)]
#
# O editor Python do CQ-Editor e ocultado — o usuario so interage com o YAML.
# O runner_stub.py e carregado no motor de render mas nunca exibido.
#
# Execute via: abrir_dual.bat
# =============================================================================

import sys
import os

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CQ_EDITOR_DIR = os.path.join(PROJ_DIR, 'libs', 'CQ-editor')
GUI_DIR  = os.path.join(PROJ_DIR, 'gui')
CORE_DIR = os.path.join(PROJ_DIR, 'core')
for path in [PROJ_DIR, CQ_EDITOR_DIR, GUI_DIR, CORE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PyQt5.QtWidgets import (QApplication, QDockWidget, QAction, QMessageBox, QToolBar,
                             QMenu, QLabel, QFileDialog, QDialog, QVBoxLayout,
                             QHBoxLayout, QTabWidget, QWidget, QSpinBox,
                             QDoubleSpinBox, QLineEdit, QCheckBox,
                             QDialogButtonBox, QFormLayout, QGroupBox,
                             QProgressBar, QFrame, QToolButton)
from PyQt5.QtCore import Qt, QFileSystemWatcher, QTimer, QSettings, QSize
from PyQt5.QtGui import QKeySequence, QColor, QIcon, QPalette

try:
    from core.version import __version__
except ImportError:
    __version__ = '3.0.0'

from cq_editor.main_window import MainWindow
from painel_footprint_2d import FootprintViewer2D
from painel_symbol_2d    import SymbolViewer2D
from painel_yaml_editor import YamlEditorPanel
from painel_biblioteca import BibliotecaPanel
from painel_help import HelpPanel
from splash import SplashScreen
import logging
from log_config import setup_logging
from core.config import AppConfig

log = logging.getLogger('interface_dual')


# =============================================================================
# Helpers — cada etapa do main() em sua própria função
# =============================================================================

def _create_app():
    """Cria e configura a QApplication."""
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Plataforma CAM/CAD - Gerador de Footprints")
    app.setOrganizationName("CAD-Data-Frontier")
    app.setStyle("Fusion")
    
    # Global Dark Theme
    # QPalette e QColor já importados no topo do módulo
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 46))
    palette.setColor(QPalette.WindowText, QColor(205, 214, 244))
    palette.setColor(QPalette.Base, QColor(24, 24, 37))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 46))
    palette.setColor(QPalette.ToolTipBase, QColor(24, 24, 37))
    palette.setColor(QPalette.ToolTipText, QColor(205, 214, 244))
    palette.setColor(QPalette.Text, QColor(205, 214, 244))
    palette.setColor(QPalette.Button, QColor(49, 50, 68))
    palette.setColor(QPalette.ButtonText, QColor(205, 214, 244))
    palette.setColor(QPalette.BrightText, QColor(243, 139, 168))
    palette.setColor(QPalette.Highlight, QColor(137, 180, 250))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 46))
    app.setPalette(palette)
    
    app.setStyleSheet('''
        QToolTip { color: #CDD6F4; background-color: #181825; border: 1px solid #45475A; }
        QDockWidget::title { background: #1E1E2E; padding-left: 5px; padding-top: 3px; }
        QMenuBar { background-color: #1E1E2E; color: #CDD6F4; }
        QMenuBar::item:selected { background-color: #313244; }
        QMenu { background-color: #1E1E2E; color: #CDD6F4; border: 1px solid #45475A; }
        QMenu::item:selected { background-color: #313244; }

        QPushButton {
            background-color: #313244;
            color: #CDD6F4;
            border: 1px solid #45475A;
            border-radius: 4px;
            padding: 5px 12px;
        }
        QPushButton:hover {
            background-color: #45475A;
            border-color: #89B4FA;
        }
        QPushButton:pressed {
            background-color: #585B70;
        }
        QPushButton:disabled {
            background-color: #252535;
            color: #585B70;
            border-color: #353545;
        }

        QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
            background-color: #313244;
            color: #CDD6F4;
            border: 1px solid #45475A;
            border-radius: 3px;
            padding: 3px 6px;
        }
        QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
            border-color: #89B4FA;
        }

        QScrollBar:vertical {
            background: #181825; width: 10px; border: none;
        }
        QScrollBar::handle:vertical {
            background: #45475A; min-height: 30px; border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover { background: #585B70; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

        QScrollBar:horizontal {
            background: #181825; height: 10px; border: none;
        }
        QScrollBar::handle:horizontal {
            background: #45475A; min-width: 30px; border-radius: 5px;
        }
        QScrollBar::handle:horizontal:hover { background: #585B70; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    ''')
    
    return app


def _find_first_yaml(config_dir):
    """Find the first non-preset YAML file in config_dir."""
    for f in sorted(os.listdir(config_dir)):
        if f.endswith(('.yaml', '.yml')) and not f.startswith('_'):
            return os.path.join(config_dir, f)
    # Fallback to first preset
    for f in sorted(os.listdir(config_dir)):
        if f.endswith(('.yaml', '.yml')):
            return os.path.join(config_dir, f)
    return None


def _init_paths():
    """Retorna dict com todos os caminhos do projeto."""
    import json
    config_dir = os.path.join(PROJ_DIR, 'modulos_config')
    saida_dir  = os.path.join(PROJ_DIR, 'saida')
    os.makedirs(saida_dir, exist_ok=True)

    # Descobre dinamicamente o primeiro YAML disponível
    primeiro_yaml = _find_first_yaml(config_dir)
    if primeiro_yaml:
        nome_base = os.path.splitext(os.path.basename(primeiro_yaml))[0]
        kicad_default = os.path.join(saida_dir, nome_base + '.kicad_mod')
    else:
        primeiro_yaml = ''
        kicad_default = ''

    paths = {
        'script':    os.path.join(PROJ_DIR, 'core', 'runner_stub.py'),
        'kicad_mod': kicad_default,
        'yaml':      primeiro_yaml,
        'estado':    os.path.join(PROJ_DIR, '_estado_atual.json'),
        'saida_dir': saida_dir,
    }

    # Tentar ler sessão anterior
    estado_existente = None
    if os.path.isfile(paths['estado']):
        try:
            with open(paths['estado'], 'r', encoding='utf-8') as f:
                estado_existente = json.load(f)
            if not isinstance(estado_existente, dict):
                estado_existente = None
        except (json.JSONDecodeError, OSError):
            estado_existente = None

    if estado_existente:
        # Restaurar caminhos da sessão anterior se válidos
        yaml_anterior = estado_existente.get('yaml_path', '')
        if yaml_anterior and os.path.isfile(yaml_anterior):
            paths['yaml'] = yaml_anterior
        kicad_anterior = estado_existente.get('kicad_mod_path', '')
        if kicad_anterior and os.path.isfile(kicad_anterior):
            paths['kicad_mod'] = kicad_anterior
    else:
        # Criar estado inicial apenas se não existia ou estava corrompido
        estado_inicial = {'yaml_path': paths['yaml'], 'kicad_mod_path': paths['kicad_mod']}
        with open(paths['estado'], 'w', encoding='utf-8') as f:
            json.dump(estado_inicial, f, ensure_ascii=False, indent=2)

    return paths


def _create_panels(win, paths):
    """Cria todos os painéis (viewers, editor, biblioteca) e retorna dict."""
    viewer_2d = FootprintViewer2D(
        filepath=paths['kicad_mod'] if os.path.isfile(paths['kicad_mod']) else '',
        parent=win,
    )
    sym_path_inicial = os.path.join(
        PROJ_DIR, 'saida',
        os.path.splitext(os.path.basename(paths['yaml']))[0] + '.kicad_sym'
    )
    viewer_sym = SymbolViewer2D(
        filepath=sym_path_inicial if os.path.isfile(sym_path_inicial) else '',
        parent=win,
    )
    yaml_editor = YamlEditorPanel(yaml_path=paths['yaml'], parent=win)
    biblioteca = BibliotecaPanel(
        modulos_dir=os.path.join(PROJ_DIR, 'modulos_config'), parent=win
    )
    return {
        'viewer_2d':   viewer_2d,
        'viewer_sym':  viewer_sym,
        'yaml_editor': yaml_editor,
        'biblioteca':  biblioteca,
    }


def _create_docks(win, panels):
    """Cria QDockWidgets para cada painel e retorna dict."""
    dock_features = (
        QDockWidget.DockWidgetMovable |
        QDockWidget.DockWidgetFloatable |
        QDockWidget.DockWidgetClosable
    )
    docks = {}

    for name, title, widget, min_w in [
        ('2d',         'Footprint 2D  —  KiCad',         panels['viewer_2d'],   350),
        ('symbol',     'Simbolo Esquematico  —  KiCad',  panels['viewer_sym'],  350),
        ('yaml',       '⚙  Configuracao YAML',           panels['yaml_editor'], 300),
        ('biblioteca', '📚  Biblioteca',                  panels['biblioteca'],  180),
    ]:
        dock = QDockWidget(title, win)
        dock.setObjectName(f"dock_{name}")
        dock.setWidget(widget)
        dock.setMinimumWidth(min_w)
        dock.setFeatures(dock_features)
        docks[name] = dock

    return docks


def _setup_toolbar(win, yaml_editor):
    """Unifica toolbar: remove botões CQ-Editor, mantém só 3D view + plataforma."""
    # Ocultar outras toolbars inúteis que o CQ-Editor pode criar
    for tb in win.findChildren(QToolBar):
        if tb != win.toolbar:
            tb.hide()

    tb = win.toolbar
    tb.setWindowTitle("Main Toolbar")
    tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
    tb.setIconSize(QSize(20, 20))

    # --- Fase 2: Remover TODOS os botões CQ-Editor da toolbar ---
    # Salvar ações 3D úteis antes de limpar
    _3D_KEEP = {'fit', 'iso', 'top', 'bottom', 'front', 'back',
                'left', 'right', 'wireframe', 'shaded',
                'clear all', 'clear current'}
    kept_3d_actions = []
    for act in list(tb.actions()):
        txt = act.text().lower().replace('&', '').strip()
        if txt in _3D_KEEP or 'view' in txt:
            kept_3d_actions.append(act)

    # Limpar toda a toolbar
    tb.clear()

    # Re-adicionar ações da plataforma
    # Grupo: Executar + Salvar Saída
    tb.addAction(yaml_editor.act_gerar)
    tb.addAction(yaml_editor.act_salvar_saida)
    tb.addSeparator()

    # Estilizar botões ▶ e 💾 com objectName para CSS
    for btn in tb.findChildren(QToolButton):
        if btn.defaultAction() == yaml_editor.act_gerar:
            btn.setObjectName('btn_executar')
        elif btn.defaultAction() == yaml_editor.act_salvar_saida:
            btn.setObjectName('btn_salvar_saida')

    # Grupo: Arquivo
    for act in [yaml_editor.act_save, yaml_editor.act_save_as,
                yaml_editor.act_reload, yaml_editor.act_open]:
        tb.addAction(act)
    tb.addSeparator()

    # Grupo: Componentes
    tb.addAction(yaml_editor.act_novo)
    tb.addAction(yaml_editor.act_duplicar)
    tb.addSeparator()

    # Grupo: Ferramentas
    for act in [yaml_editor.act_pin_editor, yaml_editor.act_cq_editor,
                yaml_editor.act_export_lib, yaml_editor.act_verificar]:
        tb.addAction(act)
    tb.addSeparator()

    # Grupo: Edição
    tb.addAction(yaml_editor.act_undo)
    tb.addAction(yaml_editor.act_redo)
    tb.addAction(yaml_editor.act_ln)

    # Grupo: Views 3D (ações úteis do CQ-Editor)
    if kept_3d_actions:
        tb.addSeparator()
        for act in kept_3d_actions:
            tb.addAction(act)

    # Estilizar toolbar
    tb.setStyleSheet('''
        QToolBar { background:#1E1E2E; border:none; padding:2px; spacing:2px; }
        QToolButton { color:#CDD6F4; border:none; padding:4px 7px;
                      border-radius:4px; font-size:12px; }
        QToolButton:hover { background:#313244; }
        QToolButton:pressed { background:#45475A; }
        QToolButton:disabled { color:#585870; }
        QToolButton:checked { background:#313244; color:#89DCEB; }

        /* ▶ Executar — verde destaque */
        QToolButton#btn_executar {
            background: #2D5A27;
            color: #A6E3A1;
            font-weight: bold;
            padding: 4px 12px;
            border: 1px solid #40864A;
        }
        QToolButton#btn_executar:hover {
            background: #3A7A35;
            border-color: #5AAA55;
        }
        QToolButton#btn_executar:pressed {
            background: #1E4A18;
        }
        QToolButton#btn_executar:disabled {
            background: #252535;
            color: #585870;
            border-color: #353545;
        }

        /* 💾 Salvar Saída — azul accent */
        QToolButton#btn_salvar_saida {
            background: #27405A;
            color: #89B4FA;
            font-weight: bold;
            padding: 4px 12px;
            border: 1px solid #3A6090;
        }
        QToolButton#btn_salvar_saida:hover {
            background: #355580;
            border-color: #5588BB;
        }
        QToolButton#btn_salvar_saida:pressed {
            background: #1E3048;
        }
        QToolButton#btn_salvar_saida:disabled {
            background: #252535;
            color: #585870;
            border-color: #353545;
        }
    ''')


def _setup_layout(win, docks):
    """Configura a disposição dos docks na janela."""
    # --- Fase 1: Ocultar TODOS os docks CQ-Editor inúteis ---
    _CQ_DOCKS_HIDE = [
        'editor', 'properties',
        'console',              # IPython console
        'traceback_viewer',     # Python traceback
        'variables_viewer',     # Python variables
        'cq_object_inspector',  # CadQuery inspector
    ]
    for d in _CQ_DOCKS_HIDE:
        dock = win.docks.get(d) or getattr(win, f'{d}_dock', None)
        if dock and isinstance(dock, QDockWidget):
            dock.hide()
            dock.setFeatures(QDockWidget.NoDockWidgetFeatures)  # impede reabrir

    # Log: escondido por padrão, mas pode ser aberto pelo menu
    log_dock = win.docks.get('log') or getattr(win, 'log_dock', None)
    if log_dock and isinstance(log_dock, QDockWidget):
        log_dock.setWindowTitle('📝 Log do Sistema')
        win.addDockWidget(Qt.BottomDockWidgetArea, log_dock)
        log_dock.hide()  # escondido por padrão

    # Garantir que a árvore de objetos do CQ-Editor apareça na direita
    obj_dock = win.docks.get('object_tree') or win.docks.get('objects')
    if obj_dock and isinstance(obj_dock, QDockWidget):
        obj_dock.setWindowTitle('Árvore de Objetos')
        win.addDockWidget(Qt.RightDockWidgetArea, obj_dock)
        obj_dock.show()

    # YAML Editor à esquerda
    win.addDockWidget(Qt.LeftDockWidgetArea, docks['yaml'])

    # Footprint 2D à esquerda (ficará lado a lado com YAML via split)
    win.addDockWidget(Qt.LeftDockWidgetArea, docks['2d'])
    win.splitDockWidget(docks['yaml'], docks['2d'], Qt.Horizontal)

    # Symbol Viewer como aba junto ao Footprint 2D
    win.addDockWidget(Qt.LeftDockWidgetArea, docks['symbol'])
    win.tabifyDockWidget(docks['2d'], docks['symbol'])
    docks['2d'].raise_()

    # Biblioteca como aba junto ao YAML
    win.addDockWidget(Qt.LeftDockWidgetArea, docks['biblioteca'])
    win.tabifyDockWidget(docks['yaml'], docks['biblioteca'])
    docks['yaml'].raise_()


def _setup_signals(win, panels, docks, paths):
    """Conecta sinais entre os componentes."""
    yaml_editor = panels['yaml_editor']
    viewer_2d = panels['viewer_2d']
    viewer_sym = panels['viewer_sym']
    biblioteca = panels['biblioteca']
    estado_path = paths['estado']

    # Título dinâmico
    def _atualizar_titulo(yaml_path=''):
        base = 'EDA Footprint Generator'
        if yaml_path:
            nome = os.path.basename(yaml_path).replace('.yaml', '').replace('.yml', '')
            win.setWindowTitle(f'{nome} — {base}')
        else:
            win.setWindowTitle(base)

    try:
        yaml_editor.sigFileLoaded.connect(_atualizar_titulo)
    except Exception:
        pass

    # --- Estado de preview (arquivos gerados temporários) ---
    _preview_state = {'unsaved': False}

    def _marcar_preview_salvo():
        _preview_state['unsaved'] = False
        yaml_editor.act_salvar_saida.setEnabled(False)

    def _marcar_preview_gerado():
        _preview_state['unsaved'] = True
        yaml_editor.act_salvar_saida.setEnabled(True)

    def _salvar_preview():
        """Copia arquivos de saida/_preview/ para saida/ (permanente)."""
        import shutil, glob
        preview_dir = os.path.join(PROJ_DIR, 'saida', '_preview')
        saida_dir = os.path.join(PROJ_DIR, 'saida')
        if not os.path.isdir(preview_dir):
            log.warning('Nada para salvar: pasta _preview não existe')
            return False

        arquivos = glob.glob(os.path.join(preview_dir, '*'))
        if not arquivos:
            log.warning('Nada para salvar: pasta _preview vazia')
            return False

        n = 0
        for src in arquivos:
            if os.path.isfile(src):
                dst = os.path.join(saida_dir, os.path.basename(src))
                shutil.copy2(src, dst)
                log.info('Salvo: %s', os.path.basename(dst))
                n += 1

        _marcar_preview_salvo()
        win.statusBar().showMessage(f'✅  {n} arquivo(s) salvo(s) em saida/', 5000)
        return True

    yaml_editor.act_salvar_saida.triggered.connect(_salvar_preview)

    def _checar_preview_nao_salvo():
        """Retorna True se pode prosseguir (salvo ou descartado). False para cancelar."""
        if not _preview_state['unsaved']:
            return True

        from PyQt5.QtWidgets import QMessageBox
        msg = QMessageBox(win)
        msg.setWindowTitle('Preview não salvo')
        msg.setText('Os arquivos gerados ainda não foram salvos.')
        msg.setInformativeText('Deseja salvar antes de continuar?')
        msg.setIcon(QMessageBox.Warning)
        btn_salvar = msg.addButton('Salvar', QMessageBox.AcceptRole)
        btn_descartar = msg.addButton('Descartar', QMessageBox.DestructiveRole)
        btn_cancelar = msg.addButton('Cancelar', QMessageBox.RejectRole)
        msg.setDefaultButton(btn_salvar)
        msg.setStyleSheet('''
            QMessageBox { background: #1E1E2E; color: #CDD6F4; }
            QPushButton { background: #313244; color: #CDD6F4;
                          padding: 5px 18px; border-radius: 4px; }
            QPushButton:hover { background: #45475A; }
        ''')
        msg.exec_()

        clicked = msg.clickedButton()
        if clicked == btn_salvar:
            _salvar_preview()
            return True
        elif clicked == btn_descartar:
            _marcar_preview_salvo()
            return True
        else:
            return False  # Cancelar

    # Biblioteca → Editor YAML (com aviso de preview não salvo)
    def _on_componente_selecionado(yaml_path):
        if not _checar_preview_nao_salvo():
            return  # Cancelado
        yaml_editor.load_file(yaml_path)
        yaml_editor._write_estado()

    biblioteca.sigComponenteSelecionado.connect(_on_componente_selecionado)

    # Debugger (CQ-Editor) → Viewers 2D
    import json
    try:
        debugger = win.components["debugger"]

        def _on_rendered(*_):
            try:
                with open(estado_path, 'r', encoding='utf-8') as f:
                    estado = json.load(f)

                novo_kicad = estado.get('kicad_mod_path', '')
                if novo_kicad and os.path.isfile(novo_kicad):
                    QTimer.singleShot(200, lambda p=novo_kicad: viewer_2d.set_file(p))
                else:
                    QTimer.singleShot(200, viewer_2d.reload_file)

                novo_sym = estado.get('sym_path', '')
                if novo_sym and os.path.isfile(novo_sym):
                    QTimer.singleShot(400, lambda p=novo_sym: viewer_sym.set_file(p))
                else:
                    QTimer.singleShot(400, viewer_sym.reload_file)
            except Exception:
                QTimer.singleShot(200, viewer_2d.reload_file)
                QTimer.singleShot(400, viewer_sym.reload_file)

        debugger.sigRendered.connect(_on_rendered)

        # --- Barra de progresso durante geração ---
        _progress_frame = QFrame(win)
        _progress_frame.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 46, 230);
                border: 1px solid #45475A;
                border-radius: 10px;
            }
        """)
        _pf_layout = QVBoxLayout(_progress_frame)
        _pf_layout.setContentsMargins(20, 15, 20, 15)
        _pf_layout.setSpacing(8)

        _progress_label = QLabel('⚙️  Gerando componente...', _progress_frame)
        _progress_label.setStyleSheet(
            'color: #CDD6F4; font-size: 13px; font-weight: bold; '
            'background: transparent; border: none;')
        _progress_label.setAlignment(Qt.AlignCenter)
        _pf_layout.addWidget(_progress_label)

        _progress_bar = QProgressBar(_progress_frame)
        _progress_bar.setRange(0, 0)  # modo indeterminado (animação)
        _progress_bar.setFixedHeight(8)
        _progress_bar.setStyleSheet("""
            QProgressBar {
                background: #313244;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #89B4FA, stop:0.5 #B4BEFE, stop:1 #89B4FA);
                border-radius: 4px;
            }
        """)
        _pf_layout.addWidget(_progress_bar)

        _progress_detail = QLabel('Preparando...', _progress_frame)
        _progress_detail.setStyleSheet(
            'color: #6C7086; font-size: 10px; '
            'background: transparent; border: none;')
        _progress_detail.setAlignment(Qt.AlignCenter)
        _pf_layout.addWidget(_progress_detail)

        _progress_frame.setFixedSize(300, 85)
        _progress_frame.hide()

        def _center_progress():
            """Centraliza o frame de progresso na janela."""
            pw = win.centralWidget() or win
            cx = (pw.width() - _progress_frame.width()) // 2
            cy = (pw.height() - _progress_frame.height()) // 2
            _progress_frame.move(max(0, cx), max(0, cy))
            _progress_frame.raise_()

        def _show_progress():
            _progress_label.setText('⚙️  Gerando componente...')
            _progress_detail.setText('Footprint 2D + Símbolo + Modelo 3D')
            _center_progress()
            _progress_frame.show()
            QApplication.processEvents()

        def _hide_progress():
            _progress_frame.hide()

        def _on_rendered_with_progress(*args):
            _hide_progress()
            _on_rendered(*args)
            _marcar_preview_gerado()

        debugger.sigRendered.disconnect(_on_rendered)
        debugger.sigRendered.connect(_on_rendered_with_progress)

        def _debug_render():
            log.debug('debugger.render() chamado via sigGerarRequested')
            _show_progress()
            try:
                debugger.render()
            except Exception as ex:
                log.error('ERRO em debugger.render(): %s: %s', type(ex).__name__, ex, exc_info=True)
                _hide_progress()
        yaml_editor.sigGerarRequested.connect(_debug_render)
        log.info("Sinais conectados com sucesso.")
    except (KeyError, AttributeError) as e:
        log.warning("Aviso: %s", e)

    # --- Fase 4: Redirecionar F5 e desativar TODOS os shortcuts CQ-Editor ---
    def _limpar_cqeditor_shortcuts():
        from PyQt5.QtWidgets import QShortcut
        # Redirecionar F5 para nosso gerar
        atalho_f5 = QShortcut(QKeySequence('F5'), win)
        atalho_f5.setContext(Qt.ApplicationShortcut)
        atalho_f5.activated.connect(yaml_editor._on_gerar)

        # Shortcuts CQ-Editor a desativar (conflitam ou são inúteis)
        _KILL_SHORTCUTS = {
            'f5', 'ctrl+f5', 'ctrl+f10', 'ctrl+f11', 'ctrl+f12',  # debugger
            'ctrl+n', 'ctrl+o', 'ctrl+s', 'ctrl+shift+s',          # editor .py
            'ctrl+/', 'alt+/', 'ctrl+f',                           # editor Python
            'ctrl+q',                                               # quit CQ-Editor
        }
        _RENDER_KEYWORDS = {'render', 'run', 'execute', 'play', 'f5'}

        for act in win.findChildren(QAction):
            sc = act.shortcut().toString().lower().replace(' ', '')
            tx = act.text().lower().replace('&', '')

            if sc in _KILL_SHORTCUTS:
                if sc == 'f5' or any(k in tx for k in _RENDER_KEYWORDS):
                    # Redirecionar F5/Render para nosso gerar
                    try:
                        act.setShortcut(QKeySequence())
                        act.triggered.disconnect()
                        act.triggered.connect(yaml_editor._on_gerar)
                    except Exception:
                        pass
                else:
                    # Desativar completamente
                    act.setShortcut(QKeySequence())
                    act.setEnabled(False)

    QTimer.singleShot(500, _limpar_cqeditor_shortcuts)


def _purge_cqeditor_menus(win):
    """Fase 3: Remove TODOS os menus CQ-Editor e cria menus limpos da plataforma."""
    menubar = win.menuBar()

    # Identificar e remover menus CQ-Editor (em inglês)
    _CQ_MENUS = {'&File', '&Edit', '&Tools', '&Run', '&View', '&Help'}
    for menu_action in list(menubar.actions()):
        if menu_action.text() in _CQ_MENUS:
            menubar.removeAction(menu_action)


def _setup_view_menu(win, docks):
    """Cria menu Visualizar limpo (sem toggles CQ-Editor)."""
    _settings = QSettings('CAD-Data-Frontier', 'Plataforma-CAM-CAD')
    menubar = win.menuBar()

    view_menu = QMenu('&Visualizar', win)

    # Toggles dos docks da PLATAFORMA
    view_menu.addSection('Painéis')
    for dock_name, dock_obj in docks.items():
        act = dock_obj.toggleViewAction()
        view_menu.addAction(act)

    # Toggle da árvore de objetos 3D (CQ-Editor - útil)
    obj_dock = win.docks.get('object_tree') or win.docks.get('objects')
    if obj_dock and isinstance(obj_dock, QDockWidget):
        view_menu.addAction(obj_dock.toggleViewAction())

    # Toggle do log (escondido por padrão, abre sob demanda)
    log_dock = win.docks.get('log') or getattr(win, 'log_dock', None)
    if log_dock and isinstance(log_dock, QDockWidget):
        act_log = log_dock.toggleViewAction()
        act_log.setText('📝  Log do Sistema')
        view_menu.addAction(act_log)

    view_menu.addSeparator()

    # Toggle toolbar
    for tb_widget in win.findChildren(QToolBar):
        if not tb_widget.isHidden():
            act = tb_widget.toggleViewAction()
            act.setText(f'Toolbar: {tb_widget.windowTitle() or "Principal"}')
            view_menu.addAction(act)

    view_menu.addSeparator()

    # Views 3D (do CQ-Editor - úteis)
    view_menu.addSection('Vista 3D')
    _3D_VIEWS = {'fit', 'iso', 'top', 'bottom', 'front', 'back',
                 'left', 'right', 'wireframe', 'shaded'}
    for act in win.findChildren(QAction):
        txt = act.text().lower().replace('&', '').strip()
        if txt in _3D_VIEWS:
            view_menu.addAction(act)

    view_menu.addSeparator()

    # Resetar layout
    act_reset = QAction('  🔄  Resetar Layout para o Padrão', win)
    act_reset.setToolTip('Apagar configuração salva e restaurar layout padrão')

    def _reset_layout():
        _settings.remove('window/geometry')
        _settings.remove('window/state')
        QMessageBox.information(
            win, 'Layout Resetado',
            'Layout resetado com sucesso!\n\n'
            'Feche e reabra a aplicação para ver o layout padrão.'
        )

    act_reset.triggered.connect(_reset_layout)
    view_menu.addAction(act_reset)

    menubar.addMenu(view_menu)
    return _settings


def _setup_status_bar(win, panels):
    """Cria e configura a status bar da janela principal com 3 seções."""
    yaml_editor = panels['yaml_editor']

    sb = win.statusBar()
    sb.setStyleSheet(
        'QStatusBar { background:#1A1A2E; color:#CDD6F4; border-top: 1px solid #313244; }'
        'QStatusBar::item { border: none; }'
    )

    # Seção esquerda: posição do cursor
    lbl_cursor = QLabel('Ln 1, Col 1')
    lbl_cursor.setStyleSheet(
        'color:#CDD6F4; font-family:Consolas; font-size:11px; padding:2px 12px;'
    )

    # Seção central: nome do arquivo
    lbl_filename = QLabel('Nenhum arquivo')
    lbl_filename.setStyleSheet(
        'color:#CDD6F4; font-family:Consolas; font-size:11px; padding:2px 12px;'
    )

    # Seção direita: validação YAML
    lbl_validation = QLabel('✓ YAML válido')
    lbl_validation.setStyleSheet(
        'color:#A6E3A1; font-family:Consolas; font-size:11px; padding:2px 12px;'
    )

    sb.addWidget(lbl_cursor, 0)
    sb.addWidget(lbl_filename, 1)  # stretch=1 para centralizar
    sb.addPermanentWidget(lbl_validation)

    # --- Conectar cursor position ---
    def _on_cursor_changed():
        cursor = yaml_editor.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        lbl_cursor.setText(f'Ln {line}, Col {col}')

    yaml_editor.editor.cursorPositionChanged.connect(_on_cursor_changed)

    # --- Conectar filename ---
    def _on_file_loaded(path):
        if path:
            lbl_filename.setText(os.path.basename(path))
        else:
            lbl_filename.setText('Nenhum arquivo')

    try:
        yaml_editor.sigFileLoaded.connect(_on_file_loaded)
    except Exception:
        pass

    # Inicializar com arquivo atual
    if yaml_editor.yaml_path:
        lbl_filename.setText(os.path.basename(yaml_editor.yaml_path))

    # --- Conectar validação YAML ---
    def _on_validation_changed(is_valid):
        if is_valid:
            lbl_validation.setText('✓ YAML válido')
            lbl_validation.setStyleSheet(
                'color:#A6E3A1; font-family:Consolas; font-size:11px; padding:2px 12px;'
            )
        else:
            lbl_validation.setText('✗ YAML inválido')
            lbl_validation.setStyleSheet(
                'color:#F38BA8; font-family:Consolas; font-size:11px; padding:2px 12px;'
            )

    try:
        yaml_editor.sigValidationChanged.connect(_on_validation_changed)
    except Exception:
        pass


def _setup_ferramentas_menu(win, panels=None, paths=None):
    """Cria o menu 'Ferramentas' com BOM, DRC, Eagle e Altium export."""
    menubar = win.menuBar()

    ferramentas_menu = QMenu('Ferr&amentas', win)
    menubar.addMenu(ferramentas_menu)

    # --- Gerar BOM ---
    act_bom = QAction('📊  Gerar BOM...', win)
    act_bom.setToolTip('Gera Bill of Materials (CSV) a partir dos componentes YAML')

    def _on_gerar_bom():
        output_path, _ = QFileDialog.getSaveFileName(
            win,
            'Salvar BOM como CSV',
            os.path.join(PROJ_DIR, 'saida', 'BOM.csv'),
            'CSV Files (*.csv);;All Files (*)',
        )
        if not output_path:
            return

        try:
            from core.gerador_bom import gerar_bom
            modulos_dir = os.path.join(PROJ_DIR, 'modulos_config')
            resultado = gerar_bom(modulos_dir, output_path)

            QMessageBox.information(
                win, 'BOM Gerado com Sucesso',
                f'\u2705  BOM gerado!\n\n'
                f'Componentes: {resultado["total"]}\n'
                f'Arquivo: {resultado["arquivo"]}\n\n'
                f'O arquivo CSV foi salvo com sucesso.',
            )
        except Exception as e:
            QMessageBox.critical(
                win, 'Erro ao Gerar BOM',
                f'\u274c  Erro ao gerar BOM:\n\n{type(e).__name__}: {e}',
            )

    act_bom.triggered.connect(_on_gerar_bom)
    ferramentas_menu.addAction(act_bom)

    # --- Relatório Técnico ---
    act_relatorio = QAction('🖨️  Relatório Técnico...', win)
    act_relatorio.setShortcut(QKeySequence('Ctrl+Shift+P'))
    act_relatorio.setToolTip('Gerar relatório técnico em PDF/HTML com réguas CAD')

    def _on_relatorio():
        from gui.dialogo_relatorio import DialogoRelatorio
        dlg = DialogoRelatorio(
            yaml_editor=panels['yaml_editor'] if panels else None,
            modulos_dir=os.path.join(PROJ_DIR, 'modulos_config'),
            saida_dir=os.path.join(PROJ_DIR, 'saida'),
            parent=win,
        )
        dlg.exec_()

    act_relatorio.triggered.connect(_on_relatorio)
    ferramentas_menu.addAction(act_relatorio)
    ferramentas_menu.addSeparator()

    # --- Verificar DRC ---
    act_drc = QAction('🔍  Verificar DRC...', win)
    act_drc.setToolTip('Executa verificação IPC + DRC no componente atual')

    def _on_verificar_drc():
        import yaml as _yaml
        yaml_editor = panels['yaml_editor'] if panels else None
        if yaml_editor is None:
            QMessageBox.warning(win, 'DRC', 'Editor YAML não disponível.')
            return

        # Obter dados YAML do editor
        try:
            texto = yaml_editor.editor.toPlainText()
            dados = _yaml.safe_load(texto)
        except Exception as ex:
            QMessageBox.critical(
                win, 'Erro DRC',
                f'Não foi possível ler o YAML:\n{ex}')
            return

        if not isinstance(dados, dict):
            QMessageBox.warning(
                win, 'DRC', 'O YAML não contém um dicionário válido.')
            return

        # Executar IPC
        ipc_text = ''
        try:
            from core.validador_ipc import validar_yaml
            ipc_result = validar_yaml(dados)
            ipc_lines = []
            for e in ipc_result.errors:   ipc_lines.append(f'❌ ERRO IPC: {e}')
            for w in ipc_result.warnings: ipc_lines.append(f'⚠️ AVISO IPC: {w}')
            for i in ipc_result.info:     ipc_lines.append(f'ℹ️ {i}')
            ipc_text = '\n'.join(ipc_lines)
        except Exception as ex:
            ipc_text = f'⚠️ Erro ao executar IPC: {ex}'

        # Executar DRC
        drc_text = ''
        try:
            from core.verificador_drc import verificar_drc
            drc_result = verificar_drc(dados)
            drc_lines = []
            for e in drc_result.errors:   drc_lines.append(f'❌ ERRO DRC: {e}')
            for w in drc_result.warnings: drc_lines.append(f'⚠️ AVISO DRC: {w}')
            for i in drc_result.info:     drc_lines.append(f'ℹ️ {i}')
            drc_text = '\n'.join(drc_lines)
        except Exception as ex:
            drc_text = f'⚠️ Erro ao executar DRC: {ex}'

        # Combinar resultados
        nome = dados.get('nome', '<sem nome>')
        header = f'Resultados para: {nome}\n{"═" * 50}\n'

        combined = header
        combined += '\n── Validação IPC-7351B ──\n'
        combined += (ipc_text if ipc_text else '✅ Nenhum problema IPC encontrado.')
        combined += '\n\n── Verificação DRC ──\n'
        combined += (drc_text if drc_text else '✅ Nenhum problema DRC encontrado.')

        # Determinar tipo de diálogo
        has_errors = False
        try:
            has_errors = (not ipc_result.ok) or (not drc_result.ok)
        except Exception:
            pass

        if has_errors:
            QMessageBox.warning(win, 'Resultado DRC + IPC', combined)
        else:
            QMessageBox.information(win, 'Resultado DRC + IPC', combined)

    act_drc.triggered.connect(_on_verificar_drc)
    ferramentas_menu.addAction(act_drc)
    ferramentas_menu.addSeparator()

    # --- Exportar Eagle (.lbr) ---
    act_eagle = QAction('🦅  Exportar Eagle (.lbr)...', win)
    act_eagle.setToolTip('Exporta o footprint atual para formato Eagle .lbr (XML)')

    def _on_exportar_eagle():
        import json as _json
        # Localizar .kicad_mod atual
        kicad_mod = ''
        estado_path = paths.get('estado', '') if paths else ''
        if estado_path and os.path.isfile(estado_path):
            try:
                with open(estado_path, 'r', encoding='utf-8') as f:
                    estado = _json.load(f)
                kicad_mod = estado.get('kicad_mod_path', '')
            except Exception:
                pass
        if not kicad_mod or not os.path.isfile(kicad_mod):
            kicad_mod, _ = QFileDialog.getOpenFileName(
                win, 'Selecionar .kicad_mod',
                os.path.join(PROJ_DIR, 'saida'),
                'KiCad Footprint (*.kicad_mod);;All Files (*)',
            )
        if not kicad_mod:
            return

        # Escolher saída
        default_out = os.path.splitext(kicad_mod)[0] + '.lbr'
        output_path, _ = QFileDialog.getSaveFileName(
            win, 'Salvar como Eagle .lbr', default_out,
            'Eagle Library (*.lbr);;All Files (*)',
        )
        if not output_path:
            return

        try:
            from core.exportar_eagle import kicad_to_eagle
            result_path = kicad_to_eagle(kicad_mod, output_path)
            QMessageBox.information(
                win, 'Eagle Export',
                f'✅  Exportado com sucesso!\n\n'
                f'Arquivo: {result_path}')
        except Exception as e:
            QMessageBox.critical(
                win, 'Erro Eagle Export',
                f'❌  Erro ao exportar:\n\n{type(e).__name__}: {e}')

    act_eagle.triggered.connect(_on_exportar_eagle)
    ferramentas_menu.addAction(act_eagle)

    # --- Exportar Altium (CSV) ---
    act_altium = QAction('📐  Exportar Altium (CSV)...', win)
    act_altium.setToolTip('Exporta o footprint atual para formato Altium CSV importável')

    def _on_exportar_altium():
        import json as _json
        # Localizar .kicad_mod atual
        kicad_mod = ''
        estado_path = paths.get('estado', '') if paths else ''
        if estado_path and os.path.isfile(estado_path):
            try:
                with open(estado_path, 'r', encoding='utf-8') as f:
                    estado = _json.load(f)
                kicad_mod = estado.get('kicad_mod_path', '')
            except Exception:
                pass
        if not kicad_mod or not os.path.isfile(kicad_mod):
            kicad_mod, _ = QFileDialog.getOpenFileName(
                win, 'Selecionar .kicad_mod',
                os.path.join(PROJ_DIR, 'saida'),
                'KiCad Footprint (*.kicad_mod);;All Files (*)',
            )
        if not kicad_mod:
            return

        # Escolher saída
        default_out = os.path.splitext(kicad_mod)[0] + '_altium.csv'
        output_path, _ = QFileDialog.getSaveFileName(
            win, 'Salvar como Altium CSV', default_out,
            'CSV Files (*.csv);;All Files (*)',
        )
        if not output_path:
            return

        try:
            from core.exportar_altium import kicad_to_altium_csv
            result_path = kicad_to_altium_csv(kicad_mod, output_path)
            QMessageBox.information(
                win, 'Altium Export',
                f'✅  Exportado com sucesso!\n\n'
                f'Arquivo: {result_path}')
        except Exception as e:
            QMessageBox.critical(
                win, 'Erro Altium Export',
                f'❌  Erro ao exportar:\n\n{type(e).__name__}: {e}')

    act_altium.triggered.connect(_on_exportar_altium)
    ferramentas_menu.addAction(act_altium)


def _setup_help_dock(win):
    """Cria a janela flutuante de ajuda (HelpPanel) e atalho F1 para toggle."""
    from PyQt5.QtWidgets import QShortcut

    help_panel = HelpPanel(win)

    # Criar como dock flutuante (janela independente sobre o programa)
    dock_help = QDockWidget('📘  Referência YAML', win)
    dock_help.setObjectName('dock_help')
    dock_help.setWidget(help_panel)
    dock_help.setFeatures(
        QDockWidget.DockWidgetMovable |
        QDockWidget.DockWidgetFloatable |
        QDockWidget.DockWidgetClosable
    )
    dock_help.setFloating(True)  # janela flutuante, não encaixada
    dock_help.resize(750, 650)   # tamanho generoso
    dock_help.hide()

    # Estilizar a title bar do dock flutuante
    dock_help.setStyleSheet('''
        QDockWidget {
            font-size: 13px;
            font-weight: bold;
            color: #CDD6F4;
        }
        QDockWidget::title {
            background: #1E1E2E;
            padding: 8px;
            border-bottom: 1px solid #45475A;
        }
    ''')

    def _toggle_help():
        if dock_help.isVisible():
            dock_help.hide()
        else:
            # Centralizar sobre a janela principal
            win_geo = win.geometry()
            cx = win_geo.x() + (win_geo.width() - dock_help.width()) // 2
            cy = win_geo.y() + (win_geo.height() - dock_help.height()) // 2
            dock_help.move(max(0, cx), max(0, cy))
            dock_help.show()
            dock_help.raise_()
            help_panel.search_bar.setFocus()

    # Atalho F1 global
    shortcut_f1 = QShortcut(QKeySequence('F1'), win)
    shortcut_f1.setContext(Qt.ApplicationShortcut)
    shortcut_f1.activated.connect(_toggle_help)

    # Escape fecha a ajuda
    shortcut_esc = QShortcut(QKeySequence('Escape'), dock_help)
    shortcut_esc.activated.connect(dock_help.hide)

    return dock_help, _toggle_help


def _setup_ajuda_menu(win, dock_help=None, toggle_help=None):
    """Cria o menu 'Ajuda' com 'Referência YAML' e 'Sobre...'."""
    menubar = win.menuBar()

    ajuda_menu = QMenu('A&juda', win)
    menubar.addMenu(ajuda_menu)

    # Referência YAML (F1)
    if toggle_help is not None:
        act_ref = QAction('📘  Referência YAML', win)
        act_ref.setShortcut(QKeySequence('F1'))
        act_ref.setToolTip('Abrir/fechar painel de referência rápida YAML')
        act_ref.triggered.connect(toggle_help)
        ajuda_menu.addAction(act_ref)
        ajuda_menu.addSeparator()

    act_sobre = QAction('Sobre...', win)
    act_sobre.setToolTip('Informações sobre a plataforma')

    def _show_about():
        import sys
        from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel as _QLabel, QDialogButtonBox

        dlg = QDialog(win)
        dlg.setWindowTitle('Sobre — EDA Footprint Generator')
        dlg.setFixedSize(480, 340)
        dlg.setStyleSheet(
            'QDialog { background:#1E1E2E; }'
            'QLabel { color:#CDD6F4; }'
        )

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(30, 25, 30, 20)
        lay.setSpacing(8)

        # Título
        title = _QLabel('EDA Footprint Generator')
        title.setStyleSheet(
            'font-size:18px; font-weight:bold; color:#89B4FA; padding-bottom:4px;'
        )
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # Versão
        version = _QLabel(f'v{__version__}')
        version.setStyleSheet('font-size:14px; color:#A6E3A1;')
        version.setAlignment(Qt.AlignCenter)
        lay.addWidget(version)

        # Separador visual
        sep = _QLabel('')
        sep.setFixedHeight(1)
        sep.setStyleSheet('background:#313244; margin:8px 40px;')
        lay.addWidget(sep)

        # Descrição
        desc = _QLabel('Gerador de footprints, símbolos e modelos 3D\npara KiCad')
        desc.setStyleSheet('font-size:12px; color:#BAC2DE; padding:4px 0;')
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Info técnica
        info_text = (
            f'Python {sys.version.split()[0]}\n'
            f'PyQt5 {PYQT_VERSION_STR}  |  Qt {QT_VERSION_STR}'
        )
        info = _QLabel(info_text)
        info.setStyleSheet(
            'font-size:11px; color:#6C7086; font-family:Consolas; padding:8px 0;'
        )
        info.setAlignment(Qt.AlignCenter)
        lay.addWidget(info)

        lay.addStretch()

        # Botão OK
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.setStyleSheet(
            'QPushButton { background:#313244; color:#CDD6F4; border:none; '
            'padding:6px 24px; border-radius:4px; font-size:12px; }'
            'QPushButton:hover { background:#45475A; }'
        )
        btn_box.accepted.connect(dlg.accept)
        lay.addWidget(btn_box, alignment=Qt.AlignCenter)

        dlg.exec_()

    act_sobre.triggered.connect(_show_about)
    ajuda_menu.addAction(act_sobre)


# =============================================================================
# Editar menu — Preferências
# =============================================================================

def _setup_editar_menu(win):
    """Cria o menu 'Editar' com item 'Preferências...'."""
    menubar = win.menuBar()

    # Verificar se já existe um menu 'Editar'
    editar_menu = None
    for menu_action in menubar.actions():
        if menu_action.text().replace('&', '') in ('Editar', 'Edit'):
            editar_menu = menu_action.menu()
            break

    if editar_menu is None:
        editar_menu = QMenu('&Editar', win)
        # Inserir após o menu Arquivo
        inserted = False
        for i, menu_action in enumerate(menubar.actions()):
            txt = menu_action.text().replace('&', '')
            if txt in ('View', 'Visualizar', 'Ferramentas', 'Tools'):
                menubar.insertMenu(menu_action, editar_menu)
                inserted = True
                break
        if not inserted:
            menubar.addMenu(editar_menu)

    act_prefs = QAction('⚙  Preferências...', win)
    act_prefs.setShortcut(QKeySequence('Ctrl+,'))
    act_prefs.setToolTip('Abrir o diálogo de preferências da aplicação')

    def _show_preferences():
        dlg = QDialog(win)
        dlg.setWindowTitle('Preferências — Plataforma CAM-CAD')
        dlg.setFixedSize(520, 420)
        dlg.setStyleSheet(
            'QDialog { background:#1E1E2E; }'
            'QLabel { color:#CDD6F4; font-size:12px; }'
            'QTabWidget::pane { border:1px solid #45475A; background:#1E1E2E; }'
            'QTabBar::tab { background:#313244; color:#CDD6F4; padding:8px 18px;'
            '               border:1px solid #45475A; border-bottom:none;'
            '               border-top-left-radius:4px; border-top-right-radius:4px; }'
            'QTabBar::tab:selected { background:#1E1E2E; color:#89B4FA; }'
            'QTabBar::tab:hover { background:#45475A; }'
            'QGroupBox { color:#89B4FA; border:1px solid #45475A;'
            '            border-radius:6px; margin-top:12px; padding-top:16px;'
            '            font-size:12px; font-weight:bold; }'
            'QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }'
            'QSpinBox, QDoubleSpinBox, QLineEdit { background:#181825; color:#CDD6F4;'
            '    border:1px solid #45475A; border-radius:4px; padding:4px 8px;'
            '    font-size:12px; font-family:Consolas; }'
            'QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color:#89B4FA; }'
            'QCheckBox { color:#CDD6F4; font-size:12px; spacing:6px; }'
            'QCheckBox::indicator { width:16px; height:16px; border:2px solid #45475A;'
            '    border-radius:3px; background:#181825; }'
            'QCheckBox::indicator:checked { background:#89B4FA; border-color:#89B4FA; }'
        )

        main_lay = QVBoxLayout(dlg)
        main_lay.setContentsMargins(16, 12, 16, 12)

        tabs = QTabWidget()
        main_lay.addWidget(tabs)

        # ── Tab Geral ──
        tab_geral = QWidget()
        lay_geral = QVBoxLayout(tab_geral)
        lay_geral.setContentsMargins(16, 16, 16, 16)

        grp_output = QGroupBox('Saída')
        form_output = QFormLayout(grp_output)
        output_dir = QLineEdit(str(AppConfig.get('output/directory')))
        form_output.addRow('Diretório de saída:', output_dir)
        lay_geral.addWidget(grp_output)

        grp_auto = QGroupBox('Automação')
        form_auto = QFormLayout(grp_auto)
        chk_auto_gen = QCheckBox('Gerar automaticamente ao salvar')
        chk_auto_gen.setChecked(bool(AppConfig.get('general/auto_generate')))
        form_auto.addRow(chk_auto_gen)
        spn_autosave = QSpinBox()
        spn_autosave.setRange(500, 30000)
        spn_autosave.setSuffix(' ms')
        spn_autosave.setValue(int(AppConfig.get('general/auto_save_interval')))
        form_auto.addRow('Intervalo auto-save:', spn_autosave)
        lay_geral.addWidget(grp_auto)

        lay_geral.addStretch()
        tabs.addTab(tab_geral, 'Geral')

        # ── Tab Editor ──
        tab_editor = QWidget()
        lay_editor = QVBoxLayout(tab_editor)
        lay_editor.setContentsMargins(16, 16, 16, 16)

        grp_font = QGroupBox('Fonte')
        form_font = QFormLayout(grp_font)
        spn_fontsize = QSpinBox()
        spn_fontsize.setRange(8, 24)
        spn_fontsize.setSuffix(' pt')
        spn_fontsize.setValue(int(AppConfig.get('editor/font_size')))
        form_font.addRow('Tamanho da fonte:', spn_fontsize)
        lay_editor.addWidget(grp_font)

        lay_editor.addStretch()
        tabs.addTab(tab_editor, 'Editor')

        # ── Tab Visualizador ──
        tab_viewer = QWidget()
        lay_viewer = QVBoxLayout(tab_viewer)
        lay_viewer.setContentsMargins(16, 16, 16, 16)

        grp_grid = QGroupBox('Grid')
        form_grid = QFormLayout(grp_grid)
        spn_grid = QDoubleSpinBox()
        spn_grid.setRange(0.1, 10.0)
        spn_grid.setDecimals(2)
        spn_grid.setSuffix(' mm')
        spn_grid.setValue(float(AppConfig.get('grid/size')))
        form_grid.addRow('Tamanho do grid:', spn_grid)
        lay_viewer.addWidget(grp_grid)

        grp_bg = QGroupBox('Aparência')
        form_bg = QFormLayout(grp_bg)
        bg_edit = QLineEdit(str(AppConfig.get('viewer/background')))
        bg_edit.setPlaceholderText('#1A1A2E')
        form_bg.addRow('Cor de fundo (hex):', bg_edit)
        lay_viewer.addWidget(grp_bg)

        lay_viewer.addStretch()
        tabs.addTab(tab_viewer, 'Visualizador')

        # ── Botões OK / Cancelar ──
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.setStyleSheet(
            'QPushButton { background:#313244; color:#CDD6F4; border:none;'
            '              padding:6px 20px; border-radius:4px; font-size:12px; }'
            'QPushButton:hover { background:#45475A; }'
        )

        def _on_ok():
            AppConfig.set('output/directory', output_dir.text())
            AppConfig.set('general/auto_generate', chk_auto_gen.isChecked())
            AppConfig.set('general/auto_save_interval', spn_autosave.value())
            AppConfig.set('editor/font_size', spn_fontsize.value())
            AppConfig.set('grid/size', spn_grid.value())
            AppConfig.set('viewer/background', bg_edit.text())
            AppConfig.sync()
            dlg.accept()

        btn_box.accepted.connect(_on_ok)
        btn_box.rejected.connect(dlg.reject)
        main_lay.addWidget(btn_box)

        dlg.exec_()

    act_prefs.triggered.connect(_show_preferences)
    editar_menu.addAction(act_prefs)


# =============================================================================
# Wizard de criação de componente
# =============================================================================

def _setup_wizard_menu(win, panels, paths):
    """Adiciona 'Novo Componente (Wizard)...' ao menu Arquivo."""
    yaml_editor = panels['yaml_editor']
    menubar = win.menuBar()

    # Localizar menu Arquivo
    arquivo_menu = None
    for menu_action in menubar.actions():
        if menu_action.text().replace('&', '') in ('Arquivo', 'File'):
            arquivo_menu = menu_action.menu()
            break

    if arquivo_menu is None:
        return  # menu Arquivo será criado por _setup_arquivo_menu

    act_wizard = QAction('🧙  Novo Componente (Wizard)...', win)
    act_wizard.setShortcut(QKeySequence('Ctrl+Shift+N'))
    act_wizard.setToolTip('Assistente guiado para criar um novo componente')

    def _on_wizard():
        from gui.wizard_componente import WizardComponente
        wizard = WizardComponente(win)

        def _on_criado(yaml_path):
            yaml_editor.load_file(yaml_path)
            yaml_editor._write_estado()
            yaml_editor._on_gerar()
            log.info('Componente criado via Wizard: %s', yaml_path)

        wizard.sigComponenteCriado.connect(_on_criado)
        wizard.exec_()

    act_wizard.triggered.connect(_on_wizard)

    # Inserir no topo do menu Arquivo
    first_action = arquivo_menu.actions()[0] if arquivo_menu.actions() else None
    if first_action:
        arquivo_menu.insertAction(first_action, act_wizard)
        arquivo_menu.insertSeparator(first_action)
    else:
        arquivo_menu.addAction(act_wizard)


# =============================================================================
# Arquivo menu — Arquivos Recentes
# =============================================================================

_MAX_RECENT = 5


def _load_recent_files(estado_path: str) -> list:
    """Lê a lista de arquivos recentes do _estado_atual.json."""
    import json
    if not os.path.isfile(estado_path):
        return []
    try:
        with open(estado_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        recent = data.get('recent_files', [])
        return [p for p in recent if isinstance(p, str)][:_MAX_RECENT]
    except Exception:
        return []


def _save_recent_files(estado_path: str, recent: list):
    """Salva a lista de arquivos recentes no _estado_atual.json."""
    import json
    data = {}
    if os.path.isfile(estado_path):
        try:
            with open(estado_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    data['recent_files'] = recent[:_MAX_RECENT]
    try:
        with open(estado_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _add_to_recent(estado_path: str, filepath: str):
    """Adiciona um arquivo ao topo da lista de recentes (sem duplicatas)."""
    filepath = os.path.abspath(filepath)
    recent = _load_recent_files(estado_path)
    # Remove duplicatas
    recent = [p for p in recent if os.path.abspath(p) != filepath]
    recent.insert(0, filepath)
    recent = recent[:_MAX_RECENT]
    _save_recent_files(estado_path, recent)
    return recent


def _setup_arquivo_menu(win, panels, paths):
    """Cria o menu 'Arquivo' com sub-menu 'Arquivos Recentes'."""
    yaml_editor = panels['yaml_editor']
    estado_path = paths['estado']
    menubar = win.menuBar()

    # Verificar se já existe um menu 'Arquivo'
    arquivo_menu = None
    for menu_action in menubar.actions():
        if menu_action.text().replace('&', '') in ('Arquivo', 'File'):
            arquivo_menu = menu_action.menu()
            break

    if arquivo_menu is None:
        arquivo_menu = QMenu('&Arquivo', win)
        # Inserir como primeiro menu
        first_action = menubar.actions()[0] if menubar.actions() else None
        if first_action:
            menubar.insertMenu(first_action, arquivo_menu)
        else:
            menubar.addMenu(arquivo_menu)

    # Sub-menu Arquivos Recentes
    recent_menu = QMenu('📂  Arquivos Recentes', win)
    arquivo_menu.addSeparator()
    arquivo_menu.addMenu(recent_menu)

    def _populate_recent_menu():
        recent_menu.clear()
        recent = _load_recent_files(estado_path)
        if not recent:
            act = recent_menu.addAction('(nenhum arquivo recente)')
            act.setEnabled(False)
            return
        for filepath in recent:
            if not os.path.isfile(filepath):
                continue
            display = os.path.basename(filepath)
            act = recent_menu.addAction(display)
            act.setToolTip(filepath)
            act.triggered.connect(
                lambda checked, p=filepath: _open_recent(p)
            )

    def _open_recent(filepath):
        """Abre um arquivo YAML recente no editor."""
        if os.path.isfile(filepath):
            yaml_editor.load_file(filepath)
            yaml_editor._write_estado()
            yaml_editor._on_gerar()
            _add_to_recent(estado_path, filepath)
            _populate_recent_menu()

    # Registrar arquivo quando o YAML editor carrega um arquivo
    def _on_yaml_loaded(yaml_path):
        if yaml_path and os.path.isfile(yaml_path):
            _add_to_recent(estado_path, yaml_path)
            _populate_recent_menu()

    try:
        yaml_editor.sigFileLoaded.connect(_on_yaml_loaded)
    except Exception:
        pass

    # Popular na inicialização
    _populate_recent_menu()

    # Adicionar arquivo atual à lista de recentes
    if os.path.isfile(paths.get('yaml', '')):
        _add_to_recent(estado_path, paths['yaml'])
        _populate_recent_menu()

    # Mostrar menu ao passar o mouse (já temos estilo global)
    recent_menu.aboutToShow.connect(_populate_recent_menu)


def _setup_persistence(app, win, docks):
    """Configura salvar/restaurar layout da janela."""
    _settings = QSettings('CAD-Data-Frontier', 'Plataforma-CAM-CAD')
    
    # Forçar reset de layout uma vez para aplicar a nova disposição lado-a-lado
    if not _settings.value('layout_v3_clean_cq', False):
        _settings.remove('window/geometry')
        _settings.remove('window/state')
        _settings.setValue('layout_v3_clean_cq', True)
        
    _has_saved = bool(_settings.value('window/state'))

    def _set_initial_sizes():
        try:
            win.resizeDocks([docks['yaml'], docks['2d']], [340, 420], Qt.Horizontal)
        except Exception:
            pass

    if not _has_saved:
        QTimer.singleShot(300, _set_initial_sizes)

    def _restaurar_layout():
        geom = _settings.value('window/geometry')
        state = _settings.value('window/state')
        if geom:
            win.restoreGeometry(geom)
        if state:
            win.restoreState(state)
            log.info("Layout restaurado.")

        if hasattr(win, 'toolbar') and not win.toolbar.isVisible():
            win.toolbar.setVisible(True)

        # Guarda de segurança: docks críticos devem estar visíveis
        docks_criticos = [
            (docks['yaml'],       "YAML Editor"),
            (docks['2d'],         "Footprint 2D"),
            (docks['symbol'],     "Simbolo Esquematico"),
            (docks['biblioteca'], "Biblioteca"),
        ]
        
        obj_dock = win.docks.get('object_tree') or win.docks.get('objects')
        if obj_dock and isinstance(obj_dock, QDockWidget):
            docks_criticos.append((obj_dock, "Arvore de Objetos"))
        ocultos = [(d, n) for d, n in docks_criticos if not d.isVisible()]
        if ocultos:
            nomes = ', '.join(n for _, n in ocultos)
            log.info("Docks ocultos detectados (%s) — restaurando.", nomes)
            for d, _ in ocultos:
                d.setVisible(True)
                d.raise_()
            try:
                win.resizeDocks([docks['yaml'], docks['2d']], [340, 420], Qt.Horizontal)
            except Exception:
                pass
        docks['yaml'].raise_()

        # Forçar help dock a ficar flutuante e oculto (restoreState pode encaixar)
        try:
            dock_help = win.findChild(QDockWidget, 'dock_help')
            if dock_help:
                dock_help.setFloating(True)
                dock_help.hide()
        except Exception:
            pass

    QTimer.singleShot(200, _restaurar_layout)

    def _salvar_layout():
        _settings.setValue('window/geometry', win.saveGeometry())
        _settings.setValue('window/state',    win.saveState())
        log.info("Layout salvo.")

    app.aboutToQuit.connect(_salvar_layout)


def _setup_file_watcher(win, paths, viewer_2d):
    """Configura watcher para auto-reload de arquivos gerados."""
    watcher = QFileSystemWatcher(win)
    kicad_mod = paths['kicad_mod']
    saida_dir = paths['saida_dir']

    if os.path.isfile(kicad_mod):
        watcher.addPath(kicad_mod)
    watcher.addPath(saida_dir)

    def _on_file_changed(path):
        if os.path.isfile(path):
            watcher.addPath(path)
        viewer_2d.reload_file()

    def _on_dir_changed(path):
        if os.path.isfile(kicad_mod):
            if kicad_mod not in watcher.files():
                watcher.addPath(kicad_mod)
            viewer_2d.reload_file()

    watcher.fileChanged.connect(_on_file_changed)
    watcher.directoryChanged.connect(_on_dir_changed)


# =============================================================================
# main() — orquestrador enxuto
# =============================================================================

def main():
    app = _create_app()

    # --- Splash Screen ---
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    splash.set_progress('Carregando caminhos...', 10)
    paths = _init_paths()

    splash.set_progress('Inicializando motor 3D...', 20)
    win = MainWindow(
        filename=paths['script'] if os.path.isfile(paths['script']) else None
    )
    win.setWindowTitle('EDA Footprint Generator')
    # Definir ícone da janela
    _icon_path = os.path.join(PROJ_DIR, 'assets', 'app_icon.ico')
    if os.path.isfile(_icon_path):
        win.setWindowIcon(QIcon(_icon_path))


    splash.set_progress('Criando painéis...', 40)
    panels = _create_panels(win, paths)
    docks = _create_docks(win, panels)

    splash.set_progress('Configurando toolbar...', 50)
    _setup_toolbar(win, panels['yaml_editor'])
    _setup_layout(win, docks)

    # --- Fase 3: Purgar menus CQ-Editor ANTES de criar os da plataforma ---
    _purge_cqeditor_menus(win)

    # --- Fase 5: Override closeEvent para evitar diálogo CQ-Editor ---
    _original_closeEvent = win.closeEvent

    def _clean_closeEvent(event):
        """Fecha direto sem perguntar 'Save changes to .py?' do CQ-Editor."""
        _settings_close = QSettings('CAD-Data-Frontier', 'Plataforma-CAM-CAD')
        _settings_close.setValue('window/geometry', win.saveGeometry())
        _settings_close.setValue('window/state', win.saveState())
        event.accept()

    win.closeEvent = _clean_closeEvent

    splash.set_progress('Conectando sinais...', 60)
    _setup_signals(win, panels, docks, paths)
    _setup_view_menu(win, docks)
    _setup_arquivo_menu(win, panels, paths)
    _setup_editar_menu(win)
    _setup_wizard_menu(win, panels, paths)
    _setup_ferramentas_menu(win, panels, paths)

    splash.set_progress('Restaurando layout...', 70)
    _setup_persistence(app, win, docks)
    _setup_file_watcher(win, paths, panels['viewer_2d'])
    _setup_status_bar(win, panels)

    splash.set_progress('Configurando ajuda...', 85)
    dock_help, toggle_help = _setup_help_dock(win)
    _setup_ajuda_menu(win, dock_help, toggle_help)

    splash.set_progress('Pronto!', 100)

    win.setMinimumSize(1024, 600)
    win.resize(1200, 800)
    win.showNormal()
    win.show()
    splash.finish(win)

    if os.path.isfile(paths['kicad_mod']):
        QTimer.singleShot(500, panels['viewer_2d'].reload_file)

    log.info("Interface iniciada.")
    log.info("Motor 3D : %s", paths['script'])
    log.info("YAML     : %s", paths['yaml'])
    log.info("Monitor  : %s", paths['kicad_mod'])
    log.info("F5 e botao nativo redirecionados para Atualizar 2D + 3D.")

    return app.exec_()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n\n*** ERRO FATAL: {e} ***")
        input("\nPressione ENTER para fechar...")
        sys.exit(1)
