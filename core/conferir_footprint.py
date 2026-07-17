# =============================================================================
# conferir_footprint.py
# Confere um .kicad_mod: colisão entre pads e, se houver gabarito, comparação
# pad a pad contra ele.
#
# Por que existe: "gerou sem erro" não quer dizer "está certo". Nesta base já
# aconteceu de três verificadores (validar IPC+schema, gerar, e um script de
# comparação) darem "ok" para um footprint cujos pads laterais estavam em
# curto. Quem pegou foi a checagem de colisão.
#
# Compara GEOMETRIA, não texto: um pad 1,15x0,70 girado 90° tem o mesmo
# sizeX/sizeY de um não girado e ocupa cobre TRANSPOSTO. Comparar (x,y,w,h)
# sem olhar a rotação dá falso positivo — foi exatamente o que aconteceu.
#
# Não depende do pcbnew: lê o .kicad_mod pelo sexpr_parser.
# =============================================================================

import os

from sexpr_parser import parse_sexpr, find_all, find_one, get_at, get_size


def ler_pads(caminho):
    """Lê os pads de um .kicad_mod → {numero: (x, y, w, h)}.

    w/h já vêm com a rotação aplicada (a extensão real do cobre em X/Y), para
    que a comparação seja geométrica.
    """
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"footprint não encontrado: {caminho}")
    with open(caminho, 'r', encoding='utf-8') as f:
        sexpr = parse_sexpr(f.read())

    pads = {}
    for pad in find_all(sexpr, 'pad'):
        numero = str(pad[1]) if len(pad) > 1 else '?'
        x, y, ang = get_at(pad)
        w, h = get_size(pad)
        if round(ang) % 180 == 90:
            w, h = h, w          # girado: o cobre ocupa transposto
        pads[numero] = (round(x, 3), round(y, 3), round(w, 3), round(h, 3))
    return pads


def nome_footprint(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        sexpr = parse_sexpr(f.read())
    return str(sexpr[1]) if len(sexpr) > 1 else os.path.basename(caminho)


def colisoes(pads, folga_min=0.0):
    """Pares de pads cujo cobre se sobrepõe → (num_a, num_b, sobreposicao_mm).

    Pads com o MESMO número são o mesmo net (um pino com dois pads): tocar ali
    é intencional, não curto.
    """
    itens = list(pads.items())
    out = []
    for i in range(len(itens)):
        for j in range(i + 1, len(itens)):
            (na, a), (nb, b) = itens[i], itens[j]
            if na == nb:
                continue
            ox = (a[2] + b[2]) / 2 - abs(a[0] - b[0])
            oy = (a[3] + b[3]) / 2 - abs(a[1] - b[1])
            folga = max(-ox, -oy)          # separados se QUALQUER eixo separar
            if folga < folga_min:
                out.append((na, nb, round(-folga, 4)))
    return out


def comparar(pads_meu, pads_ref):
    """Compara dois conjuntos de pads.

    Retorna um dict com o veredito. Trata à parte o caso em que TODOS os pads
    divergem pelo MESMO deslocamento: isso é offset de ORIGEM, não erro de
    geometria — as posições relativas batem. Reportar como 71 erros esconderia
    o fato de que só falta reancorar a origem.
    """
    faltando = sorted(set(pads_ref) - set(pads_meu), key=_ordem)
    sobrando = sorted(set(pads_meu) - set(pads_ref), key=_ordem)
    comuns = [n for n in pads_ref if n in pads_meu]

    tam_dif = [n for n in comuns if pads_meu[n][2:] != pads_ref[n][2:]]
    deslocs = {(round(pads_meu[n][0] - pads_ref[n][0], 3),
                round(pads_meu[n][1] - pads_ref[n][1], 3)) for n in comuns}
    iguais = [n for n in comuns if pads_meu[n] == pads_ref[n]]

    offset = None
    if comuns and not tam_dif and len(deslocs) == 1:
        d = next(iter(deslocs))
        if d != (0.0, 0.0):
            offset = d

    return {
        'total_ref': len(pads_ref), 'total_meu': len(pads_meu),
        'iguais': len(iguais), 'divergentes': len(comuns) - len(iguais),
        'faltando': faltando, 'sobrando': sobrando,
        'tamanhos_diferentes': sorted(tam_dif, key=_ordem),
        'offset_de_origem': offset,
        'detalhes': [{'pad': n, 'gabarito': pads_ref[n], 'gerado': pads_meu[n]}
                     for n in comuns if pads_meu[n] != pads_ref[n]][:20],
    }


def _ordem(n):
    return (0, int(n)) if str(n).isdigit() else (1, str(n))


def conferir(caminho, gabarito=None, folga_min=0.0):
    """Confere um footprint. Retorna (ok, relatorio)."""
    pads = ler_pads(caminho)
    rel = {
        'footprint': nome_footprint(caminho),
        'pads': len(pads),
        'colisoes': [{'pads': [a, b], 'sobreposicao_mm': s}
                     for a, b, s in colisoes(pads, folga_min)],
    }
    ok = not rel['colisoes']

    if gabarito:
        ref = ler_pads(gabarito)
        cmp_ = comparar(pads, ref)
        rel['gabarito'] = {'arquivo': os.path.basename(gabarito),
                           'nome': nome_footprint(gabarito), **cmp_}
        # Offset de origem não é erro de geometria — as relativas batem.
        ok = ok and not cmp_['faltando'] and not cmp_['sobrando'] \
            and not cmp_['tamanhos_diferentes'] \
            and (cmp_['divergentes'] == 0 or cmp_['offset_de_origem'] is not None)

    return ok, rel
