# =============================================================================
# footprint_helpers.py
# Helpers compartilhados para geração de footprints KiCad (.kicad_mod)
#
# Funções utilitárias reutilizáveis que eliminam duplicação de código
# entre os geradores de footprint (v1 e v2).
#
# Autor: Gerador Automático de Footprints
# Compatibilidade: KiCad 6.x / 7.x / 8.x
# =============================================================================

import math
import re
import logging

try:
    from KicadModTree import (
        Footprint,
        Text,
        Line,
        Arc,
        Circle,
        Pad,
        Model,
        KicadFileHandler,
    )
except ImportError:
    from KicadModTree import (
        Footprint,
        Text,
        Line,
        Pad,
        Model,
        KicadFileHandler,
    )
    Arc = None
    Circle = None

log = logging.getLogger(__name__)


# =============================================================================
# Drawing helpers — camadas de desenho (courtyard, silkscreen, fab)
# =============================================================================

def draw_courtyard(kicad_mod, x1, y1, x2, y2, margin=0.5, line_width=0.05):
    """Desenha retângulo de courtyard com margem ao redor da área (x1,y1)-(x2,y2).

    Produz 4 linhas na camada F.CrtYd com a margem aplicada:
      - top:    (x1-m, y1-m) → (x2+m, y1-m)
      - bottom: (x1-m, y2+m) → (x2+m, y2+m)
      - left:   (x1-m, y1-m) → (x1-m, y2+m)
      - right:  (x2+m, y1-m) → (x2+m, y2+m)

    Padrão courtyard width = 0.05 mm conforme IPC.
    """
    cx1 = x1 - margin
    cy1 = y1 - margin
    cx2 = x2 + margin
    cy2 = y2 + margin

    # Top
    kicad_mod.append(Line(start=[cx1, cy1], end=[cx2, cy1],
                          layer='F.CrtYd', width=line_width))
    # Bottom
    kicad_mod.append(Line(start=[cx1, cy2], end=[cx2, cy2],
                          layer='F.CrtYd', width=line_width))
    # Left
    kicad_mod.append(Line(start=[cx1, cy1], end=[cx1, cy2],
                          layer='F.CrtYd', width=line_width))
    # Right
    kicad_mod.append(Line(start=[cx2, cy1], end=[cx2, cy2],
                          layer='F.CrtYd', width=line_width))


def draw_courtyard_raw(kicad_mod, cx1, cy1, cx2, cy2, line_width=0.05):
    """Desenha retângulo de courtyard com coordenadas já calculadas (sem margem).

    Útil quando o chamador já calculou as coordenadas do courtyard
    considerando pads + margem.
    """
    kicad_mod.append(Line(start=[cx1, cy1], end=[cx2, cy1],
                          layer='F.CrtYd', width=line_width))
    kicad_mod.append(Line(start=[cx1, cy2], end=[cx2, cy2],
                          layer='F.CrtYd', width=line_width))
    kicad_mod.append(Line(start=[cx1, cy1], end=[cx1, cy2],
                          layer='F.CrtYd', width=line_width))
    kicad_mod.append(Line(start=[cx2, cy1], end=[cx2, cy2],
                          layer='F.CrtYd', width=line_width))


def draw_silkscreen_rect(kicad_mod, x1, y1, x2, y2, line_width=0.12):
    """Desenha retângulo na camada F.SilkS.

    Replica o padrão do motor v1 (removido; ver CHANGELOG):
      4 linhas: top, bottom, left, right.
    """
    # Top
    kicad_mod.append(Line(start=[x1, y1], end=[x2, y1],
                          layer='F.SilkS', width=line_width))
    # Bottom
    kicad_mod.append(Line(start=[x1, y2], end=[x2, y2],
                          layer='F.SilkS', width=line_width))
    # Left
    kicad_mod.append(Line(start=[x1, y1], end=[x1, y2],
                          layer='F.SilkS', width=line_width))
    # Right
    kicad_mod.append(Line(start=[x2, y1], end=[x2, y2],
                          layer='F.SilkS', width=line_width))


def draw_fab_rect(kicad_mod, x1, y1, x2, y2, line_width=0.10):
    """Desenha retângulo na camada F.Fab.

    Replica o padrão do motor v1 (removido; ver CHANGELOG):
      4 linhas: top, bottom, left, right.
    """
    # Top
    kicad_mod.append(Line(start=[x1, y1], end=[x2, y1],
                          layer='F.Fab', width=line_width))
    # Bottom
    kicad_mod.append(Line(start=[x1, y2], end=[x2, y2],
                          layer='F.Fab', width=line_width))
    # Left
    kicad_mod.append(Line(start=[x1, y1], end=[x1, y2],
                          layer='F.Fab', width=line_width))
    # Right
    kicad_mod.append(Line(start=[x2, y1], end=[x2, y2],
                          layer='F.Fab', width=line_width))


def draw_circle_segments(kicad_mod, cx, cy, r, layer, line_width, n_segs=16):
    """Desenha um círculo aproximado por n_segs segmentos de Line.

    Replica _circulo_silkscreen() do motor v1 (removido).
    Usado para corpos cilíndricos (LED, capacitor, TO-92 etc.).
    """
    for i in range(n_segs):
        a0 = 2 * math.pi * i / n_segs
        a1 = 2 * math.pi * (i + 1) / n_segs
        kicad_mod.append(Line(
            start=[cx + r * math.cos(a0), cy + r * math.sin(a0)],
            end=[cx + r * math.cos(a1), cy + r * math.sin(a1)],
            layer=layer, width=line_width,
        ))


def draw_dshape(kicad_mod, r, layer, line_width, n_segs=10):
    """Desenha forma D-shape (TO-92): reta em y=-r, semicírculo em y>=0.

    Replica _dshape() do gerar_footprint_transistor_to92().
    """
    # Linha reta (lado plano) em y = -r
    kicad_mod.append(Line(
        start=[-r, -r], end=[r, -r],
        layer=layer, width=line_width,
    ))
    # Semicírculo do ângulo pi a 2*pi
    for i in range(n_segs):
        a0 = math.pi + math.pi * i / n_segs
        a1 = math.pi + math.pi * (i + 1) / n_segs
        kicad_mod.append(Line(
            start=[r * math.cos(a0), r * math.sin(a0)],
            end=[r * math.cos(a1), r * math.sin(a1)],
            layer=layer, width=line_width,
        ))


def draw_pin1_marker(kicad_mod, x, y, style='dot', layer='F.SilkS',
                     size=0.3, line_width=0.12):
    """Marca o pino 1 no footprint.

    Estilos disponíveis (replicam padrões do motor v1, removido):

    'dot'      — Duas linhas em L (usado em castellated/conector).
    'chamfer'  — Linha diagonal no canto (usado em DIP/SOIC).
    'arrow'    — Linha vertical simples (usado em conector header).
    'triangle' — Triângulo apontando para o pino 1.

    Parâmetros:
        x, y     : posição de referência do marcador
        size     : dimensão do marcador (raio/comprimento)
        layer    : camada (padrão F.SilkS)
        line_width: espessura da linha
    """
    if style == 'dot':
        # Duas linhas em L — padrão castellated (linhas 126-129)
        kicad_mod.append(Line(
            start=[x - size, y - size], end=[x - size, y + size],
            layer=layer, width=line_width,
        ))
        kicad_mod.append(Line(
            start=[x - size, y - size], end=[x, y - size],
            layer=layer, width=line_width,
        ))

    elif style == 'chamfer':
        # Linha diagonal: canto superior-esquerdo (DIP/SOIC)
        # x, y = canto do corpo; size = raio do arco
        kicad_mod.append(Line(
            start=[x, y + size], end=[x + size, y],
            layer=layer, width=line_width,
        ))

    elif style == 'arrow':
        # Linha vertical simples (conector header)
        kicad_mod.append(Line(
            start=[x, y - size], end=[x, y + size],
            layer=layer, width=line_width,
        ))

    elif style == 'triangle':
        # Triângulo equilátero apontando para a direita
        h = size * math.sqrt(3) / 2
        kicad_mod.append(Line(
            start=[x, y - size / 2], end=[x, y + size / 2],
            layer=layer, width=line_width,
        ))
        kicad_mod.append(Line(
            start=[x, y - size / 2], end=[x + h, y],
            layer=layer, width=line_width,
        ))
        kicad_mod.append(Line(
            start=[x, y + size / 2], end=[x + h, y],
            layer=layer, width=line_width,
        ))

    else:
        log.warning(f"Estilo de marcador de pino 1 desconhecido: '{style}'")


# =============================================================================
# Text helpers — referência e valor
# =============================================================================

def add_reference_text(kicad_mod, nome, x, y, size=1.0, offset=1.5,
                       layer='F.SilkS', thickness=0.12):
    """Adiciona texto de referência (REF**).

    Replica o padrão do motor v1 (removido; ver CHANGELOG):
        Text(type=Text.TYPE_REFERENCE, text='REF**',
             at=[x, y - offset], layer='F.SilkS',
             size=[size, size], thickness=thickness)

    Parâmetros:
        x, y      : centro do footprint (texto é colocado em [x, y - offset])
        size      : tamanho da fonte (padrão 1.0)
        offset    : deslocamento Y acima do corpo (padrão 1.5)
        layer     : camada (padrão F.SilkS)
        thickness : espessura do traço (padrão 0.12)
    """
    kicad_mod.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[x, y - offset],
        layer=layer, size=[size, size], thickness=thickness,
    ))


def add_value_text(kicad_mod, nome, x, y, size=1.0, offset=1.5,
                   layer='F.Fab', thickness=0.10):
    """Adiciona texto de valor.

    Replica o padrão do motor v1 (removido; ver CHANGELOG):
        Text(type=Text.TYPE_VALUE, text=nome,
             at=[x, y + offset], layer='F.Fab',
             size=[size, size], thickness=thickness)

    Parâmetros:
        x, y      : centro do footprint (texto é colocado em [x, y + offset])
        nome      : valor do texto (nome do componente)
        size      : tamanho da fonte (padrão 1.0)
        offset    : deslocamento Y abaixo do corpo (padrão 1.5)
        layer     : camada (padrão F.Fab)
        thickness : espessura do traço (padrão 0.10)
    """
    kicad_mod.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[x, y + offset],
        layer=layer, size=[size, size], thickness=thickness,
    ))


def add_3d_model(kicad_mod, nome_modelo, path_prefix='${KIPRJMOD}/', dados=None,
                 nome_padrao=None):
    """Adiciona referência ao modelo 3D STEP.

    Resolução do NOME:
      - nome_modelo=None (campo `kicad.modelo_3d` omitido no YAML) → usa
        f"{nome_padrao}.step", que é exatamente o arquivo que o cli.py gera.
        Sem isso o .step nasce ÓRFÃO: existe em disco, mas o footprint não o
        referencia e o KiCad não mostra 3D nenhum — falha silenciosa.
      - nome_modelo='' (vazio explícito) → não referencia nada. É a saída para
        quem realmente não quer modelo 3D.

    Resolução do CAMINHO (prioridade):
      1. Se nome_modelo já contém '/' ou '$' → caminho completo
      2. Se dados['kicad']['modelo_3d_path'] existe → usa como prefixo
      3. Caso contrário → usa path_prefix (default: '${KIPRJMOD}/')

    Atenção ao default '${KIPRJMOD}/': aponta para a pasta do PROJETO, o que
    não serve para biblioteca compartilhada (o .step não mora junto do
    .kicad_pro). Nesse caso use uma variável do KiCad, ex.:
    modelo_3d: "${MINHA_LIB_3DSHAPES}/Peca.step"
    """
    if nome_modelo is None:
        if not nome_padrao:
            return
        nome_modelo = f"{nome_padrao}.step"
    if not nome_modelo:
        return

    if '/' in nome_modelo or '$' in nome_modelo:
        filename = nome_modelo
    else:
        # Resolver prefixo do YAML se disponível
        prefix = path_prefix
        if isinstance(dados, dict):
            # `kicad:` pode existir vazio no YAML — nesse caso vira None, não {}
            kicad = dados.get('kicad')
            yaml_path = kicad.get('modelo_3d_path', '') if isinstance(kicad, dict) else ''
            if yaml_path:
                prefix = yaml_path
        # Garantir que termina com /
        if not prefix.endswith('/'):
            prefix += '/'
        filename = prefix + nome_modelo

    kicad_mod.append(Model(
        filename=filename,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))


# =============================================================================
# Pad helpers — pads THT, SMD, thermal
# =============================================================================

def build_override_map(dados, pad_w_def, pad_h_def):
    """Normaliza `pinos.overrides` para {identificador_do_pino: (largura, altura)}.

    A chave é **string** porque no KiCad o número do pad é textual: "1" num DIP,
    "A1" num BGA. Chavear por int excluiria os padrões de grade (BGA) do
    mecanismo. Consulte sempre com `str(num)`.

    O schema (schemas/component.schema.json) declara `overrides` como `oneOf`,
    ou seja, AMBAS as formas abaixo são válidas e precisam funcionar:

      dict  — override por pino:
          overrides:
            "1": {largura: 1.2, altura: 0.8}

      lista — override por grupo de pinos (ergonômico para castellated, onde
              dezenas de pinos compartilham o mesmo tamanho):
          overrides:
            - numeros: [1, 9, 16]
              largura: 2.5
              altura: 1.2

    Campos ausentes caem no default do padrão (pad_w_def / pad_h_def).
    Entradas malformadas são ignoradas em vez de derrubar a geração.
    """
    override_map = {}
    pinos = dados.get('pinos') if isinstance(dados, dict) else None
    overrides = pinos.get('overrides') if isinstance(pinos, dict) else None
    if not overrides:
        return override_map

    def _wh(ov):
        return (float(ov.get('largura', pad_w_def)),
                float(ov.get('altura', pad_h_def)))

    if isinstance(overrides, dict):
        for chave, ov in overrides.items():
            if not isinstance(ov, dict):
                continue
            try:
                override_map[str(chave)] = _wh(ov)
            except (TypeError, ValueError):
                continue

    elif isinstance(overrides, list):
        for ov in overrides:
            if not isinstance(ov, dict):
                continue
            try:
                w, h = _wh(ov)
            except (TypeError, ValueError):
                continue
            for n in (ov.get('numeros') or []):
                # O schema tipa `numeros` como array de inteiros — validar aqui
                # descarta lixo. (A forma dict, ao contrário, aceita chave
                # textual de propósito: é como o BGA endereça "A1".)
                try:
                    override_map[str(int(n))] = (w, h)
                except (TypeError, ValueError):
                    continue

    return override_map


def read_paste_ratio(thermal, default=0.5):
    """Lê o ratio de pasta do bloco `thermal_pad`, aceitando as duas grafias.

    O schema declara `pasta_ratio` como **sinônimo** de `paste_ratio`, e o
    `_template.yaml` ensina justamente a grafia `pasta_ratio`. Ler só uma
    fazia a outra ser descartada em silêncio: o YAML era aceito, o footprint
    gerava, e a abertura de pasta saía no default.

    `paste_ratio` tem precedência quando ambas aparecem.
    """
    if not isinstance(thermal, dict):
        return default
    for chave in ('paste_ratio', 'pasta_ratio'):
        if chave in thermal:
            try:
                return float(thermal[chave])
            except (TypeError, ValueError):
                return default
    return default


def add_pth_pad(kicad_mod, number, x, y, pad_diam, drill_diam,
                shape=None, size=None):
    """Adiciona pad through-hole.

        Pad(number=N, type=Pad.TYPE_THT, shape=<shape>,
            at=[x, y], size=[w, h], drill=drill_diam,
            layers=['*.Cu', '*.Mask'])

    shape padrão: Pad.SHAPE_CIRCLE (use Pad.SHAPE_RECT para pino 1).

    size: (w, h) opcional — vem de `pinos.overrides` e sobrepõe pad_diam.
          Um pad PTH redondo é só o caso w == h; com w != h o KiCad exige
          SHAPE_OVAL (SHAPE_CIRCLE com lados diferentes é inválido), então a
          troca é feita aqui. O anel é validado contra o MENOR lado, que é
          onde ele é mais estreito.
    """
    w, h = (float(size[0]), float(size[1])) if size else (pad_diam, pad_diam)

    if shape is None:
        shape = Pad.SHAPE_CIRCLE if w == h else Pad.SHAPE_OVAL
    elif shape == Pad.SHAPE_CIRCLE and w != h:
        shape = Pad.SHAPE_OVAL

    validate_annular_ring(min(w, h), drill_diam)

    kicad_mod.append(Pad(
        number=number,
        type=Pad.TYPE_THT,
        shape=shape,
        at=[x, y],
        size=[w, h],
        drill=drill_diam,
        layers=['*.Cu', '*.Mask'],
    ))


def add_smd_pad(kicad_mod, number, x, y, width, height,
                shape=None, roundrect_ratio=0.25,
                layers=None):
    """Adiciona pad SMD.

    Replica o padrão do motor v1 (removido; ver CHANGELOG):
        Pad(number=N, type=Pad.TYPE_SMT, shape=<shape>,
            at=[x, y], size=[width, height],
            layers=['F.Cu', 'F.Paste', 'F.Mask'])

    shape padrão: Pad.SHAPE_RECT (compatível com v1).
    Para SHAPE_ROUNDRECT, usa roundrect_ratio.
    """
    if shape is None:
        shape = Pad.SHAPE_RECT
    if layers is None:
        layers = ['F.Cu', 'F.Paste', 'F.Mask']

    kwargs = dict(
        number=number,
        type=Pad.TYPE_SMT,
        shape=shape,
        at=[x, y],
        size=[width, height],
        layers=layers,
    )

    # roundrect_ratio só é relevante para SHAPE_ROUNDRECT
    if shape == Pad.SHAPE_ROUNDRECT:
        kwargs['roundrect_rratio'] = roundrect_ratio

    kicad_mod.append(Pad(**kwargs))


def add_thermal_pad(kicad_mod, x, y, width, height, paste_ratio=0.5):
    """Adiciona thermal/exposed pad central.

    Pad SMD sem paste (ou com paste reduzido) usado para dissipação
    térmica em QFN/TQFP. O paste_ratio controla a cobertura de pasta
    de solda (0 = sem pasta, 1 = cobertura total).
    """
    layers = ['F.Cu', 'F.Mask']
    if paste_ratio > 0:
        layers.append('F.Paste')

    kwargs = dict(
        number='EP',
        type=Pad.TYPE_SMT,
        shape=Pad.SHAPE_RECT,
        at=[x, y],
        size=[width, height],
        layers=layers,
    )

    # Se paste_ratio < 1.0, reduzir o tamanho da abertura de pasta
    if 0 < paste_ratio < 1.0:
        kwargs['solder_paste_margin_ratio'] = -(1.0 - paste_ratio)

    kicad_mod.append(Pad(**kwargs))


# =============================================================================
# Validation — regras IPC
# =============================================================================

def validate_annular_ring(pad_diam, drill_diam, min_ring=0.15):
    """Valida anel de cobre mínimo (IPC Class 2).

    Retorna True se o anel >= min_ring.
    Emite warning no log se violado.
    """
    ring = (pad_diam - drill_diam) / 2
    if ring < min_ring:
        log.warning(
            f'Annular ring {ring:.2f}mm < minimum {min_ring}mm '
            f'(pad={pad_diam}mm, drill={drill_diam}mm)'
        )
    return ring >= min_ring


def validate_pad_clearance(pads_positions, min_clearance=0.2):
    """Valida espaçamento mínimo entre pads (compatibilidade).

    pads_positions: lista de (x, y, largura, altura)
    Retorna True se todos os pares satisfazem o espaçamento mínimo.

    Prefira `check_pad_collisions`, que distingue sobreposição (erro) de folga
    curta (aviso) e identifica os pads pelo número.
    """
    pads = [(i + 1, *p) for i, p in enumerate(pads_positions)]
    sobrepostos, curtos = pad_clearance_report(pads, min_clearance)
    for a, b, gap in sobrepostos + curtos:
        log.warning('Pad clearance %.2fmm < minimo %.2fmm entre pads %s e %s',
                    gap, min_clearance, a, b)
    return not (sobrepostos or curtos)


def pad_clearance_report(pads, min_clearance=0.2):
    """Mede a folga entre todos os pares de pads.

    pads: lista de (numero, x, y, largura, altura)
    Retorna (sobrepostos, curtos), cada um lista de (num_a, num_b, folga_mm):
      - sobrepostos: folga < 0  -> o cobre se toca. Curto: erro.
      - curtos:      0 <= folga < min_clearance -> fabricável no limite: aviso.

    Dois retângulos estão separados se QUALQUER eixo os separar, por isso a
    folga é o max(dx, dy). Pads com o MESMO número são o mesmo net (ex.: um
    pino com dois pads) e são ignorados — tocar ali é intencional.
    """
    sobrepostos, curtos = [], []
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            na, xi, yi, wi, hi = pads[i]
            nb, xj, yj, wj, hj = pads[j]
            if str(na) == str(nb):
                continue
            dx = abs(xi - xj) - (wi + wj) / 2
            dy = abs(yi - yj) - (hi + hj) / 2
            gap = max(dx, dy)
            if gap < 0:
                sobrepostos.append((na, nb, round(gap, 4)))
            elif gap < min_clearance:
                curtos.append((na, nb, round(gap, 4)))
    return sobrepostos, curtos


def check_pad_collisions(pads, nome, min_clearance=0.2):
    """Aborta se houver pads sobrepostos; avisa se a folga for curta.

    Chamado pelos padrões que posicionam pads. Sobreposição vira ValueError
    porque o footprint sairia com pads em curto — e "gerou sem erro" nao pode
    significar "está certo". Folga curta é só aviso: pode ser deliberado.
    """
    sobrepostos, curtos = pad_clearance_report(pads, min_clearance)

    for a, b, gap in curtos:
        log.warning("%s: folga de %.3fmm entre os pads %s e %s (< %.2fmm)",
                    nome, gap, a, b, min_clearance)

    if sobrepostos:
        det = ', '.join(f'{a}+{b} ({-gap:.3f}mm)' for a, b, gap in sobrepostos[:6])
        mais = f' e mais {len(sobrepostos) - 6}' if len(sobrepostos) > 6 else ''
        raise ValueError(
            f"'{nome}': {len(sobrepostos)} par(es) de pads se sobrepoem — "
            f"o cobre se toca e os pinos sairiam em curto: {det}{mais}. "
            f"Corrija as posicoes/tamanhos no YAML."
        )
    return True


# =============================================================================
# Post-processing — conversão para formato KiCad v6+
# =============================================================================

def postprocess_v6(content, attr='through_hole'):
    """Converte saída KicadModTree v5 para formato v6+.

    Transformações:
    - (module ...) → (footprint ...)
    - Adiciona (version 20231120) após o nome do módulo
    - Adiciona (attr through_hole|smd) antes do primeiro elemento

    Parâmetros:
        content : string com o conteúdo do .kicad_mod (formato v5)
        attr    : 'through_hole' ou 'smd'

    Retorna:
        String convertida para formato v6+.
    """
    # 1. (module ...) → (footprint ...)
    result = content.replace('(module ', '(footprint ', 1)

    # 2. Adicionar (version 20231120) após o nome do footprint
    # Padrão: (footprint "NomeDoModulo" ...)
    # O nome pode ou não estar entre aspas
    match = re.search(r'(\(footprint\s+(?:"[^"]*"|[^\s)]+))', result)
    if match:
        insert_pos = match.end()
        version_str = '\n  (version 20231120)'
        result = result[:insert_pos] + version_str + result[insert_pos:]

    # 3. Adicionar (attr ...) — logo após (layer "F.Cu") ou antes do primeiro (fp_text)
    attr_str = f'\n  (attr {attr})'

    # Tentar inserir após (layer ...)
    layer_match = re.search(r'(\(layer\s+(?:"[^"]*"|[^\s)]+)\))', result)
    if layer_match:
        insert_pos = layer_match.end()
        result = result[:insert_pos] + attr_str + result[insert_pos:]
    else:
        # Fallback: inserir antes do primeiro (fp_text) ou (pad)
        for tag in ['(fp_text', '(pad']:
            idx = result.find(tag)
            if idx > 0:
                result = result[:idx] + attr_str + '\n  ' + result[idx:]
                break

    return result


def apply_footprint_margins(kicad_mod, dados):
    """Aplica as margens de topo do YAML ao footprint (propriedades do KiCad).

    No KiCad, `solder_paste_margin` / `solder_mask_margin` são propriedades do
    FOOTPRINT (o KicadFileHandler as escreve a partir de pasteMargin/
    maskMargin) — e é exatamente onde o schema as declara: no topo, não por pad.

    Ficam aqui, no ponto de saída comum aos 7 padrões, em vez de repetidas em
    cada um — foi a repetição que deixou campos serem esquecidos.
    """
    if not isinstance(dados, dict):
        return
    for campo, setter in (('solder_paste_margin', kicad_mod.setPasteMargin),
                          ('solder_mask_margin', kicad_mod.setMaskMargin)):
        valor = dados.get(campo)
        if valor is None:
            continue
        try:
            setter(float(valor))
        except (TypeError, ValueError):
            log.warning("%s inválido (%r) — ignorado", campo, valor)


def save_footprint(kicad_mod, caminho_saida, v6=True, attr='through_hole',
                   dados=None):
    """Salva o footprint em arquivo .kicad_mod.

    Se v6=True, aplica postprocess_v6() para compatibilidade com KiCad 6+.
    Se `dados` for passado, aplica as margens de topo (solder_paste_margin /
    solder_mask_margin) antes de serializar.
    """
    import os

    apply_footprint_margins(kicad_mod, dados)

    # Garantir que o diretório existe
    dir_saida = os.path.dirname(caminho_saida)
    if dir_saida:
        os.makedirs(dir_saida, exist_ok=True)

    handler = KicadFileHandler(kicad_mod)

    try:
        if v6:
            # Gerar conteúdo em memória e pós-processar
            content = handler.serialize()
            content = postprocess_v6(content, attr=attr)
            with open(caminho_saida, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            # Modo legado (v5) — escrita direta
            handler.writeFile(caminho_saida)
    except PermissionError:
        log.error('Sem permissão para salvar: %s', caminho_saida)
        raise
    except OSError as e:
        log.error('Erro ao salvar footprint: %s (%s)', caminho_saida, e)
        raise

    log.info(f'Footprint salvo: {caminho_saida}')
