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
import contextlib
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

def _stdout_limpo(args):
    """Em --json o stdout carrega só o JSON — prints do core vão para stderr."""
    if getattr(args, 'json', False):
        return contextlib.redirect_stdout(sys.stderr)
    return contextlib.nullcontext()


# (chave no dict de resultados, rótulo de --apenas, sufixo do arquivo)
_ARTEFATOS = [
    ('kicad_mod', 'footprint', '.kicad_mod'),
    ('kicad_sym', 'symbol', '.kicad_sym'),
    ('step', '3d', '.step'),
]


def _artefatos_pedidos(nome, saida, apenas):
    """Artefatos que esta execução deve produzir, respeitando --apenas."""
    return [(chave, rotulo, os.path.join(saida, f"{nome}{sufixo}"))
            for chave, rotulo, sufixo in _ARTEFATOS
            if not apenas or apenas == rotulo]


def _conferir_no_disco(pedidos, resultados, pulados, falhou):
    """Confirma no disco que cada artefato pedido saiu de fato.

    A ausência de exceção não é prova: o gerador já respondeu "ok": true para
    um .kicad_sym que nunca chegou a ser escrito.
    """
    erros = []
    for chave, rotulo, caminho_previsto in pedidos:
        if chave in falhou or chave in pulados:
            continue
        if chave not in resultados:
            erros.append(f"{rotulo}: não foi gerado e o gerador não disse por quê")
            continue
        caminho = resultados.get(chave) or caminho_previsto
        if not os.path.isfile(caminho):
            erros.append(
                f"{rotulo}: o gerador respondeu OK, mas o arquivo não existe "
                f"no disco: {caminho}")
        elif os.path.getsize(caminho) == 0:
            erros.append(f"{rotulo}: arquivo gerado está vazio (0 bytes): {caminho}")
    return erros


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
    if not getattr(args, 'dry_run', False):
        os.makedirs(saida, exist_ok=True)
    apenas = args.apenas
    resultados = {}
    erros = []
    pulados = {}   # artefato que o gerador declinou por indisponibilidade
    falhou = set()  # etapa que já registrou erro próprio
    pedidos = _artefatos_pedidos(nome, saida, apenas)

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

    # --- Dry-run: validate + report planned outputs, write nothing ---
    if getattr(args, 'dry_run', False):
        planned = [caminho for _, _, caminho in pedidos]
        if args.json:
            print(json.dumps({
                "ok": True,
                "dry_run": True,
                "nome": nome,
                "saida": saida,
                "planned": planned,
            }, ensure_ascii=False, indent=2))
        else:
            print(f"DRY-RUN: would generate for '{nome}' into {saida}/")
            for path in planned:
                print(f"  would write: {path}")
        return 0

    # --- Footprint 2D ---
    if not apenas or apenas == 'footprint':
        try:
            kicad_path = os.path.join(saida, f"{nome}.kicad_mod")
            with _stdout_limpo(args):
                _gerar_footprint_dispatch(dados, kicad_path)
            resultados['kicad_mod'] = kicad_path
            _log(f"✅ Footprint: {os.path.basename(kicad_path)}")
        except Exception as e:
            erros.append(f"Footprint: {e}")
            falhou.add('kicad_mod')
            _log(f"❌ Footprint: {e}")

    # --- Símbolo esquemático ---
    if not apenas or apenas == 'symbol':
        try:
            sym_path = os.path.join(saida, f"{nome}.kicad_sym")
            from gerador_symbol import gerar_symbol
            with _stdout_limpo(args):
                gerar_symbol(dados, sym_path)
            resultados['kicad_sym'] = sym_path
            _log(f"✅ Símbolo: {os.path.basename(sym_path)}")
        except Exception as e:
            erros.append(f"Symbol: {e}")
            falhou.add('kicad_sym')
            _log(f"❌ Símbolo: {e}")

    # --- Modelo 3D (.step) ---
    if not apenas or apenas == '3d':
        try:
            step_path = os.path.join(saida, f"{nome}.step")
            from gerador_3d import gerar_3d_step
            with _stdout_limpo(args):
                result = gerar_3d_step(dados, step_path, log_fn=_log)
            if result:
                resultados['step'] = result
                _log(f"✅ 3D STEP: {os.path.basename(step_path)}")
            else:
                # gerar_3d_step documenta None como falha, não como recusa.
                erros.append("3D: nenhuma geometria gerada (gerar_3d_step retornou None)")
                falhou.add('step')
                _log("❌ 3D: nenhuma geometria gerada")
        except ImportError:
            pulados['step'] = "cadquery não instalado"
            _log("⚠️  3D: cadquery não instalado — .step não gerado")
        except Exception as e:
            erros.append(f"3D: {e}")
            falhou.add('step')
            _log(f"❌ 3D: {e}")

    # --- Conferência: o que foi pedido saiu mesmo? (regra 10) ---
    for e in _conferir_no_disco(pedidos, resultados, pulados, falhou):
        erros.append(e)
        _log(f"❌ {e}")

    # --- Output ---
    ok = len(erros) == 0
    if args.json:
        out = {
            "ok": ok,
            "nome": nome,
            "arquivos": resultados,
            "pulados": pulados,
            "erros": erros,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if ok:
            n = len(resultados)
            print(f"\n✅ {nome}: {n} de {len(pedidos)} arquivo(s) gerado(s) em {saida}/")
            for chave, motivo in pulados.items():
                print(f"  ⚠️  {chave} não gerado: {motivo}")
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

    # DRC. Com --footprint mede a geometria real do arquivo gerado e confere o
    # modelo 3D; sem ele, só a estimativa que o YAML permite.
    try:
        from verificador_drc import verificar_drc, verificar_drc_arquivo
        if args.footprint:
            if not os.path.isfile(args.footprint):
                result["ok"] = False
                result["erros"].append(
                    f"DRC: footprint não encontrado: {args.footprint}")
                drc = None
            else:
                drc = verificar_drc_arquivo(args.footprint, dados=dados)
        else:
            drc = verificar_drc(dados)
            result["info"].append(
                "DRC: rodou sobre o YAML (estimativa). O veredito de silkscreen "
                "sobre pad e de modelo 3D exige --footprint <arquivo.kicad_mod>.")
        if drc is not None:
            if not drc.ok:
                result["ok"] = False
            result["erros"].extend([f"DRC: {e}" for e in drc.errors])
            result["avisos"].extend([f"DRC: {w}" for w in drc.warnings])
            result["info"].extend([f"DRC: {i}" for i in drc.info])
    except ImportError:
        result["avisos"].append("verificador_drc não disponível")

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
    dry = getattr(args, 'dry_run', False)
    if not dry:
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
            pedidos = _artefatos_pedidos(nome, saida, apenas)
            produzidos = {}
            pulados = {}
            falhou = set()

            # Footprint
            if not apenas or apenas == 'footprint':
                if not dry:
                    kicad_path = os.path.join(saida, f"{nome}.kicad_mod")
                    with _stdout_limpo(args):
                        _gerar_footprint_dispatch(dados, kicad_path)
                    produzidos['kicad_mod'] = kicad_path
                arquivos.append('.kicad_mod')

            # Symbol
            if not apenas or apenas == 'symbol':
                if not dry:
                    sym_path = os.path.join(saida, f"{nome}.kicad_sym")
                    from gerador_symbol import gerar_symbol
                    with _stdout_limpo(args):
                        gerar_symbol(dados, sym_path)
                    produzidos['kicad_sym'] = sym_path
                arquivos.append('.kicad_sym')

            # 3D
            if not apenas or apenas == '3d':
                if dry:
                    arquivos.append('.step')
                else:
                    try:
                        step_path = os.path.join(saida, f"{nome}.step")
                        from gerador_3d import gerar_3d_step
                        with _stdout_limpo(args):
                            r3d = gerar_3d_step(dados, step_path, log_fn=lambda m: None)
                        if r3d:
                            produzidos['step'] = r3d
                            arquivos.append('.step')
                        else:
                            falhou.add('step')
                            raise RuntimeError(
                                "3D: nenhuma geometria gerada (gerar_3d_step retornou None)")
                    except ImportError:
                        pulados['step'] = "cadquery não instalado"

            faltando = [] if dry else _conferir_no_disco(
                pedidos, produzidos, pulados, falhou)
            if faltando:
                raise RuntimeError('; '.join(faltando))

            resultados.append({"nome": nome, "ok": True, "arquivos": arquivos,
                               "pulados": pulados})
            ok_count += 1
            if not args.json:
                verbo = "would write" if dry else "gerado"
                print(f"  ✅ {nome}: {', '.join(arquivos)}  ({verbo})")

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
            "dry_run": dry,
            "resultados": resultados,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"  Total: {len(yamls)}  ✅ {ok_count}  ❌ {err_count}")
        if dry:
            print("  DRY-RUN — nada foi escrito")
        else:
            print(f"  Saída: {saida}/")
        print(f"{'='*50}")

    return 0 if err_count == 0 else 1


# =============================================================================
# Subcomando: conferir
# =============================================================================

def _achar_simbolo_irmao(caminho_footprint):
    """.kicad_sym de mesmo nome, ao lado do .kicad_mod."""
    irmao = os.path.splitext(caminho_footprint)[0] + '.kicad_sym'
    return irmao if os.path.isfile(irmao) else None


def cmd_conferir(args):
    """Confere um .kicad_mod: colisão entre pads, gabarito e símbolo."""
    from conferir_footprint import conferir

    simbolo = args.simbolo
    auto = False
    if not simbolo and not args.sem_simbolo:
        simbolo = _achar_simbolo_irmao(args.footprint)
        auto = simbolo is not None

    try:
        ok, rel = conferir(args.footprint, gabarito=args.gabarito,
                           folga_min=args.folga_min, simbolo=simbolo)
    except (FileNotFoundError, OSError) as e:
        if args.json:
            print(json.dumps({"ok": False, "erros": [str(e)]},
                             ensure_ascii=False, indent=2))
        else:
            print(f"❌ {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": ok, "simbolo_auto": auto, **rel},
                         ensure_ascii=False, indent=2))
        return 0 if ok else 1

    print(f"{rel['footprint']}: {rel['pads']} pads")

    col = rel['colisoes']
    if col:
        print(f"  ❌ {len(col)} par(es) de pads se sobrepõem (cobre em curto):")
        for c in col[:8]:
            print(f"       {c['pads'][0]}+{c['pads'][1]}  {c['sobreposicao_mm']}mm")
        if len(col) > 8:
            print(f"       ... e mais {len(col) - 8}")
    else:
        print("  ✅ sem sobreposição entre pads")

    g = rel.get('gabarito')
    if g:
        print(f"\nvs gabarito ({g['nome']}):")
        print(f"  pads: {g['total_meu']} gerado / {g['total_ref']} gabarito")
        if g['faltando']:
            print(f"  ❌ faltando no gerado: {g['faltando'][:12]}")
        if g['sobrando']:
            print(f"  ❌ sobrando no gerado: {g['sobrando'][:12]}")
        if g['tamanhos_diferentes']:
            print(f"  ❌ tamanho diferente em: {g['tamanhos_diferentes'][:12]}")

        if g['offset_de_origem']:
            dx, dy = g['offset_de_origem']
            print(f"  ⚠️  os {g['divergentes']} pads divergem pelo MESMO deslocamento "
                  f"({dx:+g}, {dy:+g}) mm")
            print("      Isso é offset de ORIGEM, não erro de geometria: as posições")
            print("      relativas batem. Reancore a origem (ou aceite, se intencional).")
        elif g['divergentes']:
            print(f"  ❌ geometria: {g['iguais']}/{g['total_ref']} idênticos "
                  f"| divergentes: {g['divergentes']}")
            for d in g['detalhes'][:8]:
                print(f"       pad {d['pad']}: gabarito={d['gabarito']}  gerado={d['gerado']}")
        else:
            print(f"  ✅ geometria: {g['iguais']}/{g['total_ref']} pads idênticos")

    s = rel.get('simbolo')
    if s:
        origem = " (encontrado ao lado do footprint)" if auto else ""
        print(f"\nvs símbolo ({s['arquivo']}){origem}:")
        print(f"  pinos: {s['pinos']} símbolo / {s['pads_numerados']} pads "
              f"numerados | casados: {s['casados']}")

        if s['numeracao_incompativel']:
            print("  ❌ NENHUM pino casa: símbolo e footprint usam numerações de")
            print("      universos diferentes. Nenhuma ligação desse componente")
            print("      chega ao cobre — o par simbolo+footprint é inutilizável.")

        if s['pinos_sem_pad']:
            print(f"  ❌ pino sem pad: {s['pinos_sem_pad'][:12]}")
            print("      O netlist dá net a esses pinos e não há cobre para levá-los.")
            for d in s['detalhes_pinos_sem_pad'][:8]:
                print(f"       pino {d['numero']} ({d['nome']})")
        if s['pads_sem_pino']:
            print(f"  ⚠️  pad sem pino: {s['pads_sem_pino'][:12]}")
            print("      Cobre que nenhum net alcança (é o caso do EP/aba térmica).")
            print("      Não reprova: a placa fabrica.")
        if not s['pinos_sem_pad'] and not s['pads_sem_pino']:
            print("  ✅ todo pino tem pad e todo pad numerado tem pino")
    elif not args.sem_simbolo:
        print("\nsem símbolo conferido: não há .kicad_sym ao lado do footprint")
        print("  (use --simbolo para apontar um, ou --sem-simbolo para calar isto)")

    print()
    print("  OK" if ok else "  FALHOU")
    return 0 if ok else 1


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
    p_gerar.add_argument('--dry-run', action='store_true',
                         help='Validar e listar arquivos que seriam gerados, sem escrever')
    p_gerar.set_defaults(func=cmd_gerar)

    # validar
    p_validar = sub.add_parser('validar', help='Validar YAML (Schema + IPC + DRC)')
    p_validar.add_argument('yaml', help='Arquivo YAML do componente')
    p_validar.add_argument('--footprint',
                           help='.kicad_mod já gerado deste YAML: roda o DRC '
                                'sobre a geometria real e confere o modelo 3D')
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
    p_batch.add_argument('--dry-run', action='store_true',
                         help='Validar e listar o que seria gerado, sem escrever')
    p_batch.set_defaults(func=cmd_batch)

    # conferir
    p_conf = sub.add_parser(
        'conferir',
        help='Conferir um .kicad_mod (colisão de pads + gabarito opcional)')
    p_conf.add_argument('footprint', help='Arquivo .kicad_mod gerado')
    p_conf.add_argument('--gabarito',
                        help='.kicad_mod de referência (oficial do fabricante) '
                             'para comparar pad a pad')
    p_conf.add_argument('--folga-min', type=float, default=0.0,
                        dest='folga_min',
                        help='Folga mínima entre pads em mm (default 0 = só '
                             'acusa sobreposição real)')
    p_conf.add_argument('--simbolo',
                        help='.kicad_sym do mesmo componente, para conferir os '
                             'números de pino contra os pads. Se omitido, usa o '
                             '.kicad_sym de mesmo nome ao lado do footprint')
    p_conf.add_argument('--sem-simbolo', action='store_true', dest='sem_simbolo',
                        help='Não procurar o .kicad_sym irmão')
    p_conf.set_defaults(func=cmd_conferir)

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
