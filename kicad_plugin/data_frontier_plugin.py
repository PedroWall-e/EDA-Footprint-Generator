"""
EDA Footprint Generator — Plugin KiCad (pcbnew).

Este plugin adiciona uma ação ao menu do PCB Editor do KiCad que permite
gerar footprints a partir de definições YAML e importá-los diretamente
no PCB atual.

Requisitos:
  - KiCad 7.x ou 8.x com pcbnew Python API
  - Plataforma EDA Footprint Generator instalada (core/ com gerador_footprint.py)
  - PyYAML (pip install pyyaml)

Instalação:
  1. Copie a pasta kicad_plugin/ para o diretório de plugins do KiCad:
     - Windows: %APPDATA%/kicad/<version>/scripting/plugins/
     - Linux:   ~/.local/share/kicad/<version>/scripting/plugins/
     - macOS:   ~/Library/Preferences/kicad/<version>/scripting/plugins/
  2. Reinicie o KiCad
  3. O plugin aparecerá em: Tools → External Plugins → EDA Footprint Generator

Uso via kicad-cli:
  kicad-cli fp-lib-table --add <library_path> --name DataFrontier
"""

import os
import sys
import logging
import json
import subprocess

log = logging.getLogger(__name__)

# Tentar importar pcbnew (só disponível dentro do KiCad)
try:
    import pcbnew
    import wx
    _IN_KICAD = True
except ImportError:
    _IN_KICAD = False
    log.info("pcbnew não disponível — executando fora do KiCad")


# =============================================================================
# Helpers
# =============================================================================

def _get_plugin_dir():
    """Retorna o diretório do plugin."""
    return os.path.dirname(os.path.abspath(__file__))


def _get_project_dir():
    """Retorna o diretório raiz do projeto EDA Footprint Generator."""
    plugin_dir = _get_plugin_dir()
    # O plugin está em: <project>/kicad_plugin/
    return os.path.dirname(plugin_dir)


def _ensure_paths():
    """Garante que os caminhos do projeto estão no sys.path."""
    project_dir = _get_project_dir()
    core_dir = os.path.join(project_dir, 'core')
    for p in [project_dir, core_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)


def _load_metadata():
    """Carrega metadata.json do plugin."""
    meta_path = os.path.join(_get_plugin_dir(), 'metadata.json')
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'name': 'EDA Footprint Generator',
            'version': '2.0.0',
        }


# =============================================================================
# Geração de footprint a partir de YAML
# =============================================================================

def generate_from_yaml(yaml_path: str, output_dir: str = None) -> dict:
    """Gera footprint a partir de um arquivo YAML.

    Args:
        yaml_path: Caminho para o arquivo YAML do componente.
        output_dir: Diretório de saída (default: <project>/saida/).

    Returns:
        dict com chaves:
            - 'kicad_mod': caminho do .kicad_mod gerado
            - 'nome': nome do componente
            - 'success': True se gerado com sucesso
            - 'error': mensagem de erro (se houver)
    """
    _ensure_paths()

    try:
        import yaml
    except ImportError:
        return {'success': False, 'error': 'PyYAML não instalado. Execute: pip install pyyaml'}

    # Carregar YAML
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            dados = yaml.safe_load(f)
    except Exception as e:
        return {'success': False, 'error': f'Erro ao carregar YAML: {e}'}

    if not isinstance(dados, dict):
        return {'success': False, 'error': 'YAML não contém um dicionário válido'}

    nome = dados.get('nome', 'Componente')

    # Diretório de saída
    if output_dir is None:
        output_dir = os.path.join(_get_project_dir(), 'saida')
    os.makedirs(output_dir, exist_ok=True)

    # Gerar footprint
    try:
        from gerador_footprint_v2 import gerar_footprint_universal
        kicad_mod_path = os.path.join(output_dir, f"{nome}.kicad_mod")
        gerar_footprint_universal(dados, kicad_mod_path)
        return {
            'success': True,
            'kicad_mod': kicad_mod_path,
            'nome': nome,
            'error': None,
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Erro ao gerar footprint: {type(e).__name__}: {e}',
        }


def install_library_via_cli(lib_path: str, lib_name: str = 'DataFrontier') -> bool:
    """Instala uma biblioteca no KiCad.

    Args:
        lib_path: Caminho para o diretório .pretty ou arquivo .kicad_mod.
        lib_name: Nome da biblioteca na tabela.

    Returns:
        True se o comando foi executado com sucesso.
    """
    # NOTA: O comando 'kicad-cli fp-lib-table --add' NÃO EXISTE no kicad-cli.
    # O kicad-cli não possui subcomando para manipular fp-lib-table.
    # Para instalar bibliotecas, use a interface do KiCad:
    #   Preferences → Manage Footprint Libraries → Add
    # Ou edite manualmente o arquivo fp-lib-table.kicad_lib.
    log.warning(
        f'install_library_via_cli() desabilitado: kicad-cli não suporta '
        f'"fp-lib-table --add". Instale a biblioteca "{lib_name}" '
        f'manualmente via Preferences → Manage Footprint Libraries.'
    )
    return False


# =============================================================================
# Plugin KiCad (pcbnew ActionPlugin)
# =============================================================================

if _IN_KICAD:

    class DataFrontierDialog(wx.Dialog):
        """Diálogo wx para selecionar YAML e gerar footprint."""

        def __init__(self, parent):
            meta = _load_metadata()
            super().__init__(
                parent,
                title=meta.get('name', 'EDA Footprint Generator'),
                size=(520, 380),
                style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            )

            self._yaml_path = ''
            self._result = None

            self._init_ui()
            self.CenterOnParent()

        def _init_ui(self):
            """Constrói a interface do diálogo."""
            panel = wx.Panel(self)
            main_sizer = wx.BoxSizer(wx.VERTICAL)

            # Título
            title = wx.StaticText(
                panel, label='EDA Footprint Generator — Footprint Generator')
            title_font = title.GetFont()
            title_font.SetPointSize(14)
            title_font.MakeBold()
            title.SetFont(title_font)
            main_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 15)

            # Separador
            main_sizer.Add(
                wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

            # Seletor de arquivo YAML
            file_sizer = wx.BoxSizer(wx.HORIZONTAL)
            lbl = wx.StaticText(panel, label='Arquivo YAML:')
            file_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

            self._txt_path = wx.TextCtrl(panel, style=wx.TE_READONLY)
            self._txt_path.SetHint('Selecione um arquivo YAML...')
            file_sizer.Add(self._txt_path, 1, wx.EXPAND | wx.RIGHT, 8)

            btn_browse = wx.Button(panel, label='Procurar...')
            btn_browse.Bind(wx.EVT_BUTTON, self._on_browse)
            file_sizer.Add(btn_browse, 0)

            main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 15)

            # Opções
            opts_box = wx.StaticBox(panel, label='Opções')
            opts_sizer = wx.StaticBoxSizer(opts_box, wx.VERTICAL)

            self._chk_import = wx.CheckBox(
                panel, label='Importar footprint no PCB atual')
            self._chk_import.SetValue(True)
            opts_sizer.Add(self._chk_import, 0, wx.ALL, 5)

            self._chk_lib = wx.CheckBox(
                panel, label='Instalar como biblioteca KiCad (via kicad-cli)')
            self._chk_lib.SetValue(False)
            opts_sizer.Add(self._chk_lib, 0, wx.ALL, 5)

            main_sizer.Add(opts_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

            # Log/status
            self._txt_log = wx.TextCtrl(
                panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
            self._txt_log.SetMinSize((-1, 80))
            main_sizer.Add(self._txt_log, 1, wx.EXPAND | wx.ALL, 15)

            # Botões
            btn_sizer = wx.StdDialogButtonSizer()
            self._btn_generate = wx.Button(panel, wx.ID_OK, 'Gerar Footprint')
            self._btn_generate.Bind(wx.EVT_BUTTON, self._on_generate)
            self._btn_generate.Enable(False)
            btn_sizer.AddButton(self._btn_generate)

            btn_cancel = wx.Button(panel, wx.ID_CANCEL, 'Fechar')
            btn_sizer.AddButton(btn_cancel)
            btn_sizer.Realize()

            main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

            panel.SetSizer(main_sizer)

        def _log(self, msg):
            """Adiciona mensagem ao log do diálogo."""
            self._txt_log.AppendText(msg + '\n')

        def _on_browse(self, event):
            """Abre file dialog para selecionar YAML."""
            dlg = wx.FileDialog(
                self,
                message='Selecionar arquivo YAML',
                wildcard='YAML files (*.yaml;*.yml)|*.yaml;*.yml|All files (*.*)|*.*',
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )

            # Iniciar no diretório modulos_config se existir
            modulos_dir = os.path.join(_get_project_dir(), 'modulos_config')
            if os.path.isdir(modulos_dir):
                dlg.SetDirectory(modulos_dir)

            if dlg.ShowModal() == wx.ID_OK:
                self._yaml_path = dlg.GetPath()
                self._txt_path.SetValue(self._yaml_path)
                self._btn_generate.Enable(True)
                self._log(f'Arquivo selecionado: {os.path.basename(self._yaml_path)}')

            dlg.Destroy()

        def _on_generate(self, event):
            """Gera o footprint e opcionalmente importa no PCB."""
            if not self._yaml_path:
                return

            self._log('Gerando footprint...')
            self._btn_generate.Enable(False)
            wx.Yield()

            result = generate_from_yaml(self._yaml_path)

            if not result.get('success'):
                self._log(f'❌ Erro: {result.get("error", "Erro desconhecido")}')
                self._btn_generate.Enable(True)
                return

            kicad_mod = result['kicad_mod']
            nome = result.get('nome', 'Componente')
            self._log(f'✅ Footprint gerado: {os.path.basename(kicad_mod)}')

            # Importar no PCB atual
            if self._chk_import.GetValue():
                try:
                    board = pcbnew.GetBoard()
                    if board:
                        fp = pcbnew.FootprintLoad(
                            os.path.dirname(kicad_mod),
                            os.path.splitext(os.path.basename(kicad_mod))[0]
                        )
                        if fp:
                            board.Add(fp)
                            pcbnew.Refresh()
                            self._log(f'✅ Footprint importado no PCB')
                        else:
                            self._log('⚠️ Não foi possível carregar o footprint')
                    else:
                        self._log('⚠️ Nenhum PCB aberto')
                except Exception as e:
                    self._log(f'⚠️ Erro ao importar: {e}')

            # Instalar biblioteca
            if self._chk_lib.GetValue():
                self._log('Instalando biblioteca via kicad-cli...')
                success = install_library_via_cli(kicad_mod, 'DataFrontier')
                if success:
                    self._log('✅ Biblioteca instalada')
                else:
                    self._log('⚠️ kicad-cli não disponível. '
                              'Instale manualmente via: '
                              'Preferences → Manage Footprint Libraries')

            self._btn_generate.Enable(True)
            self._result = result

        def get_result(self):
            """Retorna o resultado da geração."""
            return self._result


    class DataFrontierPlugin(pcbnew.ActionPlugin):
        """Plugin registrado no menu Tools do KiCad pcbnew."""

        def defaults(self):
            meta = _load_metadata()
            self.name = meta.get('name', 'EDA Footprint Generator')
            self.category = 'Footprint Generation'
            self.description = meta.get(
                'description', 'Generate footprints from YAML definitions')
            self.show_toolbar_button = True

            # Ícone (opcional)
            icon_path = os.path.join(_get_plugin_dir(), 'icon.png')
            if os.path.isfile(icon_path):
                self.icon_file_name = icon_path

        def Run(self):
            """Executado quando o plugin é ativado no KiCad."""
            dlg = DataFrontierDialog(None)
            dlg.ShowModal()
            dlg.Destroy()


    # Registrar plugin
    DataFrontierPlugin().register()


# =============================================================================
# Execução standalone (fora do KiCad)
# =============================================================================

def main():
    """Execução standalone para testes."""
    import argparse

    parser = argparse.ArgumentParser(
        description='EDA Footprint Generator — KiCad Plugin')
    parser.add_argument('yaml_file', help='Arquivo YAML do componente')
    parser.add_argument('-o', '--output', help='Diretório de saída',
                        default=None)
    parser.add_argument('--install', action='store_true',
                        help='Instalar como biblioteca KiCad')

    args = parser.parse_args()

    if not os.path.isfile(args.yaml_file):
        print(f'Erro: arquivo não encontrado: {args.yaml_file}')
        sys.exit(1)

    result = generate_from_yaml(args.yaml_file, args.output)

    if result.get('success'):
        print(f'✅ Footprint gerado: {result["kicad_mod"]}')
        if args.install:
            success = install_library_via_cli(result['kicad_mod'])
            if success:
                print('✅ Biblioteca instalada')
            else:
                print('⚠️ Falha ao instalar biblioteca')
    else:
        print(f'❌ Erro: {result.get("error")}')
        sys.exit(1)


if __name__ == '__main__':
    main()
