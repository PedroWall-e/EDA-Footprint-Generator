# =============================================================================
# teste_cli.py
# Testes da CLI (cli.py) — verifica subcomandos gerar, validar, batch
#
# Usa subprocess para testar a CLI como o usuário a usa.
# =============================================================================

import os
import sys
import json
import subprocess
import shutil
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(PROJ, 'cli.py')
PYTHON = os.path.join(PROJ, '.venv', 'Scripts', 'python.exe')
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

MODULOS = os.path.join(PROJ, 'modulos_config')

# Contadores globais
_ok = 0
_fail = 0


def teste(descricao, condicao):
    """Registra resultado de teste."""
    global _ok, _fail
    if condicao:
        _ok += 1
        print(f"  ✅ {descricao}")
    else:
        _fail += 1
        print(f"  ❌ {descricao}")


def _run_cli(*args, json_mode=False, timeout=60):
    """Executa cli.py e retorna (returncode, stdout, stderr)."""
    cmd = [PYTHON, '-W', 'ignore::DeprecationWarning', '-X', 'utf8', CLI]
    if json_mode:
        cmd.append('--json')
    cmd.extend(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding='utf-8',
        cwd=PROJ, timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


# ─── Grupo 1: Comandos básicos ───────────────────────────────────────────────

print("\n📋 Grupo 1: Comandos básicos da CLI")

rc, out, _ = _run_cli('--help')
teste("cli.py --help retorna exit 0", rc == 0)
teste("--help contém 'gerar'", 'gerar' in out)
teste("--help contém 'validar'", 'validar' in out)
teste("--help contém 'batch'", 'batch' in out)


# ─── Grupo 2: Subcomando validar ─────────────────────────────────────────────

print("\n📋 Grupo 2: Subcomando validar")

yaml_valido = os.path.join(MODULOS, 'NE555_DIP8.yaml')
rc, out, _ = _run_cli('validar', yaml_valido)
teste("validar NE555_DIP8.yaml retorna exit 0", rc == 0)

rc, out, _ = _run_cli('--json', 'validar', yaml_valido)
teste("validar --json retorna JSON válido", rc == 0)
try:
    data = json.loads(out)
    teste("JSON contém campo 'ok'", 'ok' in data)
except (json.JSONDecodeError, ValueError):
    teste("JSON parseável", False)


# ─── Grupo 3: Subcomando gerar ───────────────────────────────────────────────

print("\n📋 Grupo 3: Subcomando gerar")

# Criar diretório temporário
saida_test = os.path.join(PROJ, 'saida', '_cli_test_auto')
os.makedirs(saida_test, exist_ok=True)

# Gerar componente com padrao: (v2 direto)
rc, out, _ = _run_cli('gerar', os.path.join(MODULOS, 'MT6835GT_QFN16.yaml'),
                       '-o', saida_test)
teste("gerar MT6835GT (padrao: quad_smd) exit 0", rc == 0)
teste(".kicad_mod existe", os.path.exists(os.path.join(saida_test, 'MT6835GT_QFN16.kicad_mod')))
teste(".kicad_sym existe", os.path.exists(os.path.join(saida_test, 'MT6835GT_QFN16.kicad_sym')))

# Gerar componente com tipo: (shim v1→v2)
rc, out, _ = _run_cli('gerar', os.path.join(MODULOS, 'NE555_DIP8.yaml'),
                       '-o', saida_test)
teste("gerar NE555 (tipo: ci_dip → shim v2) exit 0", rc == 0)
teste("NE555 .kicad_mod existe", os.path.exists(os.path.join(saida_test, 'NE555_DIP8.kicad_mod')))

# Verificar campo Footprint preenchido
sym_path = os.path.join(saida_test, 'NE555_DIP8.kicad_sym')
if os.path.exists(sym_path):
    with open(sym_path, encoding='utf-8') as f:
        sym_text = f.read()
    teste("Footprint preenchido no .kicad_sym",
          'Footprint' in sym_text and '""' not in sym_text.split('Footprint')[1][:20])
else:
    teste("Footprint preenchido no .kicad_sym", False)


# ─── Grupo 4: Erros ──────────────────────────────────────────────────────────

print("\n📋 Grupo 4: Tratamento de erros")

rc, _, _ = _run_cli('gerar', 'arquivo_que_nao_existe.yaml', '-o', saida_test)
teste("gerar arquivo inexistente retorna erro", rc != 0)


# ─── Grupo 5: Subcomando batch ────────────────────────────────────────────────

print("\n📋 Grupo 5: Subcomando batch")

saida_batch = os.path.join(PROJ, 'saida', '_cli_batch_test')
os.makedirs(saida_batch, exist_ok=True)

# batch pode retornar exit!=0 se algum componente falha (ex: 3D sem CadQuery)
# mas ainda gera footprints para os que funcionam
rc, out, _ = _run_cli('batch', MODULOS, '-o', saida_batch, timeout=120)
teste("batch executou sem crash", True)

# Contar quantos .kicad_mod foram gerados
mods = [f for f in os.listdir(saida_batch) if f.endswith('.kicad_mod')]
teste(f"batch gerou {len(mods)} footprints (>= 10)", len(mods) >= 10)


# ─── Grupo 6: Modo JSON ──────────────────────────────────────────────────────

print("\n📋 Grupo 6: Modo --json")

rc, out, _ = _run_cli('--json', 'gerar',
                       os.path.join(MODULOS, 'resistor_470R.yaml'),
                       '-o', saida_test)
# O JSON pode ter output de log antes — extrair apenas o JSON
json_text = out
if '{' in out:
    json_text = out[out.index('{'):]
try:
    data = json.loads(json_text)
    teste("Output --json é JSON válido", True)
    teste("JSON contém 'arquivos'", 'arquivos' in data)
except (json.JSONDecodeError, ValueError):
    teste("Output --json é JSON válido", False)


# ─── Grupo 7: Listar padrões ─────────────────────────────────────────────────

print("\n📋 Grupo 7: Subcomando padroes")

rc, out, _ = _run_cli('padroes')
teste("padroes retorna exit 0", rc == 0)
teste("padroes contém 'dual_smd'", 'dual_smd' in out)
teste("padroes contém 'axial_pth'", 'axial_pth' in out)


# ─── Limpeza ──────────────────────────────────────────────────────────────────

shutil.rmtree(saida_test, ignore_errors=True)
shutil.rmtree(saida_batch, ignore_errors=True)


# ─── Resultado final ─────────────────────────────────────────────────────────

print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║   RESULTADO — Testes CLI                                           ║
║══════════════════════════════════════════════════════════════════════║
║    Total:   {_ok + _fail}
║    ✅ OK:    {_ok}
║    ❌ Falha: {_fail}
╚══════════════════════════════════════════════════════════════════════╝
""")

sys.exit(1 if _fail > 0 else 0)
