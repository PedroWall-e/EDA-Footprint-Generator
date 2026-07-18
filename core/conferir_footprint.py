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
# Confere também SÍMBOLO x FOOTPRINT: o mesmo YAML gera .kicad_mod e .kicad_sym,
# e o KiCad casa pino<->pad PELO NÚMERO. Divergindo, o erro só aparece lá na
# frente, no netlist, longe daqui. Compara só os NÚMEROS: posição do pino no
# esquemático e posição do pad no cobre não têm relação nenhuma entre si.
#
# Não depende do pcbnew: lê .kicad_mod e .kicad_sym pelo sexpr_parser.
# =============================================================================

import os

from sexpr_parser import parse_sexpr, find_all, find_one, get_at, get_size

# Pad sem número ('') ou sem token de número ('?'): furo mecânico NPTH e
# sub-pad de exposed pad. Não têm pino por construção — nunca são erro.
_SEM_NUMERO = ('', '?')


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


def ler_pinos(caminho):
    """Lê os pinos de um .kicad_sym → {numero: nome}.

    Varre o arquivo inteiro: as unidades do símbolo ('_0_1' gráfica, '_1_1' com
    os pinos) são sub-símbolos aninhados, e os pinos vivem só na segunda.

    O número vem COM aspas no .kicad_sym ((number "1" ...)) e SEM aspas no
    .kicad_mod ((pad 1 ...)); o parser tira as aspas, então os dois chegam aqui
    como str e comparam direto.
    """
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"símbolo não encontrado: {caminho}")
    with open(caminho, 'r', encoding='utf-8') as f:
        sexpr = parse_sexpr(f.read())

    pinos = {}
    for pin in find_all(sexpr, 'pin'):
        numero = find_one(pin, 'number')
        nome = find_one(pin, 'name')
        chave = str(numero[1]) if numero and len(numero) > 1 else '?'
        pinos[chave] = str(nome[1]) if nome and len(nome) > 1 else ''
    return pinos


def nome_footprint(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        sexpr = parse_sexpr(f.read())
    return str(sexpr[1]) if len(sexpr) > 1 else os.path.basename(caminho)


def nome_simbolo(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        sexpr = parse_sexpr(f.read())
    sym = find_one(sexpr, 'symbol')
    return str(sym[1]) if sym and len(sym) > 1 else os.path.basename(caminho)


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


def conferir_simbolo(caminho_mod, caminho_sym):
    """Confere os números de pino do símbolo contra os pads do footprint.

    As duas direções da divergência NÃO são o mesmo erro:

    - pino sem pad: o netlist atribui um net ao pino e não existe cobre para
      levá-lo. A ligação some calada. É ERRO e derruba o veredito.
    - pad sem pino: existe cobre que nenhum net alcança. É o pad térmico EP dos
      QFN e a aba do SOT223, que legitimamente não têm pino. Fica em AVISO.

    Classifica por DIREÇÃO, não por nome: uma lista de nomes conhecidos ('EP',
    'PAD', 'TAB') engoliria calada um pad numerado que o símbolo esqueceu.
    """
    pads = ler_pads(caminho_mod)
    pinos = ler_pinos(caminho_sym)

    nums_pad = {n for n in pads if n not in _SEM_NUMERO}
    nums_pin = {n for n in pinos if n not in _SEM_NUMERO}

    pinos_sem_pad = sorted(nums_pin - nums_pad, key=_ordem)
    pads_sem_pino = sorted(nums_pad - nums_pin, key=_ordem)
    casados = sorted(nums_pad & nums_pin, key=_ordem)

    return {
        'simbolo': nome_simbolo(caminho_sym),
        'arquivo': os.path.basename(caminho_sym),
        'pinos': len(nums_pin),
        'pads_numerados': len(nums_pad),
        'casados': len(casados),
        'pinos_sem_pad': pinos_sem_pad,
        'pads_sem_pino': pads_sem_pino,
        # Nada casou: as duas numerações são de universos diferentes (símbolo
        # B/E/C x footprint 1/2/3). Reportar "3 erros + 3 avisos" esconderia
        # que nenhum pino desse componente vai casar, nunca.
        'numeracao_incompativel': bool(nums_pad and nums_pin and not casados),
        # ler_pads indexa por número, então os sem número colapsam numa chave
        # só: dá para saber que existem, não quantos são.
        'pads_sem_numero': any(n in _SEM_NUMERO for n in pads),
        'detalhes_pinos_sem_pad': [{'numero': n, 'nome': pinos[n]}
                                   for n in pinos_sem_pad][:20],
    }


def _ordem(n):
    return (0, int(n)) if str(n).isdigit() else (1, str(n))


def conferir(caminho, gabarito=None, folga_min=0.0, simbolo=None):
    """Confere um footprint. Retorna (ok, relatorio).

    'simbolo' é o .kicad_sym gerado do mesmo YAML; sem ele a conferência
    cruzada não roda e o veredito é o de sempre.
    """
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

    if simbolo:
        sym = conferir_simbolo(caminho, simbolo)
        rel['simbolo'] = sym
        # Só pino sem pad derruba o veredito: pad sem pino é aviso (EP/aba).
        ok = ok and not sym['pinos_sem_pad']

    return ok, rel
