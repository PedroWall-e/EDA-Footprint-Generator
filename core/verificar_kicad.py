#!/usr/bin/env python3
# =============================================================================
# verificar_kicad.py
# Valida os arquivos .kicad_mod gerados, verificando se estão de acordo com
# as especificações do KiCad.
#
# Modos de verificação:
#   1. kicad-cli (KiCad 7+): se instalado, roda verificação oficial
#   2. Python nativo: validações por regex sem depender do KiCad instalado
# =============================================================================
import sys
import os
import re
import io
import subprocess
import glob

# UTF-8 no console do Windows
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # root
SAIDA_DIR = os.path.join(PROJ, 'saida')

# =============================================================================
# Detectar kicad-cli
# =============================================================================
_KICAD_CLI_PATHS = [
    'kicad-cli',  # PATH
    r'C:\Program Files\KiCad\8.0\bin\kicad-cli.exe',
    r'C:\Program Files\KiCad\7.0\bin\kicad-cli.exe',
    r'C:\Program Files\KiCad\bin\kicad-cli.exe',
    '/usr/bin/kicad-cli',
    '/usr/local/bin/kicad-cli',
    '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
]

def _find_kicad_cli():
    for path in _KICAD_CLI_PATHS:
        try:
            r = subprocess.run([path, '--version'], capture_output=True, timeout=5)
            if r.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return None


# =============================================================================
# Verificação Python nativa (sem KiCad)
# =============================================================================
def _verificar_python(filepath: str) -> list:
    """
    Valida um .kicad_mod por análise de texto.
    Retorna lista de problemas encontrados (vazia = OK).
    """
    problemas = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return [f'Erro ao ler arquivo: {e}']

    nome = os.path.basename(filepath)

    # 1. Estrutura básica: deve começar com (footprint ou (module
    if not re.search(r'^\s*\((?:footprint|module)\s+', content, re.MULTILINE):
        problemas.append('Estrutura invalida: nao inicia com (footprint ...) ou (module ...)')

    # 2. Deve ter ao menos um pad
    pads = re.findall(r'\(pad\s+', content)
    if not pads:
        problemas.append('Nenhum pad encontrado')

    # 3. Pads THT devem ter drill
    tht_pads = re.findall(r'\(pad\s+\S+\s+thru_hole', content)
    tht_drill = re.findall(r'\(pad\s+\S+\s+thru_hole.*?\(drill\s+[\d.]+\)', content, re.DOTALL)
    if tht_pads and len(tht_drill) < len(tht_pads):
        faltando = len(tht_pads) - len(tht_drill)
        problemas.append(f'{faltando} pad(s) THT sem drill definido')

    # 4. Deve ter camada F.CrtYd (courtyard)
    if 'F.CrtYd' not in content and 'B.CrtYd' not in content:
        problemas.append('Sem courtyard (F.CrtYd / B.CrtYd) — recomendado pelo IPC-7351')

    # 5. Deve ter referência e valor
    if 'reference' not in content.lower():
        problemas.append('Sem texto de referencia (ex: U?, R?, C?)')
    if re.search(r'\(fp_text\s+value', content) is None and \
       re.search(r'\(property\s+"Value"', content) is None:
        problemas.append('Sem texto de valor')

    # 6. Pads SMD devem ter F.Cu e F.Paste no arquivo
    has_smd = bool(re.search(r'\(pad\s+\S+\s+smd', content))
    if has_smd:
        if 'F.Cu' not in content:
            problemas.append('Footprint SMD sem camada F.Cu')
        if 'F.Paste' not in content:
            problemas.append('Footprint SMD sem camada F.Paste')

    # 7. Verificar pads com tamanho zero
    zero_pads = re.findall(r'\(size\s+0(?:\.0+)?\s+0(?:\.0+)?\)', content)
    if zero_pads:
        problemas.append(f'{len(zero_pads)} pad(s) com tamanho zero')

    return problemas


# =============================================================================
# Verificação Python nativa para .kicad_sym
# =============================================================================
def _verificar_sym_python(filepath: str) -> list:
    """
    Valida um .kicad_sym por análise de texto.
    Retorna lista de problemas encontrados (vazia = OK).
    """
    problemas = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return [f'Erro ao ler arquivo: {e}']

    # 1. Estrutura básica: deve começar com (kicad_symbol_lib
    if not re.search(r'^\s*\(kicad_symbol_lib\b', content, re.MULTILINE):
        problemas.append('Estrutura invalida: nao inicia com (kicad_symbol_lib ...)')

    # 2. Deve ter ao menos um símbolo
    symbols = re.findall(r'\(symbol\s+"', content)
    if not symbols:
        problemas.append('Nenhum simbolo encontrado')

    # 3. Deve ter ao menos um pino
    pins = re.findall(r'\(pin\s+', content)
    if not pins:
        problemas.append('Nenhum pino encontrado no simbolo')

    # 4. Parênteses balanceados
    open_count = content.count('(')
    close_count = content.count(')')
    if open_count != close_count:
        problemas.append(f'Parenteses desbalanceados: {open_count} abre vs {close_count} fecha')

    return problemas


# =============================================================================
# Verificação via kicad-cli
# =============================================================================
def _verificar_kicad_cli(cli_path: str, filepath: str) -> list:
    """Roda kicad-cli fp check no arquivo. Retorna lista de problemas."""
    try:
        r = subprocess.run(
            [cli_path, 'fp', 'check', '--input', filepath],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace')
        saida = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and not saida:
            return []
        # Filtrar linhas de erro/aviso
        linhas = [l.strip() for l in saida.splitlines() if l.strip()]
        return linhas if linhas else []
    except subprocess.TimeoutExpired:
        return ['kicad-cli timeout (>30s)']
    except Exception as e:
        return [f'Erro ao executar kicad-cli: {e}']


# =============================================================================
# Runner principal
# =============================================================================
def verificar_todos(saida_dir: str = SAIDA_DIR) -> dict:
    """
    Verifica todos os .kicad_mod em saida_dir.
    Retorna dict: {nome_arquivo: [lista de problemas]} — lista vazia = OK.
    """
    arquivos = sorted(glob.glob(os.path.join(saida_dir, '*.kicad_mod')))
    if not arquivos:
        print(f'Nenhum .kicad_mod encontrado em: {saida_dir}')
        return {}

    cli = _find_kicad_cli()
    modo = f'kicad-cli ({cli})' if cli else 'Python nativo (kicad-cli nao encontrado)'
    print(f'\n=== Verificacao de Footprints KiCad ===')
    print(f'Modo: {modo}')
    print(f'Pasta: {saida_dir}')
    print(f'Arquivos: {len(arquivos)}\n')

    resultados = {}
    ok_count = 0
    warn_count = 0

    for fp in arquivos:
        nome = os.path.basename(fp)
        if cli:
            problemas = _verificar_kicad_cli(cli, fp)
        else:
            problemas = _verificar_python(fp)

        resultados[nome] = problemas

        if not problemas:
            print(f'  [OK]   {nome}')
            ok_count += 1
        else:
            print(f'  [AVISO] {nome}:')
            for p in problemas:
                print(f'          - {p}')
            warn_count += 1

    # ── Verificar .kicad_sym ────────────────────────────────────────────────
    sym_arquivos = sorted(glob.glob(os.path.join(saida_dir, '*.kicad_sym')))
    if sym_arquivos:
        print(f'\n--- Simbolos (.kicad_sym): {len(sym_arquivos)} ---\n')
        for sp in sym_arquivos:
            nome = os.path.basename(sp)
            problemas = _verificar_sym_python(sp)
            resultados[nome] = problemas
            if not problemas:
                print(f'  [OK]   {nome}')
                ok_count += 1
            else:
                print(f'  [AVISO] {nome}:')
                for p in problemas:
                    print(f'          - {p}')
                warn_count += 1

    total_arq = len(arquivos) + len(sym_arquivos)
    print(f'\nResultado: {ok_count} OK  |  {warn_count} com avisos  |  {total_arq} total')
    if not cli:
        print('\n[INFO] Para verificacao oficial, instale o KiCad 7+ e certifique-se')
        print('       que kicad-cli esta no PATH do sistema.')

    return resultados


if __name__ == '__main__':
    verificar_todos()
