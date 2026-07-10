#!/usr/bin/env python3
# =============================================================================
# cli.py
# CLI para a EDA Footprint Generator.
#
# Uso:
#   python cli.py gerar componente.yaml -o saida/
#   python cli.py validar componente.yaml
#   python cli.py padroes
#   python cli.py tipos-3d
#   python cli.py batch modulos_config/ -o saida/
#   python cli.py schema
#   echo '{"nome":"R1",...}' | python cli.py gerar --stdin -o saida/
# =============================================================================

import argparse
import json
import os
import sys


# Forçar UTF-8 no Windows (evita UnicodeEncodeError com emojis)
if sys.platform == 'win32' and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Paths do projeto
PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(PROJ_DIR, 'core')
for _p in [PROJ_DIR, CORE_DIR, os.path.join(PROJ_DIR, 'KicadModTree_dev')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_yaml(path):
    """Carrega um arquivo YAML e retorna o dict."""
    import yaml
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def _gerar_footprint_dispatch(dados, kicad_path):
    """Seleciona e executa o gerador de footprint correto (sempre v2).

    O v2 tem shim de compatibilidade: tipo: (v1) é convertido
    automaticamente para padrao: (v2) via _TIPO_PARA_PADRAO.
    """
    from gerador_footprint_v2 import gerar_footprint_universal
    gerar_footprint_universal(dados, kicad_path)


# =============================================================================
# Subcomando: gerar
# =============================================================================

def cmd_gerar(args):
    """Gera .kicad_mod + .kicad_sym + .step a partir de um YAML ou stdin."""
    import yaml

    # Carregar dados
    if args.stdin:
        raw = sys.stdin.read()
        try:
            dados = json.loads(raw)
        except json.JSONDecodeError:
            dados = yaml.safe_load(raw)
    else:
        if not args.yaml:
            print("ERRO: forneça um arquivo YAML ou use --stdin", file=sys.stderr)
            return 1
        dados = _load_yaml(args.yaml)

    nome = dados.get('nome', 'componente')
    saida = args.output or os.path.join(PROJ_DIR, 'saida')
    os.makedirs(saida, exist_ok=True)
    apenas = args.apenas
    resultados = {}
    erros = []

    def _log(msg):
        if not args.json:
            print(f"  {msg}")

    # --- Validação IPC ---
    try:
        from validador_ipc import validar_yaml
        ipc = validar_yaml(dados)
        if not ipc.ok:
            for e in ipc.errors:
                erros.append(f"IPC: {e}")
            if args.json:
                print(json.dumps({"ok": False, "erros": erros}, ensure_ascii=False, indent=2))
            else:
                print(f"ERRO: {len(ipc.errors)} erro(s) IPC")
                for e in ipc.errors:
                    print(f"  ❌ {e}")
            return 1
    except ImportError:
        pass

    # --- Footprint 2D ---
    if not apenas or apenas == 'footprint':
        try:
            kicad_path = os.path.join(saida, f"{nome}.kicad_mod")
            _gerar_footprint_dispatch(dados, kicad_path)
            resultados['kicad_mod'] = kicad_path
            _log(f"✅ Footprint: {os.path.basename(kicad_path)}")
        except Exception as e:
            erros.append(f"Footprint: {e}")
            _log(f"❌ Footprint: {e}")

    # --- Símbolo esquemático ---
    if not apenas or apenas == 'symbol':
        try:
            sym_path = os.path.join(saida, f"{nome}.kicad_sym")
            from gerador_symbol import gerar_symbol
            gerar_symbol(dados, sym_path)
            resultados['kicad_sym'] = sym_path
            _log(f"✅ Símbolo: {os.path.basename(sym_path)}")
        except Exception as e:
            erros.append(f"Symbol: {e}")
            _log(f"❌ Símbolo: {e}")

    # --- Modelo 3D (.step) ---
    if not apenas or apenas == '3d':
        try:
            step_path = os.path.join(saida, f"{nome}.step")
            from gerador_3d import gerar_3d_step
            result = gerar_3d_step(dados, step_path, log_fn=_log)
            if result:
                resultados['step'] = result
                _log(f"✅ 3D STEP: {os.path.basename(step_path)}")
            else:
                _log("⚠️  3D: nenhuma geometria gerada")
        except ImportError:
            _log("⚠️  3D: cadquery não instalado — .step não gerado")
        except Exception as e:
            erros.append(f"3D: {e}")
            _log(f"❌ 3D: {e}")

    # --- Output ---
    ok = len(erros) == 0
    if args.json:
        out = {
            "ok": ok,
            "nome": nome,
            "arquivos": resultados,
            "erros": erros,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if ok:
            n = len(resultados)
            print(f"\n✅ {nome}: {n} arquivo(s) gerado(s) em {saida}/")
        else:
            print(f"\n❌ {nome}: {len(erros)} erro(s)")

    return 0 if ok else 1


# =============================================================================
# Subcomando: validar
# =============================================================================

def cmd_validar(args):
    """Valida um YAML contra IPC-7351B e JSON Schema."""
    dados = _load_yaml(args.yaml)

    result = {"ok": True, "erros": [], "avisos": [], "info": []}

    # Schema validation
    try:
        from validador_schema import validar_schema
        schema_ok, schema_erros = validar_schema(dados)
        if not schema_ok:
            result["ok"] = False
            result["erros"].extend([f"Schema: {e}" for e in schema_erros])
    except ImportError:
        pass

    # IPC validation
    try:
        from validador_ipc import validar_yaml
        ipc = validar_yaml(dados)
        if not ipc.ok:
            result["ok"] = False
        result["erros"].extend(ipc.errors)
        result["avisos"].extend(ipc.warnings)
        result["info"].extend(ipc.info)
    except ImportError:
        result["avisos"].append("validador_ipc não disponível")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        nome = dados.get('nome', '?')
        if result["ok"]:
            print(f"✅ {nome}: validação OK")
        else:
            print(f"❌ {nome}: {len(result['erros'])} erro(s)")
        for e in result["erros"]:
            print(f"  ❌ {e}")
        for w in result["avisos"]:
            print(f"  ⚠️  {w}")
        for i in result["info"]:
            print(f"  ℹ️  {i}")

    return 0 if result["ok"] else 1


# =============================================================================
# Subcomando: padroes
# =============================================================================

def cmd_padroes(args):
    """Lista padrões de footprint suportados."""
    from gerador_footprint_v2 import listar_padroes
    padroes = listar_padroes()
    if args.json:
        print(json.dumps(padroes, indent=2))
    else:
        print("Padrões de footprint suportados:")
        for p in sorted(padroes):
            print(f"  • {p}")
    return 0


# =============================================================================
# Subcomando: tipos-3d
# =============================================================================

def cmd_tipos_3d(args):
    """Lista tipos de modelo 3D disponíveis."""
    try:
        from gerador_3d import listar_tipos_3d
        tipos = listar_tipos_3d()
    except ImportError:
        tipos = []

    if args.json:
        print(json.dumps(tipos, indent=2))
    else:
        print("Tipos de modelo 3D disponíveis:")
        for t in tipos:
            print(f"  • {t}")
    return 0


# =============================================================================
# Subcomando: batch
# =============================================================================

def cmd_batch(args):
    """Gera todos os componentes de uma pasta de YAMLs."""
    import yaml
    pasta = args.pasta
    saida = args.output or os.path.join(PROJ_DIR, 'saida')
    os.makedirs(saida, exist_ok=True)

    yamls = sorted([
        f for f in os.listdir(pasta)
        if f.endswith(('.yaml', '.yml'))
        and not f.startswith('_template')
    ])

    resultados = []
    ok_count = 0
    err_count = 0

    for yf in yamls:
        path = os.path.join(pasta, yf)
        try:
            dados = _load_yaml(path)
            nome = dados.get('nome', yf)

            arquivos = []
            apenas = args.apenas

            # Footprint
            if not apenas or apenas == 'footprint':
                kicad_path = os.path.join(saida, f"{nome}.kicad_mod")
                _gerar_footprint_dispatch(dados, kicad_path)
                arquivos.append('.kicad_mod')

            # Symbol
            if not apenas or apenas == 'symbol':
                sym_path = os.path.join(saida, f"{nome}.kicad_sym")
                from gerador_symbol import gerar_symbol
                gerar_symbol(dados, sym_path)
                arquivos.append('.kicad_sym')

            # 3D
            if not apenas or apenas == '3d':
                try:
                    step_path = os.path.join(saida, f"{nome}.step")
                    from gerador_3d import gerar_3d_step
                    if gerar_3d_step(dados, step_path, log_fn=lambda m: None):
                        arquivos.append('.step')
                except ImportError:
                    pass

            resultados.append({"nome": nome, "ok": True, "arquivos": arquivos})
            ok_count += 1
            if not args.json:
                print(f"  ✅ {nome}: {', '.join(arquivos)}")

        except Exception as e:
            resultados.append({"nome": yf, "ok": False, "erros": [str(e)]})
            err_count += 1
            if not args.json:
                print(f"  ❌ {yf}: {e}")

    if args.json:
        out = {
            "total": len(yamls),
            "sucesso": ok_count,
            "falha": err_count,
            "resultados": resultados,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"  Total: {len(yamls)}  ✅ {ok_count}  ❌ {err_count}")
        print(f"  Saída: {saida}/")
        print(f"{'='*50}")

    return 0 if err_count == 0 else 1


# =============================================================================
# Subcomando: schema
# =============================================================================

def cmd_schema(args):
    """Imprime o JSON Schema do componente."""
    schema_path = os.path.join(PROJ_DIR, 'schemas', 'component.schema.json')
    if os.path.isfile(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print(json.dumps({"error": "Schema não encontrado. Crie schemas/component.schema.json."},
                          indent=2))
        return 1
    return 0


# =============================================================================
# Parser principal
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog='datafrontier',
        description='EDA Footprint Generator — CLI para geração de componentes eletrônicos',
    )
    parser.add_argument('--json', action='store_true',
                        help='Saída em formato JSON (para agentes IA)')

    sub = parser.add_subparsers(dest='comando', help='Subcomando')

    # gerar
    p_gerar = sub.add_parser('gerar', help='Gerar .kicad_mod + .kicad_sym + .step')
    p_gerar.add_argument('yaml', nargs='?', help='Arquivo YAML do componente')
    p_gerar.add_argument('--stdin', action='store_true',
                         help='Ler dados de stdin (JSON ou YAML)')
    p_gerar.add_argument('-o', '--output', help='Diretório de saída')
    p_gerar.add_argument('--apenas', choices=['footprint', 'symbol', '3d'],
                         help='Gerar apenas um tipo de saída')
    p_gerar.set_defaults(func=cmd_gerar)

    # validar
    p_validar = sub.add_parser('validar', help='Validar YAML (IPC + Schema)')
    p_validar.add_argument('yaml', help='Arquivo YAML do componente')
    p_validar.set_defaults(func=cmd_validar)

    # padroes
    p_padroes = sub.add_parser('padroes', help='Listar padrões de footprint')
    p_padroes.set_defaults(func=cmd_padroes)

    # tipos-3d
    p_tipos = sub.add_parser('tipos-3d', help='Listar tipos de modelo 3D')
    p_tipos.set_defaults(func=cmd_tipos_3d)

    # batch
    p_batch = sub.add_parser('batch', help='Gerar todos os YAMLs de uma pasta')
    p_batch.add_argument('pasta', help='Pasta com arquivos YAML')
    p_batch.add_argument('-o', '--output', help='Diretório de saída')
    p_batch.add_argument('--apenas', choices=['footprint', 'symbol', '3d'],
                         help='Gerar apenas um tipo de saída')
    p_batch.set_defaults(func=cmd_batch)

    # schema
    p_schema = sub.add_parser('schema', help='Imprimir JSON Schema do componente')
    p_schema.set_defaults(func=cmd_schema)

    args = parser.parse_args()
    if not args.comando:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
