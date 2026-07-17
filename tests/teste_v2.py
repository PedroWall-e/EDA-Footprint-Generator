# =============================================================================
# ROTINA DE TESTES — EDA Footprint Generator v2.0
# =============================================================================
# Execute este script a partir da pasta do projeto:
#   python teste_v2.py
#
# Ele testa automaticamente todos os módulos refatorados e reporta
# PASSOU / FALHOU para cada teste.
# =============================================================================

import os
import sys
import json
import yaml
import traceback
import tempfile
import shutil
import copy
import re

# Forçar UTF-8 no stdout/stderr (evita UnicodeEncodeError com emojis ✅/❌ no
# console do Windows, que por padrão usa cp1252). Ver AGENTS.md regra 6.
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Adicionar pasta do projeto ao path
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
sys.path.insert(0, os.path.join(PROJ, 'core'))
sys.path.insert(0, os.path.join(PROJ, 'libs', 'kicad-footprint-generator'))
sys.path.insert(0, os.path.join(PROJ, 'KicadModTree_dev'))

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
        print(f"  ✅ PASSOU: {nome}")
    except Exception as e:
        _fail += 1
        msg = f"  ❌ FALHOU: {nome} → {e}"
        print(msg)
        _erros.append((nome, str(e), traceback.format_exc()))


def header(titulo):
    print(f"\n{'='*70}")
    print(f"  {titulo}")
    print(f"{'='*70}")


# =============================================================================
# GRUPO 1: Imports e Módulos
# =============================================================================
def test_grupo1():
    header("GRUPO 1: Verificar imports dos módulos")

    def t_import_helpers():
        from footprint_helpers import (
            draw_courtyard, draw_silkscreen_rect, draw_fab_rect,
            add_pth_pad, add_smd_pad, validate_annular_ring,
            postprocess_v6, save_footprint
        )
    teste("Import footprint_helpers", t_import_helpers)

    def t_import_v2():
        from gerador_footprint_v2 import gerar_footprint_universal, listar_padroes
        padroes = listar_padroes()
        assert 'axial_pth' in padroes, f"axial_pth não encontrado em {padroes}"
        assert 'custom' in padroes, f"custom não encontrado em {padroes}"
        assert 'single_row_pth' in padroes, f"single_row_pth ausente em {padroes}"
        assert len(padroes) == 8, f"Esperado 8 padrões, encontrado {len(padroes)}"
    teste("Import gerador_footprint_v2 (8 padrões)", t_import_v2)

    def t_import_validador():
        from validador_ipc import validar_yaml, IPCValidationResult
        r = IPCValidationResult()
        assert r.ok == True, "Resultado vazio deveria ser ok"
    teste("Import validador_ipc", t_import_validador)

    def t_import_symbol():
        from gerador_symbol import gerar_symbol
    teste("Import gerador_symbol", t_import_symbol)

    def t_v1_removido():
        """O motor v1 foi removido: tudo passa pelo v2 + shim tipo→padrao.

        Guarda de regressão — enquanto o v1 existia, a API o usava para
        `tipo:` e divergia da CLI (mesmo YAML, saídas diferentes).
        """
        try:
            import gerador_footprint  # noqa: F401
            assert False, "gerador_footprint (v1) deveria ter sido removido"
        except ImportError:
            pass  # esperado
    teste("Motor v1 removido (migração completa)", t_v1_removido)

    def t_api_usa_v2():
        """A API deve usar o mesmo motor da CLI (v2), nunca o v1."""
        api = open(os.path.join(PROJ, 'api_server.py'), encoding='utf-8').read()
        assert 'from gerador_footprint import' not in api, \
            "api_server.py não pode importar o motor v1"
        assert 'gerar_footprint_universal' in api, \
            "api_server.py deve usar o motor v2 (gerar_footprint_universal)"
    teste("API usa o motor v2 (igual à CLI)", t_api_usa_v2)

    def t_import_sexpr_parser():
        from sexpr_parser import parse_sexpr, find_all, find_one
    teste("Import sexpr_parser", t_import_sexpr_parser)

    def t_import_exportar():
        from exportar_biblioteca import exportar_todos
    teste("Import exportar_biblioteca", t_import_exportar)


# =============================================================================
# GRUPO 2: Validador IPC
# =============================================================================
def test_grupo2():
    header("GRUPO 2: Validador IPC-7351B")

    from validador_ipc import validar_yaml

    def t_yaml_valido():
        dados = {
            'nome': 'Teste_R470',
            'tipo': 'resistor_pth',
            'pinos': {'espacamento': 10.16, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'comprimento': 6.5, 'diametro': 2.5},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'R?', 'descricao': 'Resistor', 'tags': 'resistor', 'modelo_3d': 'R.step'}
        }
        r = validar_yaml(dados)
        assert r.ok, f"Deveria passar: {r}"
    teste("YAML válido passa sem erros", t_yaml_valido)

    def t_sem_nome():
        dados = {'tipo': 'resistor_pth'}
        r = validar_yaml(dados)
        assert not r.ok, "Deveria falhar sem nome"
        assert any('nome' in e.lower() for e in r.errors), f"Erro deveria mencionar 'nome': {r.errors}"
    teste("Rejeita YAML sem 'nome'", t_sem_nome)

    def t_sem_tipo_padrao():
        dados = {'nome': 'Teste'}
        r = validar_yaml(dados)
        assert not r.ok, "Deveria falhar sem tipo/padrao"
    teste("Rejeita YAML sem 'tipo' nem 'padrao'", t_sem_tipo_padrao)

    def t_annular_ring_ruim():
        dados = {
            'nome': 'Teste_Ring',
            'tipo': 'resistor_pth',
            'pinos': {'diametro_pad': 0.9, 'diametro_furo': 0.8},  # ring = 0.05mm < 0.15
            'kicad': {'referencia': 'R?', 'descricao': 'x', 'tags': 'x'}
        }
        r = validar_yaml(dados)
        has_ring_error = any('anel' in e.lower() or 'annular' in e.lower() or 'ring' in e.lower()
                           for e in r.errors + r.warnings)
        assert has_ring_error, f"Deveria detectar annular ring ruim: {r}"
    teste("Detecta annular ring insuficiente", t_annular_ring_ruim)

    def t_furo_minimo():
        dados = {
            'nome': 'Teste_Drill',
            'tipo': 'resistor_pth',
            'pinos': {'diametro_pad': 0.5, 'diametro_furo': 0.1},  # furo < 0.20mm
            'kicad': {'referencia': 'R?', 'descricao': 'x', 'tags': 'x'}
        }
        r = validar_yaml(dados)
        has_drill = any('furo' in e.lower() or 'drill' in e.lower()
                       for e in r.errors + r.warnings)
        assert has_drill, f"Deveria detectar furo muito pequeno: {r}"
    teste("Detecta furo < 0.20mm", t_furo_minimo)


# =============================================================================
# GRUPO 3: Motor Universal — Geração de Footprints
# =============================================================================
def test_grupo3():
    header("GRUPO 3: Motor Universal — Geração de Footprints")

    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_v2')
    os.makedirs(saida_dir, exist_ok=True)

    def t_axial_pth():
        dados = {
            'nome': 'TESTE_Resistor_Axial',
            'padrao': 'axial_pth',
            'pinos': {'espacamento': 10.16, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'formato': 'cilindro', 'diametro': 2.5, 'comprimento': 6.5},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'R.step', 'descricao': 'Resistor axial', 'tags': 'resistor'}
        }
        path = os.path.join(saida_dir, 'TESTE_axial_pth.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path), "Arquivo não criado"
        content = open(path, 'r', encoding='utf-8').read()
        assert '(footprint' in content or '(module' in content, "Conteúdo inválido"
    teste("axial_pth (resistor cilíndrico)", t_axial_pth)

    def t_radial_pth():
        dados = {
            'nome': 'TESTE_TO92',
            'padrao': 'radial_pth',
            'pinos': {'total': 3, 'pitch': 1.27, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'formato': 'dshape', 'diametro': 5.0},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'TO92.step', 'descricao': 'TO-92', 'tags': 'to92'}
        }
        path = os.path.join(saida_dir, 'TESTE_radial_pth.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        assert '(pad ' in content, "Nenhum pad encontrado"
        assert '(footprint' in content or '(module' in content
    teste("radial_pth (TO-92 dshape)", t_radial_pth)

    def t_dual_pth():
        dados = {
            'nome': 'TESTE_DIP8',
            'padrao': 'dual_pth',
            'pinos': {'total': 8, 'pitch': 2.54, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'largura': 6.35, 'comprimento': 9.9, 'afastamento_colunas': 7.62},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'DIP8.step', 'descricao': 'DIP-8', 'tags': 'dip'}
        }
        path = os.path.join(saida_dir, 'TESTE_dual_pth.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        assert '(pad ' in content, "Nenhum pad encontrado"
        assert content.count('(pad ') >= 8, f"DIP-8 deveria ter 8 pads, encontrado {content.count('(pad ')}"
    teste("dual_pth (DIP-8)", t_dual_pth)

    def t_dual_smd():
        dados = {
            'nome': 'TESTE_SOIC8',
            'padrao': 'dual_smd',
            'pinos': {'total': 8, 'pitch': 1.27, 'tamanho_pad': {'largura': 0.6, 'altura': 1.5}},
            'corpo': {'largura': 3.9, 'comprimento': 4.9, 'afastamento_colunas': 5.4},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'SOIC8.step', 'descricao': 'SOIC-8', 'tags': 'soic smd'}
        }
        path = os.path.join(saida_dir, 'TESTE_dual_smd.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        assert '(pad ' in content, "Nenhum pad encontrado"
        assert content.count('(pad ') >= 8, f"SOIC-8 deveria ter 8 pads"
        assert '(attr smd)' in content, "Falta attr smd"
    teste("dual_smd (SOIC-8)", t_dual_smd)

    def t_dual_smd_2pad():
        dados = {
            'nome': 'TESTE_0805',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0, 'tamanho_pad': {'largura': 1.0, 'altura': 1.1}},
            'corpo': {'largura': 2.0, 'comprimento': 1.25, 'afastamento_colunas': 2.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': '0805.step', 'descricao': '0805', 'tags': '0805 smd'}
        }
        path = os.path.join(saida_dir, 'TESTE_0805.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        assert content.count('(pad ') == 2, f"0805 deveria ter 2 pads"
    teste("dual_smd 2-pad (chip 0805)", t_dual_smd_2pad)

    def t_quad_smd():
        dados = {
            'nome': 'TESTE_QFP32',
            'padrao': 'quad_smd',
            'pinos': {'pitch': 0.8, 'tamanho_pad': {'largura': 0.5, 'altura': 1.2},
                      'por_lado': 8},
            'corpo': {'largura': 7.0, 'comprimento': 7.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'QFP32.step', 'descricao': 'QFP-32', 'tags': 'qfp smd'}
        }
        path = os.path.join(saida_dir, 'TESTE_quad_smd.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        assert '(pad ' in content, "Nenhum pad encontrado"
        assert '(attr smd)' in content, "Falta attr smd"
    teste("quad_smd (QFP-32)", t_quad_smd)

    def t_custom():
        dados = {
            'nome': 'TESTE_Antena',
            'padrao': 'custom',
            'pads': [
                {'numero': 1, 'nome': 'FEED', 'x': 0, 'y': 0,
                 'largura': 1.5, 'altura': 1.5, 'formato': 'retangulo', 'montagem': 'smd'},
                {'numero': 2, 'nome': 'GND', 'x': -10, 'y': -10,
                 'largura': 2.0, 'altura': 2.0, 'formato': 'circulo', 'montagem': 'smd'},
                {'numero': 3, 'nome': 'GND', 'x': 10, 'y': -10,
                 'largura': 2.0, 'altura': 2.0, 'formato': 'circulo', 'montagem': 'smd'},
                {'numero': 4, 'nome': 'MNT', 'x': 0, 'y': 8,
                 'largura': 1.6, 'altura': 1.6, 'formato': 'oval', 'montagem': 'pth', 'furo': 0.8},
            ],
            'corpo': {'largura': 25, 'comprimento': 25, 'formato': 'retangulo'},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'Antena.step', 'descricao': 'Antena custom', 'tags': 'antena'}
        }
        path = os.path.join(saida_dir, 'TESTE_custom.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        # Deve ter 4 pads
        pad_count = content.count('(pad ')
        assert pad_count == 4, f"Esperado 4 pads, encontrado {pad_count}"
    teste("custom (antena mista SMD+PTH)", t_custom)

    def t_padrao_invalido():
        dados = {'nome': 'Teste', 'padrao': 'invalido_xyz'}
        path = os.path.join(saida_dir, 'TESTE_invalido.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            assert False, "Deveria ter lançado ValueError"
        except ValueError as e:
            assert 'invalido_xyz' in str(e)
    teste("Rejeita padrão inválido", t_padrao_invalido)


# =============================================================================
# GRUPO 4: Motor v2 via Shim tipo→padrao — Componentes com tipo:
# =============================================================================
def test_grupo4():
    header("GRUPO 4: Shim tipo→padrao — Componentes com tipo:")

    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_shim')
    os.makedirs(saida_dir, exist_ok=True)

    yamls_dir = os.path.join(PROJ, 'modulos_config')
    componentes_teste = [
        ('resistor_470R.yaml', 'Resistor PTH', 'axial_pth'),
        ('1N4007_DO41.yaml', 'Diodo PTH', 'axial_pth'),
        ('NE555_DIP8.yaml', 'CI DIP-8', 'dual_pth'),
        ('NE555_SOIC8.yaml', 'CI SOIC-8', 'dual_smd'),
        ('BC547_TO92.yaml', 'Transistor TO-92', 'radial_pth'),
        ('LED_5mm_Vermelho.yaml', 'LED PTH', 'axial_pth'),
        ('Cap_100uF_16V.yaml', 'Capacitor PTH', 'axial_pth'),
        ('Crystal_16MHz_HC49.yaml', 'Crystal HC-49', 'axial_pth'),
        ('header_3pin.yaml', 'Conector 3-pin', 'dual_pth'),
    ]

    for yaml_file, desc, expected_padrao in componentes_teste:
        yaml_path = os.path.join(yamls_dir, yaml_file)
        if not os.path.exists(yaml_path):
            print(f"  ⚠️  SKIP: {yaml_file} não encontrado")
            continue

        def make_test(yp, d, ep):
            def t():
                with open(yp, 'r', encoding='utf-8') as f:
                    dados = yaml.safe_load(f)
                # Verificar que tem tipo: mas não padrao: (shim necessário)
                assert 'tipo' in dados, f"YAML deveria ter campo tipo:"
                out = os.path.join(saida_dir, dados['nome'] + '.kicad_mod')
                gerar_footprint_universal(dados, out)
                assert os.path.exists(out), f"Arquivo não criado: {out}"
                content = open(out, 'r', encoding='utf-8').read()
                assert len(content) > 200, f"Arquivo muito pequeno ({len(content)} chars)"
                assert '(pad ' in content, "Nenhum pad encontrado"
                assert '(footprint' in content or '(module' in content
            return t
        teste(f"Shim: {desc} ({yaml_file})", make_test(yaml_path, desc, expected_padrao))


# =============================================================================
# GRUPO 5: Gerador de Símbolos
# =============================================================================
def test_grupo5():
    header("GRUPO 5: Gerador de Símbolos")

    from gerador_symbol import gerar_symbol
    saida_dir = os.path.join(PROJ, 'saida', '_testes_sym')
    os.makedirs(saida_dir, exist_ok=True)

    yamls_dir = os.path.join(PROJ, 'modulos_config')
    componentes = [
        ('resistor_470R.yaml', 'Símbolo Resistor'),
        ('1N4007_DO41.yaml', 'Símbolo Diodo'),
        ('NE555_DIP8.yaml', 'Símbolo CI DIP (com pin_names)'),
        ('BC547_TO92.yaml', 'Símbolo Transistor'),
    ]

    for yaml_file, desc in componentes:
        yaml_path = os.path.join(yamls_dir, yaml_file)
        if not os.path.exists(yaml_path):
            print(f"  ⚠️  SKIP: {yaml_file} não encontrado")
            continue

        def make_test(yp, d):
            def t():
                with open(yp, 'r', encoding='utf-8') as f:
                    dados = yaml.safe_load(f)
                out = os.path.join(saida_dir, dados['nome'] + '.kicad_sym')
                gerar_symbol(dados, out)
                assert os.path.exists(out), f"Símbolo não criado: {out}"
                content = open(out, 'r', encoding='utf-8').read()
                assert '(symbol' in content, "Formato inválido"
                # Verificar campo Footprint preenchido (não vazio)
                assert '"Footprint" ""' not in content, \
                    "Campo Footprint vazio no .kicad_sym"
                # Verificar parênteses balanceados
                n_open = content.count('(')
                n_close = content.count(')')
                assert n_open == n_close, \
                    f"Parênteses desbalanceados: {n_open} abre vs {n_close} fecha"
                # Verificar que não tem ((size — bug #1 sessão anterior
                assert '((size' not in content, \
                    "Parênteses duplos em (size) detectados"
                # Verificar pin_names se existirem
                if 'pin_names' in dados:
                    content_lower = content.lower()
                    for pname in dados['pin_names'].values():
                        assert pname.lower() in content_lower or pname.upper() in content, \
                            f"Pin name '{pname}' não encontrado no símbolo"
            return t
        teste(f"{desc} ({yaml_file})", make_test(yaml_path, desc))


# =============================================================================
# GRUPO 6: Formato v6+ (pós-processamento)
# =============================================================================
def test_grupo6():
    header("GRUPO 6: Formato KiCad v6+")

    from footprint_helpers import postprocess_v6

    def t_module_to_footprint():
        v5 = '(module "TestComp"\n  (layer "F.Cu")\n  (pad 1 thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8))\n)'
        v6 = postprocess_v6(v5, attr='through_hole')
        assert '(footprint' in v6, f"Deveria conter '(footprint)': {v6[:100]}"
        assert '(module' not in v6, "Não deveria conter '(module)'"
        assert '20231120' in v6, "Deveria conter versão"
        assert 'through_hole' in v6, "Deveria conter attr"
    teste("Conversão (module) → (footprint)", t_module_to_footprint)

    def t_smd_attr():
        v5 = '(module "ChipR"\n  (pad 1 smd rect (at 0 0) (size 1 1))\n)'
        v6 = postprocess_v6(v5, attr='smd')
        assert 'smd' in v6
    teste("Attr SMD no pós-processamento", t_smd_attr)


# =============================================================================
# GRUPO 7: Helpers de Footprint
# =============================================================================
def test_grupo7():
    header("GRUPO 7: Helpers de Footprint")

    from footprint_helpers import validate_annular_ring, validate_pad_clearance

    def t_ring_ok():
        assert validate_annular_ring(1.6, 0.8) == True, "1.6/0.8 deveria passar (ring=0.4)"
    teste("Annular ring OK (1.6/0.8 = 0.4mm)", t_ring_ok)

    def t_ring_falha():
        assert validate_annular_ring(0.9, 0.8) == False, "0.9/0.8 deveria falhar (ring=0.05)"
    teste("Annular ring FALHA (0.9/0.8 = 0.05mm)", t_ring_falha)


# =============================================================================
# GRUPO 8: Presets YAML — Verificar Estrutura
# =============================================================================
def test_grupo8():
    header("GRUPO 8: Presets YAML — Verificar Estrutura")

    yamls_dir = os.path.join(PROJ, 'modulos_config')
    presets = [f for f in os.listdir(yamls_dir) if f.startswith('_preset_') and f.endswith('.yaml')]

    def t_contagem():
        assert len(presets) >= 20, f"Esperado >= 20 presets, encontrado {len(presets)}"
    teste(f"Total de presets: {len(presets)}", t_contagem)

    for preset in sorted(presets):
        def make_test(p):
            def t():
                path = os.path.join(yamls_dir, p)
                with open(path, 'r', encoding='utf-8') as f:
                    dados = yaml.safe_load(f)
                # Verificar campos obrigatórios
                assert 'nome' in dados, "'nome' faltando"
                assert 'tipo' in dados or 'padrao' in dados, "'tipo' ou 'padrao' faltando"
                assert 'kicad' in dados, "'kicad' faltando"
                assert 'margens' in dados, "'margens' faltando"
            return t
        teste(f"Preset: {preset}", make_test(preset))


# =============================================================================
# GRUPO 9: Consistência de Formato
# =============================================================================
def test_grupo9():
    header("GRUPO 9: Consistência de Formato nos Footprints Gerados")

    saida_dir = os.path.join(PROJ, 'saida', '_testes_v2')
    if not os.path.exists(saida_dir):
        print("  ⚠️  SKIP: Pasta de saída não existe (rode grupo 3 primeiro)")
        return

    for kicad_file in os.listdir(saida_dir):
        if not kicad_file.endswith('.kicad_mod'):
            continue

        def make_test(kf):
            def t():
                path = os.path.join(saida_dir, kf)
                content = open(path, 'r', encoding='utf-8').read()
                # Deve ter pelo menos 1 pad
                assert '(pad ' in content, "Nenhum pad encontrado"
                # Deve ter texto REF
                assert 'REF**' in content, "Texto REF** não encontrado"
                # Não deve estar vazio
                assert len(content) > 200, f"Arquivo muito pequeno ({len(content)} chars)"
            return t
        teste(f"Formato: {kicad_file}", make_test(kicad_file))


# =============================================================================
# GRUPO 10: Manual de Referência
# =============================================================================
def test_grupo10():
    header("GRUPO 10: Arquivos de Documentação")

    def t_manual():
        path = os.path.join(PROJ, 'docs', 'MANUAL_YAML_REFERENCIA.yaml')
        assert os.path.exists(path), "Manual não encontrado"
        content = open(path, 'r', encoding='utf-8').read()
        assert len(content) > 5000, f"Manual muito curto ({len(content)} chars)"
        assert 'axial_pth' in content, "'axial_pth' não documentado"
        assert 'custom' in content, "'custom' não documentado"
        assert 'PROMPT PARA IA' in content, "Seção de prompt para IA não encontrada"
    teste("Manual YAML existe e é completo", t_manual)

    def t_template():
        path = os.path.join(PROJ, 'modulos_config', '_template.yaml')
        assert os.path.exists(path), "Template não encontrado"
        with open(path, 'r', encoding='utf-8') as f:
            dados = yaml.safe_load(f)
        assert 'nome' in dados, "'nome' faltando no template"
    teste("Template YAML (_template.yaml)", t_template)


# =============================================================================
# GRUPO 11: Testes dos novos templates 3D
# =============================================================================
def test_grupo11():
    header("GRUPO 11: Testes dos novos templates 3D")

    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_3d')
    os.makedirs(saida_dir, exist_ok=True)
    yamls_dir = os.path.join(PROJ, 'modulos_config')

    presets_3d = [
        '_preset_SMD_0402.yaml',
        '_preset_SMD_0603.yaml',
        '_preset_SMD_0805.yaml',
        '_preset_SMD_1206.yaml',
        '_preset_SOD123.yaml',
        '_preset_SMA_DO214AC.yaml',
        '_preset_SOT23_3.yaml',
        '_preset_SOT23_5.yaml',
        '_preset_SOT223.yaml',
        '_preset_DPAK_TO252.yaml',
        '_preset_TO220.yaml',
        '_preset_TO247.yaml',
        '_preset_QFN16_4x4.yaml',
        '_preset_TQFP44.yaml',
        '_preset_SSOP20.yaml',
    ]

    for preset_file in presets_3d:
        yaml_path = os.path.join(yamls_dir, preset_file)
        if not os.path.exists(yaml_path):
            print(f"  ⚠️  SKIP: {preset_file} não encontrado")
            continue

        def make_test(yp, pf):
            def t():
                # 1. Load the YAML
                with open(yp, 'r', encoding='utf-8') as f:
                    dados = yaml.safe_load(f)

                # 2. Check it has tipo_3d field
                assert 'tipo_3d' in dados, f"Campo 'tipo_3d' não encontrado em {pf}"

                # 3. Generate footprint using the universal motor
                out = os.path.join(saida_dir, dados['nome'] + '_3d.kicad_mod')
                gerar_footprint_universal(dados, out)

                # 4. Verify .kicad_mod file was created and contains (footprint
                assert os.path.exists(out), f"Arquivo não criado: {out}"
                content = open(out, 'r', encoding='utf-8').read()
                assert '(footprint' in content or '(module' in content, \
                    f"Conteúdo inválido — '(footprint' não encontrado em {pf}"
            return t
        teste(f"3D preset: {preset_file}", make_test(yaml_path, preset_file))


# =============================================================================
# GRUPO 12: Edge cases
# =============================================================================
def test_grupo12():
    header("GRUPO 12: Edge cases — entradas incomuns")

    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_edge')
    os.makedirs(saida_dir, exist_ok=True)

    # ── 12.1: YAML com pinos.total = 1 ──────────────────────────────────
    def t_single_pin():
        dados = {
            'nome': 'EDGE_SinglePin',
            'padrao': 'radial_pth',
            'pinos': {'total': 1, 'pitch': 2.54, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'formato': 'cilindro', 'diametro': 3.0},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Single pin test', 'tags': 'edge test'}
        }
        path = os.path.join(saida_dir, 'EDGE_SinglePin.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path), "Arquivo não criado para single pin"
    teste("Edge: pinos.total=1 (gera sem crash)", t_single_pin)

    # ── 12.2: YAML com pin count muito alto (128) quad_smd ──────────────
    def t_high_pin_count():
        dados = {
            'nome': 'EDGE_QFP128',
            'padrao': 'quad_smd',
            'pinos': {
                'total': 128,
                'pitch': 0.5,
                'tamanho_pad': {'largura': 0.3, 'altura': 1.0},
                'por_lado': 32
            },
            'corpo': {'largura': 14.0, 'comprimento': 14.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'QFP-128 edge test', 'tags': 'qfp edge test'}
        }
        path = os.path.join(saida_dir, 'EDGE_QFP128.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path), "Arquivo não criado para QFP-128"
        content = open(path, 'r', encoding='utf-8').read()
        pad_count = content.count('(pad ')
        assert pad_count >= 128, f"Esperado >=128 pads, encontrado {pad_count}"
    teste("Edge: pinos.total=128 quad_smd (alta contagem)", t_high_pin_count)

    # ── 12.3: YAML com nome Unicode (Ω) ─────────────────────────────────
    def t_unicode_name():
        dados = {
            'nome': 'Resistor_10k\u03a9',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0, 'tamanho_pad': {'largura': 1.0, 'altura': 1.1}},
            'corpo': {'largura': 2.0, 'comprimento': 1.25, 'afastamento_colunas': 2.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Resistor com Unicode', 'tags': 'unicode edge test'}
        }
        path = os.path.join(saida_dir, 'EDGE_Unicode.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path), "Arquivo não criado para nome Unicode"
        content = open(path, 'r', encoding='utf-8').read()
        assert '\u03a9' in content or 'Ω' in content, "Caractere Unicode Ω não encontrado"
    teste("Edge: nome Unicode (Resistor_10kΩ)", t_unicode_name)

    # ── 12.4: YAML sem seção 'corpo' — deve levantar erro ou fallback ───
    def t_missing_corpo():
        dados = {
            'nome': 'EDGE_NoCorp',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0, 'tamanho_pad': {'largura': 1.0, 'altura': 1.1}},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Sem corpo', 'tags': 'edge test'}
        }
        path = os.path.join(saida_dir, 'EDGE_NoCorp.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            # Se não lançou exceção, o motor fez fallback — aceitar também
            assert os.path.exists(path), "Arquivo não criado no fallback"
        except (KeyError, ValueError, TypeError):
            pass  # Exceção esperada — corpo ausente detectado
    teste("Edge: YAML sem seção 'corpo' (erro ou fallback)", t_missing_corpo)

    # ── 12.5: YAML com campos extras desconhecidos — deve ignorar ───────
    def t_extra_fields():
        dados = {
            'nome': 'EDGE_ExtraFields',
            'padrao': 'axial_pth',
            'pinos': {'espacamento': 10.16, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'formato': 'cilindro', 'diametro': 2.5, 'comprimento': 6.5},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Extra fields test', 'tags': 'edge test'},
            'campo_fantasma': 'valor_qualquer',
            'metadados_bizarros': {'sub': [1, 2, 3]},
            'nota_inutil': 42,
        }
        path = os.path.join(saida_dir, 'EDGE_ExtraFields.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path), "Arquivo não criado com campos extras"
    teste("Edge: campos extras desconhecidos (sem crash)", t_extra_fields)

    # ── 12.6: YAML vazio (só nome) — deve levantar erro claro ───────────
    def t_empty_yaml():
        dados = {'nome': 'test'}
        path = os.path.join(saida_dir, 'EDGE_Empty.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            # Se chegou aqui sem erro, é um problema
            assert False, "Deveria ter lançado exceção para YAML vazio (sem padrao)"
        except (ValueError, KeyError, TypeError) as e:
            # Deve ter uma mensagem de erro clara
            assert len(str(e)) > 0, "Exceção sem mensagem"
    teste("Edge: YAML vazio (só nome) — erro claro", t_empty_yaml)


# =============================================================================
# GRUPO 13: Gerador de BOM
# =============================================================================
def test_grupo13():
    header("GRUPO 13: Gerador de BOM")

    # 13.1: Import gerar_bom
    def t_import_bom():
        from gerador_bom import gerar_bom
    teste("Import gerador_bom", t_import_bom)

    # 13.2: Generate BOM from modulos_config/ → CSV
    from gerador_bom import gerar_bom
    saida_bom = os.path.join(PROJ, 'saida', '_testes_bom')
    os.makedirs(saida_bom, exist_ok=True)
    bom_csv = os.path.join(saida_bom, 'bom_teste.csv')

    def t_gerar_bom():
        resultado = gerar_bom(os.path.join(PROJ, 'modulos_config'), bom_csv)
        assert os.path.exists(bom_csv), "Arquivo BOM não criado"
        assert resultado['total'] > 0, f"Nenhum componente no BOM: {resultado}"
    teste("Gerar BOM CSV a partir de modulos_config/", t_gerar_bom)

    # 13.3: Verify CSV has correct columns
    def t_bom_colunas():
        import csv as csv_mod
        with open(bom_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv_mod.reader(f, delimiter=';')
            header_row = next(reader)
        colunas_esperadas = ['Item', 'Referencia', 'Valor', 'Footprint', 'Descricao', 'Pinos', 'Tags']
        for col in colunas_esperadas:
            assert col in header_row, f"Coluna '{col}' não encontrada no BOM. Encontradas: {header_row}"
    teste("BOM CSV contém colunas corretas", t_bom_colunas)

    # 13.4: Verify component count matches non-preset YAML count
    def t_bom_contagem():
        yamls_dir = os.path.join(PROJ, 'modulos_config')
        yaml_count = 0
        for f_name in os.listdir(yamls_dir):
            if not f_name.lower().endswith(('.yaml', '.yml')):
                continue
            if f_name.startswith('_preset_') or f_name.startswith('_template'):
                continue
            yaml_count += 1
        import csv as csv_mod
        with open(bom_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv_mod.reader(f, delimiter=';')
            next(reader)  # skip header
            bom_count = sum(1 for _ in reader)
        assert bom_count == yaml_count, \
            f"BOM tem {bom_count} itens, mas há {yaml_count} YAMLs (excluindo presets/templates)"
    teste("Contagem BOM = YAMLs não-preset", t_bom_contagem)


# =============================================================================
# GRUPO 14: Verificador DRC
# =============================================================================
def test_grupo14():
    header("GRUPO 14: Verificador DRC")

    # 14.1: Import verificar_drc, DRCResult
    def t_import_drc():
        from verificador_drc import verificar_drc, DRCResult
        r = DRCResult()
        assert r.ok == True, "DRCResult vazio deveria ser ok"
    teste("Import verificador_drc + DRCResult", t_import_drc)

    from verificador_drc import verificar_drc, DRCResult

    # 14.2: Valid component passes DRC
    def t_drc_valido():
        dados = {
            'nome': 'DRC_OK_Resistor',
            'padrao': 'axial_pth',
            'pinos': {'espacamento': 10.16, 'diametro_pad': 1.6, 'diametro_furo': 0.8},
            'corpo': {'formato': 'cilindro', 'diametro': 2.5, 'comprimento': 6.5,
                      'largura': 6.5},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'R?', 'descricao': 'Resistor', 'tags': 'resistor'}
        }
        r = verificar_drc(dados)
        assert r.ok, f"Componente válido falhou no DRC: {r}"
    teste("Componente válido passa no DRC", t_drc_valido)

    # 14.3: Component with tiny pad (<0.15mm) triggers min_trace_width error
    def t_drc_pad_pequeno():
        dados = {
            'nome': 'DRC_TinyPad',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0,
                      'tamanho_pad': {'largura': 0.10, 'altura': 0.10}},
            'corpo': {'largura': 2.0, 'comprimento': 1.25, 'afastamento_colunas': 2.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Tiny pad test', 'tags': 'drc test'}
        }
        r = verificar_drc(dados)
        has_error = any('largura' in e.lower() or 'trace' in e.lower() or 'mínimo' in e.lower()
                        for e in r.errors)
        assert has_error, f"Deveria detectar pad muito pequeno (<0.15mm): {r}"
    teste("DRC detecta pad < 0.15mm (min_trace_width)", t_drc_pad_pequeno)

    # 14.4: Component with huge thermal pad (>25mm²) triggers thermal_relief warning
    def t_drc_thermal():
        dados = {
            'nome': 'DRC_BigThermal',
            'padrao': 'dual_smd',
            'pinos': {'total': 4, 'pitch': 1.27,
                      'tamanho_pad': {'largura': 0.6, 'altura': 1.5}},
            'thermal_pad': {'largura': 6.0, 'altura': 6.0},
            'corpo': {'largura': 5.0, 'comprimento': 5.0, 'afastamento_colunas': 5.4},
            'margens': {'courtyard': 0.50, 'silkscreen': 0.50, 'fab_line': 0.10},
            'kicad': {'descricao': 'Big thermal', 'tags': 'drc test'}
        }
        r = verificar_drc(dados)
        has_thermal = any('thermal' in w.lower() or 'relief' in w.lower()
                          for w in r.warnings)
        if not has_thermal:
            has_thermal = any('thermal' in e.lower() or 'relief' in e.lower()
                              for e in r.errors)
        assert has_thermal, f"Deveria avisar sobre thermal pad > 25mm²: {r}"
    teste("DRC detecta thermal pad > 25mm² (thermal_relief)", t_drc_thermal)

    # 14.5: Component with extreme pad ratio (>5:1) triggers aspect_ratio warning
    def t_drc_aspect_ratio():
        dados = {
            'nome': 'DRC_LongPad',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0,
                      'tamanho_pad': {'largura': 0.3, 'altura': 2.0}},
            'corpo': {'largura': 2.0, 'comprimento': 1.25, 'afastamento_colunas': 2.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'Long pad test', 'tags': 'drc test'}
        }
        r = verificar_drc(dados)
        has_ratio = any('aspect' in w.lower() or 'ratio' in w.lower() or 'proporção' in w.lower()
                        for w in r.warnings)
        assert has_ratio, f"Deveria avisar sobre aspect ratio > 5:1: {r}"
    teste("DRC detecta aspect ratio > 5:1 (pad_aspect_ratio)", t_drc_aspect_ratio)

    # 14.6: DRC with all rules disabled returns OK
    def t_drc_desabilitado():
        dados = {
            'nome': 'DRC_Disabled',
            'padrao': 'dual_smd',
            'pinos': {'total': 2, 'pitch': 0,
                      'tamanho_pad': {'largura': 0.05, 'altura': 0.05}},
            'kicad': {'descricao': 'Rules off', 'tags': 'drc test'}
        }
        rules_off = {
            'min_trace_width': False,
            'copper_to_edge': False,
            'solder_mask_expansion': False,
            'pad_silk_clearance': False,
            'min_drill_to_drill': False,
            'thermal_relief': False,
            'pad_aspect_ratio': False,
            'symmetry_check': False,
        }
        r = verificar_drc(dados, rules=rules_off)
        assert r.ok, f"Com todas as regras desabilitadas, DRC deveria ser OK: {r}"
    teste("DRC com todas as regras desabilitadas retorna OK", t_drc_desabilitado)


# =============================================================================
# GRUPO 15: Exportação multi-formato (Eagle, Altium, Relatório)
# =============================================================================
def test_grupo15():
    header("GRUPO 15: Exportação multi-formato")

    saida_dir = os.path.join(PROJ, 'saida', '_testes_export')
    os.makedirs(saida_dir, exist_ok=True)

    # Encontrar um .kicad_mod existente na saida/ para testes de conversão
    kicad_mod_source = None
    search_dirs = [
        os.path.join(PROJ, 'saida', '_testes_v2'),
        os.path.join(PROJ, 'saida', '_testes_v1'),
        os.path.join(PROJ, 'saida'),
    ]
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            for f_name in os.listdir(sdir):
                if f_name.endswith('.kicad_mod'):
                    kicad_mod_source = os.path.join(sdir, f_name)
                    break
        if kicad_mod_source:
            break

    # 15.1: Import exportar_eagle, exportar_altium
    def t_import_export():
        from exportar_eagle import kicad_to_eagle
        from exportar_altium import kicad_to_altium_csv
    teste("Import exportar_eagle + exportar_altium", t_import_export)

    from exportar_eagle import kicad_to_eagle
    from exportar_altium import kicad_to_altium_csv

    # 15.2: Convert .kicad_mod to Eagle .lbr → verify XML has <eagle> root
    def t_eagle_export():
        assert kicad_mod_source, "Nenhum .kicad_mod encontrado em saida/ (rode grupo 3 ou 4 primeiro)"
        lbr_path = os.path.join(saida_dir, 'teste_export.lbr')
        kicad_to_eagle(kicad_mod_source, lbr_path)
        assert os.path.exists(lbr_path), "Arquivo .lbr não criado"
        content = open(lbr_path, 'r', encoding='utf-8').read()
        assert '<eagle' in content, f"Arquivo .lbr não contém tag <eagle>: {content[:200]}"
    teste("Export Eagle .lbr (XML com <eagle>)", t_eagle_export)

    # 15.3: Convert .kicad_mod to Altium CSV → verify CSV has headers
    def t_altium_export():
        assert kicad_mod_source, "Nenhum .kicad_mod encontrado em saida/ (rode grupo 3 ou 4 primeiro)"
        csv_path = os.path.join(saida_dir, 'teste_export_altium.csv')
        kicad_to_altium_csv(kicad_mod_source, csv_path)
        assert os.path.exists(csv_path), "Arquivo CSV Altium não criado"
        content = open(csv_path, 'r', encoding='utf-8').read()
        assert 'Type' in content and 'Name' in content, \
            f"CSV Altium não contém headers esperados: {content[:300]}"
    teste("Export Altium CSV (com headers Type/Name)", t_altium_export)

    # 15.4: Import gerador_relatorio
    def t_import_relatorio():
        from gerador_relatorio import gerar_relatorio
    teste("Import gerador_relatorio", t_import_relatorio)

    from gerador_relatorio import gerar_relatorio

    # 15.5: Generate PDF report from 1 YAML → verify .pdf exists and size > 0
    def t_relatorio_pdf():
        yamls_dir = os.path.join(PROJ, 'modulos_config')
        # Pick the first non-preset YAML
        yaml_path = None
        for f_name in sorted(os.listdir(yamls_dir)):
            if f_name.endswith('.yaml') and not f_name.startswith('_'):
                yaml_path = os.path.join(yamls_dir, f_name)
                break
        assert yaml_path, "Nenhum YAML encontrado em modulos_config/"
        pdf_path = os.path.join(saida_dir, 'relatorio_teste.pdf')
        gerar_relatorio([yaml_path], pdf_path, opcoes={'formato': 'pdf'})
        assert os.path.exists(pdf_path), "Arquivo PDF não criado"
        assert os.path.getsize(pdf_path) > 0, "Arquivo PDF está vazio"
    teste("Relatório PDF (existe e tamanho > 0)", t_relatorio_pdf)

    # 15.6: Generate HTML report → verify .html exists and contains <html>
    def t_relatorio_html():
        yamls_dir = os.path.join(PROJ, 'modulos_config')
        yaml_path = None
        for f_name in sorted(os.listdir(yamls_dir)):
            if f_name.endswith('.yaml') and not f_name.startswith('_'):
                yaml_path = os.path.join(yamls_dir, f_name)
                break
        assert yaml_path, "Nenhum YAML encontrado em modulos_config/"
        # Pass path WITHOUT .html extension — gerador appends it
        out_base = os.path.join(saida_dir, 'relatorio_teste_html')
        gerar_relatorio([yaml_path], out_base, opcoes={'formato': 'html'})
        html_path = out_base + '.html'
        assert os.path.exists(html_path), f"Arquivo HTML não criado: {html_path}"
        content = open(html_path, 'r', encoding='utf-8').read()
        assert '<html' in content.lower(), f"Arquivo HTML não contém <html>: {content[:200]}"
    teste("Relatório HTML (existe e contém <html>)", t_relatorio_html)


# =============================================================================
# GRUPO 16: sexpr_parser
# =============================================================================
def test_grupo16():
    header("GRUPO 16: Parser S-Expression")

    from sexpr_parser import parse_sexpr, find_all, find_one

    def t_parse_simples():
        result = parse_sexpr('(footprint "TEST" (pad 1 smd))')
        assert result[0] == 'footprint'
        assert result[1] == 'TEST'
    teste("Parse S-Expression simples", t_parse_simples)

    def t_parse_aninhado():
        result = parse_sexpr('(a (b 1) (c (d 2)))')
        assert result[0] == 'a'
        assert len(result) == 3  # a, (b 1), (c (d 2))
    teste("Parse S-Expression aninhado", t_parse_aninhado)

    def t_find_all_pads():
        tree = parse_sexpr('(footprint "X" (pad 1 smd) (pad 2 smd) (pad 3 thru))')
        pads = find_all(tree, 'pad')
        assert len(pads) == 3, f"Esperado 3 pads, encontrado {len(pads)}"
    teste("find_all encontra todos os pads", t_find_all_pads)

    def t_find_one():
        tree = parse_sexpr('(footprint "X" (attr smd) (pad 1))')
        attr = find_one(tree, 'attr')
        assert attr is not None
        assert 'smd' in attr
    teste("find_one encontra primeiro match", t_find_one)

    def t_find_one_none():
        tree = parse_sexpr('(footprint "X" (pad 1))')
        result = find_one(tree, 'inexistente')
        assert result is None, "find_one deveria retornar None para tag inexistente"
    teste("find_one retorna None para tag ausente", t_find_one_none)

    def t_parse_kicad_mod_real():
        """Testa parse de um .kicad_mod real gerado."""
        saida_dir = os.path.join(PROJ, 'saida', '_testes_v2')
        mod_files = [f for f in os.listdir(saida_dir) if f.endswith('.kicad_mod')]
        assert len(mod_files) > 0, "Nenhum .kicad_mod em _testes_v2"
        mod_path = os.path.join(saida_dir, mod_files[0])
        with open(mod_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = parse_sexpr(content)
        assert tree[0] == 'footprint' or tree[0] == 'module'
        pads = find_all(tree, 'pad')
        assert len(pads) > 0, "Nenhum pad encontrado no parse do .kicad_mod"
    teste("Parse de .kicad_mod real", t_parse_kicad_mod_real)


# =============================================================================
# GRUPO 17: BGA + Padrão extra
# =============================================================================
def test_grupo17():
    header("GRUPO 17: BGA pattern")

    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_bga')
    os.makedirs(saida_dir, exist_ok=True)

    def t_bga():
        dados = {
            'nome': 'TESTE_BGA64',
            'padrao': 'bga',
            'pinos': {
                'linhas': 8, 'colunas': 8, 'pitch': 0.8,
                'tamanho_pad': {'largura': 0.4, 'altura': 0.4},
                'diametro_pad': 0.4,
            },
            'corpo': {'largura': 8.0, 'comprimento': 8.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'modelo_3d': 'BGA64.step', 'descricao': 'BGA-64', 'tags': 'bga smd'}
        }
        path = os.path.join(saida_dir, 'TESTE_BGA64.kicad_mod')
        gerar_footprint_universal(dados, path)
        assert os.path.exists(path)
        content = open(path, 'r', encoding='utf-8').read()
        pad_count = content.count('(pad ')
        assert pad_count >= 60, f"BGA 8x8 deveria ter ~64 pads, encontrado {pad_count}"
        assert '(attr smd)' in content
    teste("BGA 8x8 (64 pads)", t_bga)


# =============================================================================
# GRUPO 18: Validação de Conteúdo KiCad (regressão dos bugs corrigidos)
# =============================================================================
def test_grupo18():
    header("GRUPO 18: Validação de Conteúdo KiCad")

    from gerador_footprint_v2 import gerar_footprint_universal
    from gerador_symbol import gerar_symbol
    saida_dir = os.path.join(PROJ, 'saida', '_testes_conteudo')
    os.makedirs(saida_dir, exist_ok=True)

    # Gerar componente de teste
    dados = {
        'nome': 'TESTE_Conteudo_SOIC8',
        'padrao': 'dual_smd',
        'tipo': 'ci_soic',
        'pinos': {'total': 8, 'pitch': 1.27, 'tamanho_pad': {'largura': 0.6, 'altura': 1.5}},
        'corpo': {'largura': 3.9, 'comprimento': 4.9, 'afastamento_colunas': 5.4},
        'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
        'kicad': {'modelo_3d': 'SOIC8.step', 'descricao': 'SOIC-8 Teste', 'tags': 'soic teste',
                  'referencia': 'U?', 'valor': 'TESTE'}
    }

    mod_path = os.path.join(saida_dir, 'TESTE_Conteudo_SOIC8.kicad_mod')
    sym_path = os.path.join(saida_dir, 'TESTE_Conteudo_SOIC8.kicad_sym')
    gerar_footprint_universal(dados, mod_path)
    gerar_symbol(dados, sym_path)

    # ── Testes no .kicad_mod ──────────────────────────────────────────────
    mod_content = open(mod_path, 'r', encoding='utf-8').read()

    def t_mod_path_3d():
        # Bug corrigido: path 3D não deve conter 'saida/'
        assert 'saida/' not in mod_content or '${KIPRJMOD}/saida/' not in mod_content, \
            "Path 3D contém 'saida/' hardcoded"
        assert '(model' in mod_content, "Nenhum model 3D encontrado"
    teste("kicad_mod: path 3D sem 'saida/' hardcoded", t_mod_path_3d)

    def t_mod_pads():
        assert mod_content.count('(pad ') >= 8, "SOIC-8 deveria ter >= 8 pads"
    teste("kicad_mod: contagem de pads correta", t_mod_pads)

    def t_mod_footprint_tag():
        assert '(footprint' in mod_content, "Tag (footprint) ausente"
    teste("kicad_mod: tag (footprint) presente", t_mod_footprint_tag)

    def t_mod_encoding():
        # Verificar que o arquivo é UTF-8 válido (strict)
        with open(mod_path, 'r', encoding='utf-8', errors='strict') as f:
            f.read()
    teste("kicad_mod: encoding UTF-8 válido", t_mod_encoding)

    # ── Testes no .kicad_sym ──────────────────────────────────────────────
    sym_content = open(sym_path, 'r', encoding='utf-8').read()

    def t_sym_footprint():
        # Bug corrigido: Footprint não deve ser vazio
        assert '"Footprint" ""' not in sym_content, \
            "Campo Footprint vazio no .kicad_sym"
        assert '"Footprint"' in sym_content, "Campo Footprint ausente"
    teste("kicad_sym: campo Footprint preenchido", t_sym_footprint)

    def t_sym_parentheses():
        # Bug corrigido: parênteses devem ser balanceados
        n_open = sym_content.count('(')
        n_close = sym_content.count(')')
        assert n_open == n_close, \
            f"Parênteses desbalanceados: {n_open}( vs {n_close})"
    teste("kicad_sym: parênteses balanceados", t_sym_parentheses)

    def t_sym_no_double_size():
        # Bug corrigido: não deve ter ((size
        assert '((size' not in sym_content, \
            "Parênteses duplos ((size detectados"
    teste("kicad_sym: sem ((size)) duplos", t_sym_no_double_size)

    def t_sym_encoding():
        with open(sym_path, 'r', encoding='utf-8', errors='strict') as f:
            f.read()
    teste("kicad_sym: encoding UTF-8 válido", t_sym_encoding)


# =============================================================================
# GRUPO 19: Shim tipo→padrao — Casos especiais
# =============================================================================
def test_grupo19():
    header("GRUPO 19: Shim tipo→padrao — Edge Cases")

    from gerador_footprint_v2 import gerar_footprint_universal, _TIPO_PARA_PADRAO
    saida_dir = os.path.join(PROJ, 'saida', '_testes_shim_edge')
    os.makedirs(saida_dir, exist_ok=True)

    def t_mapeamento_completo():
        """Verifica que todos os 10 tipos têm mapeamento."""
        esperados = [
            'resistor_pth', 'diodo_pth', 'led_pth', 'capacitor_pth',
            'crystal_hc49', 'transistor_to92', 'ci_dip', 'ci_soic',
            'conector_pth', 'castellated'
        ]
        for tipo in esperados:
            assert tipo in _TIPO_PARA_PADRAO, \
                f"Tipo '{tipo}' não mapeado em _TIPO_PARA_PADRAO"
    teste("Mapeamento completo (10 tipos)", t_mapeamento_completo)

    def t_padrao_prevalece():
        """Se YAML tem ambos tipo: e padrao:, padrao: prevalece."""
        dados = {
            'nome': 'TESTE_Prevalencia',
            'tipo': 'ci_dip',  # → dual_pth via shim
            'padrao': 'dual_smd',  # prevalece
            'pinos': {'total': 4, 'pitch': 1.27,
                      'tamanho_pad': {'largura': 0.6, 'altura': 1.0}},
            'corpo': {'largura': 3.0, 'comprimento': 3.0, 'afastamento_colunas': 4.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'teste', 'tags': 'teste'}
        }
        path = os.path.join(saida_dir, 'TESTE_prevalencia.kicad_mod')
        gerar_footprint_universal(dados, path)
        content = open(path, 'r', encoding='utf-8').read()
        # dual_smd gera attr smd, dual_pth geraria through_hole
        assert '(attr smd)' in content, \
            "padrao: deveria prevalecer sobre tipo:"
    teste("padrao: prevalece sobre tipo:", t_padrao_prevalece)

    def t_tipo_desconhecido():
        """tipo: com valor desconhecido deve falhar."""
        dados = {
            'nome': 'TESTE_TipoInvalido',
            'tipo': 'componente_alienígena',
            'pinos': {'total': 2},
            'corpo': {'largura': 1.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
        }
        path = os.path.join(saida_dir, 'TESTE_tipo_invalido.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            assert False, "Deveria ter falhado com ValueError"
        except (ValueError, KeyError):
            pass  # Esperado
    teste("tipo: desconhecido → erro", t_tipo_desconhecido)

    def t_sem_tipo_nem_padrao():
        """YAML sem tipo: nem padrao: deve falhar."""
        dados = {
            'nome': 'TESTE_SemTipoNemPadrao',
            'pinos': {'total': 2},
            'corpo': {'largura': 1.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
        }
        path = os.path.join(saida_dir, 'TESTE_sem_tipo.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            assert False, "Deveria ter falhado"
        except (ValueError, KeyError, TypeError):
            pass  # Esperado
    teste("Sem tipo: nem padrao: → erro", t_sem_tipo_nem_padrao)


# =============================================================================
# GRUPO 20: pinos.overrides — as duas formas do schema (dict e lista)
# =============================================================================
def test_grupo20():
    header("GRUPO 20: pinos.overrides — formas dict e lista")

    from footprint_helpers import build_override_map
    from gerador_footprint_v2 import gerar_footprint_universal
    saida_dir = os.path.join(PROJ, 'saida', '_testes_overrides')
    os.makedirs(saida_dir, exist_ok=True)

    W, H = 1.0, 0.5  # defaults do padrão

    def t_forma_dict():
        """Forma dict: {"1": {largura, altura}} → mapeada por pino."""
        dados = {'pinos': {'overrides': {'1': {'largura': 2.5, 'altura': 1.2}}}}
        m = build_override_map(dados, W, H)
        assert m == {'1': (2.5, 1.2)}, f"Esperado {{'1': (2.5, 1.2)}}, obtido {m}"
    teste("overrides forma dict", t_forma_dict)

    def t_forma_lista():
        """Forma lista: [{numeros: [...], largura, altura}] → expande o grupo."""
        dados = {'pinos': {'overrides': [
            {'numeros': [1, 9, 16], 'largura': 2.5, 'altura': 1.2},
            {'numeros': [25], 'largura': 3.0, 'altura': 1.4},
        ]}}
        m = build_override_map(dados, W, H)
        assert m == {'1': (2.5, 1.2), '9': (2.5, 1.2), '16': (2.5, 1.2),
                     '25': (3.0, 1.4)}, f"Grupo não expandido corretamente: {m}"
    teste("overrides forma lista (grupo de pinos)", t_forma_lista)

    def t_chave_textual_bga():
        """Chave é string: o BGA endereça bolas por nome ("A1"), não por índice."""
        dados = {'pinos': {'overrides': {'A1': {'largura': 0.4, 'altura': 0.4}}}}
        m = build_override_map(dados, W, H)
        assert m == {'A1': (0.4, 0.4)}, f"Chave textual perdida: {m}"
    teste("overrides com chave textual (BGA 'A1')", t_chave_textual_bga)

    def t_campo_ausente_usa_default():
        """largura/altura ausentes caem no default do padrão."""
        dados = {'pinos': {'overrides': [{'numeros': [3], 'largura': 2.0}]}}
        m = build_override_map(dados, W, H)
        assert m == {'3': (2.0, H)}, f"Default de altura não aplicado: {m}"
    teste("overrides: campo ausente usa default", t_campo_ausente_usa_default)

    def t_ausente_ou_vazio():
        """Sem overrides (ou vazio/None) → mapa vazio, sem erro."""
        for dados in ({}, {'pinos': {}}, {'pinos': None},
                      {'pinos': {'overrides': None}}, {'pinos': {'overrides': []}}):
            m = build_override_map(dados, W, H)
            assert m == {}, f"Esperado mapa vazio para {dados}, obtido {m}"
    teste("overrides ausente/vazio → mapa vazio", t_ausente_ou_vazio)

    def t_malformado_nao_derruba():
        """Entradas malformadas são ignoradas em vez de estourar."""
        dados = {'pinos': {'overrides': ['lixo', {'sem_numeros': 1},
                                         {'numeros': ['x'], 'largura': 2.0}]}}
        m = build_override_map(dados, W, H)
        assert m == {}, f"Malformado deveria ser ignorado, obtido {m}"
    teste("overrides malformado não derruba a geração", t_malformado_nao_derruba)

    def t_quad_smd_lista_gera():
        """Regressão: quad_smd com overrides em lista costumava estourar
        AttributeError ('list' object has no attribute 'get')."""
        dados = {
            'nome': 'TESTE_Override_Lista',
            'padrao': 'quad_smd',
            'pinos': {
                'total': 8, 'pitch': 1.0,
                'tamanho_pad': {'largura': 1.0, 'altura': 0.5},
                'overrides': [{'numeros': [1, 5], 'largura': 2.5, 'altura': 1.2}],
            },
            'corpo': {'largura': 6.0, 'comprimento': 6.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'descricao': 'teste', 'tags': 'teste'},
        }
        path = os.path.join(saida_dir, 'TESTE_override_lista.kicad_mod')
        gerar_footprint_universal(dados, path)
        content = open(path, 'r', encoding='utf-8').read()
        # 2 pads devem ter o tamanho do override (em alguma das orientações)
        n = content.count('(size 2.5 1.2)') + content.count('(size 1.2 2.5)')
        assert n == 2, f"Esperado 2 pads com override, encontrado {n}"
    teste("quad_smd com overrides em lista gera (regressão)", t_quad_smd_lista_gera)

    def t_overrides_honrado_em_todos_os_padroes():
        """`pinos.overrides` deve ser honrado por todo padrão que o aceita.

        Antes, só o quad_smd o lia — os demais ignoravam em SILÊNCIO: o YAML
        era aceito, o footprint gerava, e o pad saía no tamanho padrão.
        `custom` e `bga` ficam de fora aqui: o custom declara largura/altura
        por pad na própria lista `pads:`, e o bga endereça bolas por nome
        (coberto em t_chave_textual_bga / t_bga_override).
        """
        casos = {
            'axial_pth': ({'padrao': 'axial_pth',
                           'pinos': {'espacamento': 10.16, 'diametro_pad': 1.6,
                                     'diametro_furo': 0.8},
                           'corpo': {'formato': 'cilindro', 'diametro': 2.5,
                                     'comprimento': 6.5}}, '1'),
            'radial_pth': ({'padrao': 'radial_pth',
                            'pinos': {'total': 3, 'espacamento': 2.54,
                                      'diametro_pad': 1.6, 'diametro_furo': 0.8},
                            'corpo': {'diametro': 4.8}}, '1'),
            'dual_pth': ({'padrao': 'dual_pth',
                          'pinos': {'total': 8, 'pitch': 2.54, 'diametro_pad': 1.6,
                                    'diametro_furo': 0.8},
                          'corpo': {'largura': 6.35, 'comprimento': 9.78,
                                    'afastamento_colunas': 7.62}}, '1'),
            'dual_smd': ({'padrao': 'dual_smd',
                          'pinos': {'total': 8, 'pitch': 1.27,
                                    'tamanho_pad': {'largura': 0.6, 'altura': 1.5},
                                    'afastamento_colunas': 5.4},
                          'corpo': {'largura': 3.9, 'comprimento': 4.9}}, '1'),
        }
        OV_W, OV_H = 2.7, 1.9   # tamanho improvável de coincidir com o default
        for padrao, (extra, pino) in casos.items():
            dados = {
                'nome': f'TESTE_OV_{padrao}',
                'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
                'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
                **extra,
            }
            dados['pinos']['overrides'] = {pino: {'largura': OV_W, 'altura': OV_H}}
            path = os.path.join(saida_dir, f'TESTE_ov_{padrao}.kicad_mod')
            gerar_footprint_universal(dados, path)
            content = open(path, 'r', encoding='utf-8').read()
            achou = (f'(size {OV_W} {OV_H})' in content
                     or f'(size {OV_H} {OV_W})' in content)
            assert achou, \
                f"padrão '{padrao}' ignorou pinos.overrides (pad saiu no tamanho padrão)"
    teste("overrides honrado em axial/radial/dual PTH e dual_smd",
          t_overrides_honrado_em_todos_os_padroes)

    def t_bga_override():
        """BGA: override endereçado pelo nome da bola ("A1")."""
        dados = {
            'nome': 'TESTE_OV_bga', 'padrao': 'bga',
            'pinos': {'linhas': 4, 'colunas': 4, 'pitch': 1.0,
                      'diametro_pad': 0.5,
                      'overrides': {'A1': {'largura': 0.8, 'altura': 0.8}}},
            'corpo': {'largura': 5.0, 'comprimento': 5.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_ov_bga.kicad_mod')
        gerar_footprint_universal(dados, path)
        content = open(path, 'r', encoding='utf-8').read()
        assert '(size 0.8 0.8)' in content, "bga ignorou o override da bola A1"
    teste("bga honra override por nome da bola", t_bga_override)

    def t_pasta_ratio_sinonimo():
        """`pasta_ratio` é sinônimo de `paste_ratio` (o schema promete isso).

        Ler só uma grafia fazia a outra ser descartada em silêncio — e o
        _template.yaml ensina justamente `pasta_ratio`.
        """
        from footprint_helpers import read_paste_ratio
        assert read_paste_ratio({'paste_ratio': 0.9}) == 0.9
        assert read_paste_ratio({'pasta_ratio': 0.9}) == 0.9, \
            "pasta_ratio (sinônimo declarado no schema) foi ignorado"
        assert read_paste_ratio({}) == 0.5, "default deveria ser 0.5"
        # paste_ratio tem precedência quando ambas aparecem
        assert read_paste_ratio({'paste_ratio': 0.3, 'pasta_ratio': 0.9}) == 0.3
        assert read_paste_ratio({'pasta_ratio': 'lixo'}) == 0.5, \
            "valor inválido deveria cair no default, não estourar"
    teste("thermal_pad: pasta_ratio == paste_ratio (sinônimo)",
          t_pasta_ratio_sinonimo)

    def t_total_contradiz_lados():
        """`pinos.total` divergente da distribuição por lado deve dar ERRO.

        Antes era descartado em silêncio: o Stx3 declarava total: 32 com
        por_lado: 16 e gerava 64 pads sem aviso.
        """
        base = {
            'nome': 'TESTE_Contradicao', 'padrao': 'quad_smd',
            'pinos': {'pitch': 1.0, 'tamanho_pad': {'largura': 0.5, 'altura': 0.3}},
            'corpo': {'largura': 8.0, 'comprimento': 8.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_contradicao.kicad_mod')

        # total contradiz por_lado (o caso real do Stx3: 32 vs 16x4=64)
        d = copy.deepcopy(base)
        d['pinos'].update({'total': 32, 'por_lado': 16})
        try:
            gerar_footprint_universal(d, path)
            assert False, "total=32 com por_lado=16 (=64) deveria dar erro"
        except ValueError:
            pass

        # total não divisível por 4: 30//4=7 → 28 pads, sumiam 2 em silêncio
        d = copy.deepcopy(base)
        d['pinos']['total'] = 30
        try:
            gerar_footprint_universal(d, path)
            assert False, "total=30 (não divisível por 4) deveria dar erro"
        except ValueError:
            pass

        # coerente: não pode dar erro
        d = copy.deepcopy(base)
        d['pinos'].update({'total': 64, 'por_lado': 16})
        gerar_footprint_universal(d, path)
    teste("pinos.total contraditório → erro (não gera calado)",
          t_total_contradiz_lados)

    def t_numeracao_inicio_por_lado():
        """`pinos.numeracao` fixa onde a numeração de cada lado começa."""
        dados = {
            'nome': 'TESTE_Numeracao', 'padrao': 'quad_smd',
            'pinos': {'lados': {'esquerdo': 4, 'base': 0, 'direito': 4, 'topo': 0},
                      'pitch': 1.0,
                      'tamanho_pad': {'largura': 0.5, 'altura': 0.3},
                      'numeracao': {'inicio_esquerdo': 1, 'inicio_direito': 17}},
            'corpo': {'largura': 8.0, 'comprimento': 8.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_numeracao.kicad_mod')
        gerar_footprint_universal(dados, path)
        content = open(path, 'r', encoding='utf-8').read()
        nums = set(re.findall(r'\(pad "?(\d+)"?\s', content))
        assert {'1', '2', '3', '4'} <= nums, f"esquerdo deveria ser 1..4: {sorted(nums)}"
        assert {'17', '18', '19', '20'} <= nums, \
            f"direito deveria começar em 17: {sorted(nums)}"
    teste("pinos.numeracao define início por lado", t_numeracao_inicio_por_lado)

    def t_numeracao_colisao_erro():
        """Início que colide com outro lado → erro (pad duplicado = netlist errada).

        Caso real: o Stx3 pedia inicio_direito=17 num módulo de 4 lados, onde a
        base já ocupa 17-32.
        """
        dados = {
            'nome': 'TESTE_Colisao', 'padrao': 'quad_smd',
            'pinos': {'por_lado': 16, 'pitch': 1.0,
                      'tamanho_pad': {'largura': 0.5, 'altura': 0.3},
                      'numeracao': {'inicio_esquerdo': 1, 'inicio_direito': 17}},
            'corpo': {'largura': 20.0, 'comprimento': 20.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_colisao.kicad_mod')
        try:
            gerar_footprint_universal(dados, path)
            assert False, "numeração colidindo deveria dar erro"
        except ValueError as e:
            assert 'duplicad' in str(e).lower(), f"mensagem pouco clara: {e}"
    teste("pinos.numeracao colidindo → erro (pad duplicado)",
          t_numeracao_colisao_erro)

    def t_solder_paste_margin():
        """`solder_paste_margin` (topo do YAML) vira propriedade do footprint."""
        dados = {
            'nome': 'TESTE_SPM', 'padrao': 'dual_smd',
            'solder_paste_margin': -0.05,
            'pinos': {'total': 4, 'pitch': 1.27,
                      'tamanho_pad': {'largura': 0.6, 'altura': 1.0},
                      'afastamento_colunas': 4.0},
            'corpo': {'largura': 3.0, 'comprimento': 3.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_spm.kicad_mod')
        gerar_footprint_universal(dados, path)
        content = open(path, 'r', encoding='utf-8').read()
        assert 'solder_paste_margin' in content, \
            "solder_paste_margin não foi escrito no .kicad_mod"
    teste("solder_paste_margin aplicado ao footprint", t_solder_paste_margin)

    def t_relatorio_polaridade_e_material():
        """`eletrico.polaridade` e `*.material` aparecem no relatório.

        O relatório iterava uma lista fixa que omitia polaridade — e nenhum
        código lia os materiais.
        """
        from gerador_relatorio import _specs_to_html, _specs_materiais
        html = _specs_to_html({'eletrico': {'polaridade': True}})
        assert 'Polaridade' in html and 'Polarizado' in html, \
            f"polaridade ausente do relatório: {html}"
        # False é falsy — não pode sumir
        html_f = _specs_to_html({'eletrico': {'polaridade': False}})
        assert 'Nao polarizado' in html_f, f"polaridade=False sumiu: {html_f}"
        mats = _specs_materiais({'pcb': {'material': 'FR4'},
                                 'shield_metalico': {'material': 'Aluminum'}})
        assert mats == [('Material do PCB', 'FR4'),
                        ('Material do shield', 'Aluminum')], mats
    teste("relatório mostra polaridade e materiais",
          t_relatorio_polaridade_e_material)

    def t_colisao_pads_erro():
        """Pads sobrepostos = pinos em curto → ERRO, não geração silenciosa.

        `validate_pad_clearance` existia mas ninguém a chamava: dois pads de
        1x1mm com centros a 0,1mm geravam `ok: true`.
        """
        base = {
            'nome': 'TESTE_Colisao', 'padrao': 'custom',
            'corpo': {'largura': 5.0, 'comprimento': 5.0},
            'margens': {'courtyard': 0.25, 'silkscreen': 0.12, 'fab_line': 0.10},
            'kicad': {'referencia': 'U?', 'descricao': 'x', 'tags': 'x'},
        }
        path = os.path.join(saida_dir, 'TESTE_colisao_pads.kicad_mod')

        # sobrepostos → erro
        d = copy.deepcopy(base)
        d['pads'] = [
            {'numero': 1, 'x': 0.0, 'y': 0, 'largura': 1.0, 'altura': 1.0},
            {'numero': 2, 'x': 0.1, 'y': 0, 'largura': 1.0, 'altura': 1.0},
        ]
        try:
            gerar_footprint_universal(d, path)
            assert False, "pads sobrepostos deveriam dar erro"
        except ValueError as e:
            assert 'sobrep' in str(e).lower(), f"mensagem pouco clara: {e}"

        # separados → gera normal
        d = copy.deepcopy(base)
        d['pads'] = [
            {'numero': 1, 'x': 0.0, 'y': 0, 'largura': 1.0, 'altura': 1.0},
            {'numero': 2, 'x': 2.0, 'y': 0, 'largura': 1.0, 'altura': 1.0},
        ]
        gerar_footprint_universal(d, path)

        # mesmo numero = mesmo net: tocar ali e' intencional, nao e' curto
        d = copy.deepcopy(base)
        d['pads'] = [
            {'numero': 1, 'x': 0.0, 'y': 0, 'largura': 1.0, 'altura': 1.0},
            {'numero': 1, 'x': 0.1, 'y': 0, 'largura': 1.0, 'altura': 1.0},
        ]
        gerar_footprint_universal(d, path)
    teste("pads sobrepostos → erro (custom)", t_colisao_pads_erro)

    def t_single_row_pth():
        """Header 1xN é fileira ÚNICA — antes caía no dual_pth (2 fileiras).

        Regressão: Conn_01x03 (total: 3) saía com 2 pads EMPILHADOS em (0,0),
        porque total//2 descartava o pino ímpar e afastamento_colunas ausente
        colapsava as colunas.
        """
        from gerador_footprint_v2 import _TIPO_PARA_PADRAO
        assert _TIPO_PARA_PADRAO['conector_pth'] == 'single_row_pth', \
            "conector_pth deve mapear para single_row_pth, não dual_pth"

        for total in (3, 6):
            dados = {
                'nome': f'TESTE_Header_1x{total}', 'tipo': 'conector_pth',
                'pinos': {'total': total, 'pitch': 2.54,
                          'diametro_pad': 1.7, 'diametro_furo': 1.0},
                'margens': {'courtyard': 0.5, 'silkscreen': 0.12, 'fab_line': 0.10},
                'kicad': {'referencia': 'J?', 'descricao': 'x', 'tags': 'x'},
            }
            path = os.path.join(saida_dir, f'TESTE_header_1x{total}.kicad_mod')
            gerar_footprint_universal(dados, path)
            content = open(path, 'r', encoding='utf-8').read()
            nums = re.findall(r'\(pad "?(\d+)"?\s', content)
            assert len(nums) == total, \
                f"1x{total} deveria ter {total} pads, tem {len(nums)}"
            assert sorted(map(int, nums)) == list(range(1, total + 1)), \
                f"numeração errada em 1x{total}: {sorted(nums)}"
            # nenhum pad coincidente (o bug era empilhar em (0,0))
            pos = re.findall(r'\(pad "?\d+"? \w+ \w+ \(at ([-\d.]+ [-\d.]+)\)', content)
            assert len(set(pos)) == len(pos), \
                f"1x{total} tem pads coincidentes: {pos}"
    teste("header 1xN gera fileira única (regressão)", t_single_row_pth)

    def t_schema_realmente_ativo():
        """A validação de schema tem que estar ATIVA, não degradada em silêncio.

        `validador_schema` faz `except ImportError: return (True, [])` — sem a
        lib `jsonschema` ele devolve "válido" para QUALQUER coisa. O CI não a
        instalava, então a regra "JSON Schema é a verdade" (AGENTS.md) nunca
        foi verificada lá: todo YAML passava.
        """
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            assert False, ("jsonschema não instalado — a validação de schema "
                           "está devolvendo 'válido' para tudo. "
                           "Instale: pip install jsonschema")
        from validador_schema import validar_schema
        ok, erros = validar_schema({'padrao': 'custom'})   # falta `nome`
        assert not ok, ("schema aceitou YAML sem 'nome' — validação inativa?")
    teste("validação de schema está ativa (jsonschema presente)",
          t_schema_realmente_ativo)

    def t_schema_typo_pad():
        """Typo em campo opcional de pad → erro, não default silencioso.

        `formto: circulo` entregava um pad retangular SMD com ok: true.
        """
        from validador_schema import validar_schema
        bom = {'nome': 'T', 'padrao': 'custom',
               'pads': [{'numero': 1, 'x': 0, 'y': 0,
                         'largura': 1.0, 'altura': 1.0, 'formato': 'circulo'}]}
        ok, _ = validar_schema(bom)
        assert ok, "YAML válido não deveria falhar"

        ruim = copy.deepcopy(bom)
        ruim['pads'][0].pop('formato')
        ruim['pads'][0]['formto'] = 'circulo'      # typo
        ok, erros = validar_schema(ruim)
        assert not ok, "typo em campo opcional deveria falhar no schema"
        assert any('formto' in str(e) for e in erros), f"erro não cita o typo: {erros}"
    teste("typo em campo de pad → erro no schema", t_schema_typo_pad)


# =============================================================================
# EXECUÇÃO
# =============================================================================
if __name__ == '__main__':
    sys.path.append(os.path.join(PROJ, 'libs'))
    print("\n" + "="*70)
    print("  ROTINA DE TESTES - EDA Footprint Generator v2.0")
    print("="*70)

    test_grupo1()   # Imports
    test_grupo2()   # Validador IPC
    test_grupo3()   # Motor Universal (8 padrões)
    test_grupo4()   # Shim tipo→padrao
    test_grupo5()   # Gerador de Símbolos
    test_grupo6()   # Formato v6+
    test_grupo7()   # Helpers
    test_grupo8()   # Presets YAML
    test_grupo9()   # Consistência
    test_grupo10()  # Documentação
    test_grupo11()  # Templates 3D
    test_grupo12()  # Edge cases
    test_grupo13()  # Gerador de BOM
    test_grupo14()  # Verificador DRC
    test_grupo15()  # Exportação multi-formato
    test_grupo16()  # sexpr_parser
    test_grupo17()  # BGA
    test_grupo18()  # Validação conteúdo KiCad
    test_grupo19()  # Shim edge cases
    test_grupo20()  # pinos.overrides (dict e lista)

    # ── Relatório Final ──────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  RESULTADO FINAL")
    print(f"{'='*70}")
    print(f"  Total:   {_total}")
    print(f"  ✅ OK:    {_ok}")
    print(f"  ❌ Falha: {_fail}")
    print(f"{'='*70}")

    if _erros:
        print(f"\n  DETALHES DOS ERROS:\n")
        for nome, msg, tb in _erros:
            print(f"  ── {nome} ──")
            print(f"     {msg}")
            # Mostrar últimas 3 linhas do traceback
            tb_lines = tb.strip().split('\n')
            for line in tb_lines[-3:]:
                print(f"     {line}")
            print()

    if _fail == 0:
        print("\n  🎉 TODOS OS TESTES PASSARAM! A plataforma v2.0 está funcionando.\n")
    else:
        print(f"\n  ⚠️  {_fail} teste(s) falharam. Verifique os erros acima.\n")

    sys.exit(0 if _fail == 0 else 1)

