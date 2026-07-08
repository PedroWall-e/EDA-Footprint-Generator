#!/usr/bin/env python3
# =============================================================================
# exportar_biblioteca.py
# Exporta todos os YAMLs de modulos_config/ para uma biblioteca KiCad (.pretty)
# =============================================================================
import sys
import os
import yaml
import shutil
import io
import json
import hashlib
import re
import logging

log = logging.getLogger(__name__)

# Garantir UTF-8 no console do Windows
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # root
CORE_DIR = os.path.join(PROJ, 'core')
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

try:
    from core.gerador_footprint_v2 import gerar_footprint_universal as gerar_footprint_v2
    from core.gerador_symbol import gerar_symbol
except ImportError:
    from gerador_footprint_v2 import gerar_footprint_universal as gerar_footprint_v2
    from gerador_symbol import gerar_symbol

# Prefixos de arquivos a ignorar (templates/presets, não componentes reais)
_SKIP_PREFIXES = ('_preset_', '_template')


def _file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def merge_symbols(saida_dir, output_path):
    """Merge todos os .kicad_sym individuais num único arquivo de biblioteca."""
    symbols_content = []
    for f in sorted(os.listdir(saida_dir)):
        if f.endswith('.kicad_sym'):
            with open(os.path.join(saida_dir, f), 'r', encoding='utf-8') as fh:
                content = fh.read()
            # Extrair blocos (symbol ...) do conteúdo
            for m in re.finditer(r'(\(symbol\s+"[^"]+?".*?^\))', content, re.DOTALL | re.MULTILINE):
                symbols_content.append(m.group(1))

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write('(kicad_symbol_lib (version 20231120) (generator DataFrontier)\n')
        for sym in symbols_content:
            out.write('  ' + sym + '\n')
        out.write(')\n')
    log.info(f'Biblioteca de símbolos: {output_path} ({len(symbols_content)} símbolos)')


def gerar_lib_tables(lib_dir):
    """Gera fp-lib-table e sym-lib-table para importação no KiCad."""
    # fp-lib-table
    pretty_dirs = [d for d in os.listdir(lib_dir) if d.endswith('.pretty')]
    fp_table = '(fp_lib_table\n'
    for d in sorted(pretty_dirs):
        name = d.replace('.pretty', '')
        fp_table += f'  (lib (name "{name}")(type KiCad)(uri "${{KIPRJMOD}}/biblioteca_kicad/{d}")(options "")(descr ""))\n'
    fp_table += ')\n'

    fp_path = os.path.join(lib_dir, 'fp-lib-table')
    with open(fp_path, 'w', encoding='utf-8') as f:
        f.write(fp_table)
    log.info(f'fp-lib-table: {fp_path}')

    # sym-lib-table
    sym_table = '(sym_lib_table\n'
    sym_table += '  (lib (name "DataFrontier")(type KiCad)(uri "${KIPRJMOD}/biblioteca_kicad/DataFrontier.kicad_sym")(options "")(descr ""))\n'
    sym_table += ')\n'

    sym_path = os.path.join(lib_dir, 'sym-lib-table')
    with open(sym_path, 'w', encoding='utf-8') as f:
        f.write(sym_table)
    log.info(f'sym-lib-table: {sym_path}')

def exportar_todos():
    config_dir = os.path.join(PROJ, 'modulos_config')
    lib_dir    = os.path.join(PROJ, 'biblioteca_kicad')
    saida_dir  = os.path.join(PROJ, 'saida')
    os.makedirs(saida_dir, exist_ok=True)
    
    yamls = [f for f in os.listdir(config_dir)
             if f.endswith(('.yaml', '.yml')) and not f.startswith('_')]
    
    # Contadores para relatório
    ok = 0
    erros = []
    skipped = 0
    warnings_total = 0

    # Carregar hashes para exportação incremental
    hash_file = os.path.join(lib_dir, '.export_hashes.json')
    try:
        with open(hash_file, 'r', encoding='utf-8') as f:
            hashes = json.load(f)
    except Exception:
        hashes = {}

    # Importar validador IPC (opcional)
    try:
        from validador_ipc import validar_yaml
        has_validator = True
    except ImportError:
        has_validator = False
        log.warning('validador_ipc não encontrado — validação IPC desativada')

    # Filtrar YAMLs excluindo templates e presets
    all_yamls = [f for f in os.listdir(config_dir)
                 if f.endswith(('.yaml', '.yml'))]
    yamls = []
    for f in all_yamls:
        if any(f.startswith(prefix) for prefix in _SKIP_PREFIXES):
            log.debug(f'[SKIP] {f} (template/preset)')
            skipped += 1
        elif not f.startswith('_'):
            yamls.append(f)

    log.info(f'=== Exportação em lote ===')
    log.info(f'Config: {config_dir}')
    log.info(f'YAMLs encontrados: {len(all_yamls)} total, '
             f'{len(yamls)} componentes, {skipped} templates ignorados')

    for yaml_file in sorted(yamls):
        yaml_path = os.path.join(config_dir, yaml_file)
        try:
            # Check incremental hash
            new_hash = _file_hash(yaml_path)
            if hashes.get(yaml_file) == new_hash:
                log.info(f'  [SKIP] {yaml_file} (sem mudanças)')
                skipped += 1
                continue

            with open(yaml_path, 'r', encoding='utf-8') as f:
                dados = yaml.safe_load(f)
            if not isinstance(dados, dict) or 'nome' not in dados:
                continue
            nome = dados['nome']
            tipo = dados.get('tipo', 'custom')

            # Validação IPC (se disponível)
            if has_validator:
                ipc_result = validar_yaml(dados)
                if ipc_result.warnings:
                    warnings_total += len(ipc_result.warnings)
                    for w in ipc_result.warnings:
                        log.warning(f'  IPC [{nome}]: {w}')
                if not ipc_result.ok:
                    for e in ipc_result.errors:
                        log.error(f'  IPC [{nome}]: {e}')
                    erros.append(f'{yaml_file}: Falhou validação IPC '
                                 f'({len(ipc_result.errors)} erros)')
                    continue

            # Gerar footprint no saida/ (sempre v2, com shim tipo→padrao)
            kicad_path = os.path.join(saida_dir, f'{nome}.kicad_mod')
            gerar_footprint_v2(dados, kicad_path)

            # Copiar para biblioteca .pretty
            pretty_dir = os.path.join(lib_dir, f'{tipo}.pretty')
            os.makedirs(pretty_dir, exist_ok=True)
            dest = os.path.join(pretty_dir, f'{nome}.kicad_mod')
            shutil.copy2(kicad_path, dest)

            log.info(f'  [OK] {nome} -> {tipo}.pretty/')

            # Gerar símbolo
            try:
                sym_path = os.path.join(saida_dir, f'{nome}.kicad_sym')
                gerar_symbol(dados, sym_path)
            except Exception as e:
                log.warning(f'  Símbolo não gerado para {nome}: {e}')
                warnings_total += 1

            hashes[yaml_file] = new_hash
            ok += 1
        except Exception as e:
            erros.append(f'{yaml_file}: {e}')
            log.error(f'  [ERRO] {yaml_file}: {e}')

    # Salvar hashes de exportação incremental
    with open(hash_file, 'w', encoding='utf-8') as f:
        json.dump(hashes, f, indent=2)

    # Merge símbolos num único arquivo de biblioteca
    lib_sym_path = os.path.join(lib_dir, 'DataFrontier.kicad_sym')
    merge_symbols(saida_dir, lib_sym_path)

    # Gerar tabelas de biblioteca
    gerar_lib_tables(lib_dir)

    # ═══════════════════════════════════════════════════════════════════════
    # Relatório final
    # ═══════════════════════════════════════════════════════════════════════
    total_processed = ok + len(erros)
    log.info('')
    log.info('═' * 50)
    log.info('  RELATÓRIO DE EXPORTAÇÃO')
    log.info('═' * 50)
    log.info(f'  Total processados:  {total_processed}')
    log.info(f'  Sucesso:            {ok}')
    log.info(f'  Falhas:             {len(erros)}')
    log.info(f'  Avisos IPC:         {warnings_total}')
    log.info(f'  Ignorados (skip):   {skipped}')
    log.info('═' * 50)
    if erros:
        log.info('  Detalhes dos erros:')
        for e in erros:
            log.error(f'    !! {e}')
    log.info('')

    return ok, erros

if __name__ == '__main__':
    # Configurar logging para execução direta
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
    )
    exportar_todos()
