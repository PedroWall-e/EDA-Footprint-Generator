# =============================================================================
# TESTES GUI — EDA Footprint Generator
# =============================================================================
# Testa funções de lógica pura e widgets PyQt5 da GUI.
#
# Execute:
#   python tests/teste_gui.py
# =============================================================================

import os
import sys
import tempfile
import shutil
import traceback

# Adicionar pasta do projeto ao path
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
sys.path.insert(0, os.path.join(PROJ, 'core'))
sys.path.insert(0, os.path.join(PROJ, 'gui'))

# Forçar flush imediato no stdout
sys.stdout.reconfigure(encoding='utf-8')

# ─── Contadores ──────────────────────────────────────────────────────────────
_total = 0
_ok = 0
_fail = 0
_erros = []

def teste(nome, func):
    """Executa uma função de teste e reporta resultado."""
    global _total, _ok, _fail
    _total += 1
    try:
        func()
        _ok += 1
        print(f"  ✅ PASSOU: {nome}", flush=True)
    except Exception as e:
        _fail += 1
        msg = f"  ❌ FALHOU: {nome} → {e}"
        print(msg, flush=True)
        _erros.append((nome, str(e), traceback.format_exc()))

def header(titulo):
    print(f"\n{'='*70}", flush=True)
    print(f"  {titulo}", flush=True)
    print(f"{'='*70}", flush=True)


# =============================================================================
# GRUPO 1: Lógica Pura (sem PyQt5)
# =============================================================================
def test_grupo1():
    header("GRUPO 1: Funções de lógica pura da GUI")

    from interface_dual import _find_first_yaml

    def t_find_yaml_normal():
        """Diretório com YAMLs → retorna primeiro não-preset."""
        config_dir = os.path.join(PROJ, 'modulos_config')
        result = _find_first_yaml(config_dir)
        assert result is not None, "Deveria encontrar um YAML"
        assert result.endswith(('.yaml', '.yml')), f"Não é YAML: {result}"
        basename = os.path.basename(result)
        assert not basename.startswith('_'), \
            f"Deveria retornar não-preset, retornou: {basename}"
    teste("_find_first_yaml — diretório normal", t_find_yaml_normal)

    def t_find_yaml_only_presets():
        """Diretório só com presets → retorna primeiro preset."""
        tmpdir = tempfile.mkdtemp()
        try:
            open(os.path.join(tmpdir, '_preset_a.yaml'), 'w').close()
            open(os.path.join(tmpdir, '_preset_b.yaml'), 'w').close()
            result = _find_first_yaml(tmpdir)
            assert result is not None, "Deveria retornar preset como fallback"
            assert '_preset_' in os.path.basename(result)
        finally:
            shutil.rmtree(tmpdir)
    teste("_find_first_yaml — só presets (fallback)", t_find_yaml_only_presets)

    def t_find_yaml_empty():
        """Diretório vazio → retorna None."""
        tmpdir = tempfile.mkdtemp()
        try:
            result = _find_first_yaml(tmpdir)
            assert result is None, f"Deveria retornar None, retornou: {result}"
        finally:
            shutil.rmtree(tmpdir)
    teste("_find_first_yaml — diretório vazio", t_find_yaml_empty)

    def t_init_paths():
        """_init_paths retorna dict com chaves esperadas."""
        from interface_dual import _init_paths
        paths = _init_paths()
        assert isinstance(paths, dict), f"Deveria retornar dict, é {type(paths)}"
        chaves = ['yaml', 'saida_dir']
        for chave in chaves:
            assert chave in paths, f"Chave '{chave}' ausente em paths"
        assert os.path.isdir(paths['saida_dir']), \
            f"saida_dir não existe: {paths['saida_dir']}"
    teste("_init_paths — retorna dict com chaves corretas", t_init_paths)


# =============================================================================
# GRUPO 2: Widgets PyQt5
# =============================================================================
def test_grupo2():
    header("GRUPO 2: Widgets PyQt5")

    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    def t_python_highlighter():
        """PythonHighlighter instancia e tem rules."""
        from widgets_common import PythonHighlighter
        from PyQt5.QtGui import QTextDocument
        doc = QTextDocument()
        hl = PythonHighlighter(doc)
        assert len(hl._rules) > 0, "Highlighter deveria ter rules"
        assert len(hl._rules) >= 3, \
            f"Esperado >= 3 regras (keywords, CQ, numbers), tem {len(hl._rules)}"
    teste("PythonHighlighter — instancia com rules", t_python_highlighter)

    def t_code_editor():
        """CodeEditor instancia e aceita texto."""
        from widgets_common import CodeEditor
        editor = CodeEditor()
        editor.setPlainText("# Teste\nprint('hello')")
        assert editor.toPlainText() == "# Teste\nprint('hello')"
        assert hasattr(editor, '_line_area'), "Falta _line_area (gutter)"
    teste("CodeEditor — instancia e aceita texto", t_code_editor)

    def t_yaml_highlighter():
        """YamlHighlighter instancia sem erro."""
        from painel_yaml_editor import YamlHighlighter
        from PyQt5.QtGui import QTextDocument
        doc = QTextDocument()
        hl = YamlHighlighter(doc)
        assert hl is not None
    teste("YamlHighlighter — instancia", t_yaml_highlighter)

    def t_palette_catppuccin():
        """Palette Catppuccin configura background escuro."""
        from PyQt5.QtGui import QPalette, QColor
        # Simular o que _create_app faz sem recriar QApplication
        palette = app.palette()
        palette.setColor(QPalette.Window, QColor(30, 30, 46))
        palette.setColor(QPalette.WindowText, QColor(205, 214, 244))
        palette.setColor(QPalette.Button, QColor(49, 50, 68))
        app.setPalette(palette)
        bg = app.palette().color(QPalette.Window)
        assert bg.red() < 100, f"Background deveria ser escuro, R={bg.red()}"
        text = app.palette().color(QPalette.WindowText)
        assert text.red() > 150, f"Texto deveria ser claro, R={text.red()}"
    teste("Palette Catppuccin — cores corretas", t_palette_catppuccin)

    def t_stylesheet_has_pushbutton():
        """Stylesheet global contém QPushButton."""
        # Ler o código-fonte de interface_dual.py e verificar o stylesheet
        import inspect
        from interface_dual import _create_app
        source = inspect.getsource(_create_app)
        assert 'QPushButton' in source, \
            "Stylesheet em _create_app deveria ter QPushButton"
        assert '#313244' in source, \
            "Stylesheet deveria usar cor Catppuccin #313244"
        assert 'QScrollBar' in source, \
            "Stylesheet deveria ter QScrollBar"
    teste("Stylesheet — QPushButton + QScrollBar presentes", t_stylesheet_has_pushbutton)


# =============================================================================
# GRUPO 3: Constantes e dados da GUI
# =============================================================================
def test_grupo3():
    header("GRUPO 3: Constantes e dados da GUI")

    def t_wizard_types():
        """wizard_componente.COMPONENT_TYPES é lista válida."""
        from wizard_componente import COMPONENT_TYPES
        assert isinstance(COMPONENT_TYPES, (list, tuple)), \
            f"COMPONENT_TYPES deveria ser lista, é {type(COMPONENT_TYPES)}"
        assert len(COMPONENT_TYPES) >= 5, \
            f"Esperado >= 5 tipos, tem {len(COMPONENT_TYPES)}"
        for item in COMPONENT_TYPES:
            assert isinstance(item, (dict, tuple, str)), \
                f"Tipo inválido na lista: {type(item)}"
    teste("COMPONENT_TYPES — lista válida", t_wizard_types)

    def t_dim_fields():
        """wizard_componente._DIM_FIELDS existe e é dict."""
        from wizard_componente import _DIM_FIELDS
        assert isinstance(_DIM_FIELDS, dict), \
            f"_DIM_FIELDS deveria ser dict, é {type(_DIM_FIELDS)}"
        assert len(_DIM_FIELDS) > 0, "_DIM_FIELDS está vazio"
    teste("_DIM_FIELDS — dict válido", t_dim_fields)


# =============================================================================
# EXECUÇÃO
# =============================================================================
if __name__ == '__main__':
    print("\n" + "="*70, flush=True)
    print("  TESTES GUI - EDA Footprint Generator", flush=True)
    print("="*70, flush=True)

    test_grupo1()   # Lógica pura (sem PyQt5)
    test_grupo3()   # Constantes e dados (antes do QApp para evitar CQ-Editor redirect)

    # Salvar stdout original antes de PyQt5 (CQ-Editor pode redirecionar)
    _orig_stdout = sys.stdout
    _orig_stderr = sys.stderr
    test_grupo2()   # Widgets PyQt5
    # Restaurar stdout/stderr — CQ-Editor redireciona para _PrintRedirectorSingleton
    sys.stdout = _orig_stdout if hasattr(_orig_stdout, 'write') else sys.__stdout__
    sys.stderr = _orig_stderr if hasattr(_orig_stderr, 'write') else sys.__stderr__
    # Fallback final: se o redirect do CQ-Editor corrompeu, usar __stdout__
    try:
        sys.stdout.write('')
    except (RuntimeError, OSError):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    # ── Relatório Final ──────────────────────────────────────────────────
    print(f"\n{'='*70}", flush=True)
    print(f"  RESULTADO FINAL — Testes GUI", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  Total:   {_total}", flush=True)
    print(f"  ✅ OK:    {_ok}", flush=True)
    print(f"  ❌ Falha: {_fail}", flush=True)
    print(f"{'='*70}", flush=True)

    if _erros:
        print(f"\n  DETALHES DOS ERROS:\n", flush=True)
        for nome, msg, tb in _erros:
            print(f"  ── {nome} ──", flush=True)
            print(f"     {msg}", flush=True)
            tb_lines = tb.strip().split('\n')
            for line in tb_lines[-3:]:
                print(f"     {line}", flush=True)
            print(flush=True)

    if _fail == 0:
        print("\n  🎉 TODOS OS TESTES GUI PASSARAM!\n", flush=True)
    else:
        print(f"\n  ⚠️  {_fail} teste(s) falharam.\n", flush=True)

    sys.exit(0 if _fail == 0 else 1)
