# =============================================================================
# gerador_universal.py
# Motor de geração universal — lido em tempo real pelo runner_stub.py.
# Le _estado_atual.json, gera o footprint 2D e o modelo 3D.
# Exporta automaticamente o modelo como STEP após cada geração 3D.
#
# Variáveis disponíveis no bloco modelo_3d_python do YAML:
#   cq          — CadQuery (import cadquery as cq)
#   show_object — função do CQ-Editor para exibir geometria 3D
#   dados       — dict completo do YAML carregado
#   nome        — dados['nome']
#   os, math    — módulos utilitários
# =============================================================================

import sys
import os
import json
import math
import yaml
import traceback
import cadquery as cq

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # root
CORE_DIR = os.path.join(PROJ, 'core')
for _p in [PROJ, CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ─── Log em arquivo (independente do stdout do CQ-Editor) ────────────────────
DEBUG = os.environ.get('CAD_FRONTIER_DEBUG', '').lower() in ('1', 'true', 'yes')
_LOG = os.path.join(PROJ, '_debug_3d.txt')
if DEBUG:
    with open(_LOG, 'w', encoding='utf-8') as _f:
        _f.write("=== gerador_universal.py iniciado ===\n")

def _log(msg):
    print(msg)
    if DEBUG:
        with open(_LOG, 'a', encoding='utf-8') as _f:
            _f.write(str(msg) + '\n')

# ─── Ler estado atual ────────────────────────────────────────────────────────
estado_path = os.path.join(PROJ, '_estado_atual.json')
if not os.path.isfile(estado_path):
    raise FileNotFoundError("_estado_atual.json nao encontrado. Abra um YAML e clique Gerar.")

with open(estado_path, 'r', encoding='utf-8') as f:
    estado = json.load(f)

yaml_path = estado.get('yaml_path', '')
if not yaml_path or not os.path.isfile(yaml_path):
    raise FileNotFoundError(f"YAML nao encontrado: {yaml_path}")

_log(f"YAML: {os.path.basename(yaml_path)}")

# ─── Carregar YAML ───────────────────────────────────────────────────────────
with open(yaml_path, 'r', encoding='utf-8') as f:
    dados = yaml.safe_load(f)

nome = dados['nome']
tipo = dados.get('tipo', '')
padrao = dados.get('padrao', '')
_log(f"Componente: {nome}  |  tipo: {tipo}  |  padrao: {padrao}")

# ─── Validação IPC-7351B ────────────────────────────────────────────────────
try:
    from validador_ipc import validar_yaml
    _ipc_result = validar_yaml(dados)
    if _ipc_result.errors:
        for _e in _ipc_result.errors:
            _log(f"  IPC ERRO: {_e}")
    if _ipc_result.warnings:
        for _w in _ipc_result.warnings:
            _log(f"  IPC AVISO: {_w}")
    if _ipc_result.info:
        for _i in _ipc_result.info:
            _log(f"  IPC INFO: {_i}")
    if not _ipc_result.ok:
        _log(f"ABORTANDO: {len(_ipc_result.errors)} erro(s) IPC encontrado(s). "
             f"Corrija o YAML antes de gerar.")
        raise SystemExit(1)
    _log(f"Validação IPC OK ({len(_ipc_result.warnings)} avisos)")
except ImportError:
    _log("[AVISO] validador_ipc não encontrado — validação IPC ignorada")

# ─── Diretório de saída (configurável via estado) ───────────────────────────
_output_dir = estado.get('output_dir', os.path.join(PROJ, 'saida'))
os.makedirs(_output_dir, exist_ok=True)
_log(f"Saída: {_output_dir}")

# ─── Gerar footprint 2D (.kicad_mod) ────────────────────────────────────────
kicad_path = os.path.join(_output_dir, f"{nome}.kicad_mod")

if padrao:
    # Motor Universal v2 (paramétrico)
    from gerador_footprint_v2 import gerar_footprint_universal
    gerar_footprint_universal(dados, kicad_path)
    _log(f"Footprint 2D (universal, padrao={padrao}): {os.path.basename(kicad_path)}")
else:
    # v2 com shim de compatibilidade tipo→padrao
    from gerador_footprint_v2 import gerar_footprint_universal
    gerar_footprint_universal(dados, kicad_path)
    _log(f"Footprint 2D (v2 compat): {os.path.basename(kicad_path)}")

# Salvar caminho do .kicad_mod no estado para o viewer 2D
estado['kicad_mod_path'] = kicad_path
with open(estado_path, 'w', encoding='utf-8') as f:
    json.dump(estado, f, ensure_ascii=False, indent=2)


# =============================================================================
# Templates 3D — importados de gerador_3d.py (motor headless)
# =============================================================================
from gerador_3d import rotear_template_3d as _gerar_3d_template




# =============================================================================
_log("Iniciando modelo 3D...")

# Lista que acumula as geometrias para exportar como STEP
_partes_step = []

def _show_object_wrapper(shape, name=None, options=None):
    """
    Wrapper sobre show_object do CQ-Editor:
    - Exibe a geometria no viewer interativo (comportamento original).
    - Armazena a geometria em _partes_step para exportação STEP posterior.
    """
    if options is None:
        options = {}
    show_object(shape, name=name, options=options)   # exibe no viewer
    try:
        _partes_step.append((shape, name or f'part_{len(_partes_step)}'))
    except Exception:
        pass


try:
    codigo_python = dados.get('modelo_3d_python')

    if codigo_python:
        # ── Código Python embutido no YAML (modelo_3d_python) ─────────────
        _log("Executando modelo_3d_python do YAML...")
        _SAFE_BUILTINS = {
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'int': int, 'float': float, 'str': str, 'bool': bool,
            'len': len, 'range': range, 'enumerate': enumerate,
            'list': list, 'dict': dict, 'tuple': tuple,
            'zip': zip, 'map': map, 'filter': filter,
            'sorted': sorted, 'reversed': reversed,
            'print': print, 'isinstance': isinstance,
            'True': True, 'False': False, 'None': None,
        }
        _namespace = {
            '__builtins__': _SAFE_BUILTINS,
            'cq':          cq,
            'show_object': _show_object_wrapper,
            'dados':       dados,
            'nome':        nome,
            'math':        math,
        }
        exec(compile(codigo_python, f"<{nome}.yaml>", 'exec'), _namespace)
        _log("modelo_3d_python executado com sucesso!")

    else:
        # ── Templates built-in por tipo ───────────────────────────────────
        _log(f"Usando template built-in para tipo='{tipo}'...")
        _template_result = _gerar_3d_template(tipo, dados, nome, _show_object_wrapper, cq, _log)

    _log("=== 3D CONCLUIDO ===")

except Exception as _e:
    _log(f"ERRO 3D: {type(_e).__name__}: {_e}")
    _log(traceback.format_exc())
    _template_result = None

# ─── Exportar STEP ───────────────────────────────────────────────────────────
step_path = os.path.join(_output_dir, f"{nome}.step")
try:
    # Se o template retornou um Assembly pronto (ex: BGA), salvar direto
    if '_template_result' in dir() and _template_result is not None and isinstance(_template_result, cq.Assembly):
        _template_result.save(step_path, exportType='STEP')
        _log(f"STEP exportado (Assembly direto): {os.path.basename(step_path)}")
        estado['step_path'] = step_path
        with open(estado_path, 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    elif _partes_step:
        assembly = cq.Assembly()
        for _shape, _name in _partes_step:
            try:
                assembly.add(_shape, name=_name)
            except Exception:
                pass
        assembly.save(step_path, exportType='STEP')
        _log(f"STEP exportado: {os.path.basename(step_path)}")
        estado['step_path'] = step_path
        with open(estado_path, 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    else:
        _log("[AVISO] Nenhuma geometria capturada para exportar como STEP.")
except Exception as _se:
    _log(f"[AVISO] STEP nao exportado: {_se}")

# ─── Gerar Símbolo Esquemático (.kicad_sym) ───────────────────────────────────
sym_path = os.path.join(_output_dir, f"{nome}.kicad_sym")
try:
    from gerador_symbol import gerar_symbol
    gerar_symbol(dados, sym_path)
    estado['sym_path'] = sym_path
    with open(estado_path, 'w', encoding='utf-8') as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
except Exception as _sy_e:
    _log(f"[AVISO] Symbol nao gerado: {_sy_e}")

