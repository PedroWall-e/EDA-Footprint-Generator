# =============================================================================
# gerador_footprint_v2.py
# Motor Universal de Footprints — geração paramétrica baseada em padrões
#
# Lê descrições YAML de componentes e gera footprints .kicad_mod usando
# 5 padrões de pad universais:
#   - axial_pth:  2 pads em linha (resistor, diodo, LED, cristal, capacitor)
#   - radial_pth: 3+ pads em cluster (TO-92, TO-220)
#   - dual_pth:   2 fileiras de pads PTH (DIP)
#   - dual_smd:   2 fileiras de pads SMD (SOIC, SSOP, SOT-23)
#   - quad_smd:   4 lados de pads SMD (QFP, QFN, castellated)
#
# Autor: Gerador Automático de Footprints
# Compatibilidade: KiCad 6.x / 7.x / 8.x
# =============================================================================

import os
import math
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

from footprint_helpers import (
    draw_courtyard,
    draw_courtyard_raw,
    draw_silkscreen_rect,
    draw_fab_rect,
    draw_circle_segments,
    draw_dshape,
    draw_pin1_marker,
    add_reference_text,
    add_value_text,
    add_3d_model,
    add_pth_pad,
    add_smd_pad,
    add_thermal_pad,
    read_paste_ratio,
    build_override_map,
    validate_annular_ring,
    check_pad_collisions,
    postprocess_v6,
    save_footprint,
)

log = logging.getLogger(__name__)


# =============================================================================
# Utilitários internos
# =============================================================================

def _get(dados, *keys, default=None):
    """Acesso seguro a chaves aninhadas no dicionário YAML."""
    d = dados
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def _float(dados, *keys, default=0.0):
    """Lê valor float de chaves aninhadas."""
    v = _get(dados, *keys, default=default)
    if v is None:
        return default
    return float(v)


def _int(dados, *keys, default=0):
    """Lê valor int de chaves aninhadas."""
    v = _get(dados, *keys, default=default)
    if v is None:
        return default
    return int(v)


def _body_rect(dados):
    """Extrai coordenadas do corpo retangular a partir dos dados YAML.

    Retorna (x0, y0, x1, y1) centrado na origem.
    Procura corpo.largura/corpo.comprimento ou corpo.largura/corpo.altura.
    """
    largura = _float(dados, 'corpo', 'largura', default=0)
    comprimento = _float(dados, 'corpo', 'comprimento', default=0)
    if comprimento == 0:
        comprimento = _float(dados, 'corpo', 'altura', default=0)
    return (-largura / 2, -comprimento / 2, largura / 2, comprimento / 2)


def _draw_body(kicad_mod, dados, larg_silk, larg_fab):
    """Desenha contorno do corpo baseado em corpo.formato.

    Formatos suportados:
      - 'retangulo' (padrão): retângulo nas camadas F.SilkS e F.Fab
      - 'cilindro': círculo por segmentos nas camadas F.SilkS e F.Fab
      - 'dshape': forma D (TO-92)
    """
    formato = _get(dados, 'corpo', 'formato', default='retangulo')

    if formato == 'cilindro':
        diam = _float(dados, 'corpo', 'diametro', default=0)
        if diam == 0:
            # Fallback para largura como diâmetro
            diam = _float(dados, 'corpo', 'largura', default=5.0)
        r = diam / 2
        draw_circle_segments(kicad_mod, 0, 0, r, 'F.SilkS', larg_silk)
        draw_circle_segments(kicad_mod, 0, 0, r, 'F.Fab', larg_fab)
        return (0, 0, r)  # (cx, cy, raio)

    elif formato == 'dshape':
        diam = _float(dados, 'corpo', 'diametro', default=0)
        r = diam / 2
        draw_dshape(kicad_mod, r, 'F.SilkS', larg_silk)
        draw_dshape(kicad_mod, r, 'F.Fab', larg_fab)
        return (0, 0, r)

    else:
        # retangulo (padrão)
        x0, y0, x1, y1 = _body_rect(dados)
        draw_silkscreen_rect(kicad_mod, x0, y0, x1, y1, larg_silk)
        draw_fab_rect(kicad_mod, x0, y0, x1, y1, larg_fab)
        return (x0, y0, x1, y1)


# =============================================================================
# Padrão 1: axial_pth
# 2 pads em linha — resistor, diodo, LED, cristal, capacitor axial
# =============================================================================

def _gerar_axial_pth(dados, caminho_saida):
    """Gera footprint para componentes axiais PTH com 2 pads em linha.

    YAML esperado:
        padrao: axial_pth
        nome: "Resistor_100R"
        pinos:
            espacamento: 10.16    # distância entre centros dos pads
            diametro_pad: 1.6     # diâmetro externo do pad
            diametro_furo: 0.8    # diâmetro do furo (drill)
        corpo:
            formato: retangulo    # ou cilindro
            comprimento: 6.5     # comprimento do corpo (eixo X)
            diametro: 2.5        # diâmetro/altura do corpo
            # ou largura/altura para retangulo
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "Resistor.step"
            descricao: "Resistor axial PTH"
            tags: "resistor pth axial"
    """
    nome        = dados['nome']
    espacamento = _float(dados, 'pinos', 'espacamento')
    pad_diam    = _float(dados, 'pinos', 'diametro_pad')
    furo_diam   = _float(dados, 'pinos', 'diametro_furo')
    margem_cy   = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk   = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab    = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d   = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao   = _get(dados, 'kicad', 'descricao', default='')
    tags        = _get(dados, 'kicad', 'tags', default='')

    # Posições dos pads
    x_pin1 = -espacamento / 2
    x_pin2 =  espacamento / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Corpo ---
    formato = _get(dados, 'corpo', 'formato', default='retangulo')

    if formato == 'cilindro':
        corpo_diam = _float(dados, 'corpo', 'diametro', default=2.5)
        corpo_r = corpo_diam / 2

        # Textos acima/abaixo do corpo cilíndrico
        add_reference_text(footprint, nome, 0, -corpo_r,
                           thickness=larg_silk)
        add_value_text(footprint, nome, 0, corpo_r,
                       thickness=larg_fab)

        # Corpo cilíndrico
        draw_circle_segments(footprint, 0, 0, corpo_r, 'F.SilkS', larg_silk)
        draw_circle_segments(footprint, 0, 0, corpo_r, 'F.Fab', larg_fab)

        # Courtyard
        cy_x0 = x_pin1 - pad_diam / 2 - margem_cy
        cy_x1 = x_pin2 + pad_diam / 2 + margem_cy
        cy_y0 = -corpo_r - margem_cy
        cy_y1 =  corpo_r + margem_cy
        draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    else:
        # Retangular (resistor, diodo, cristal)
        corpo_comp = _float(dados, 'corpo', 'comprimento', default=0)
        if corpo_comp == 0:
            corpo_comp = _float(dados, 'corpo', 'largura', default=6.0)
        corpo_diam = _float(dados, 'corpo', 'diametro', default=0)
        if corpo_diam == 0:
            corpo_diam = _float(dados, 'corpo', 'altura', default=2.5)
        corpo_r = corpo_diam / 2
        corpo_x0 = -corpo_comp / 2
        corpo_x1 =  corpo_comp / 2

        # Textos
        add_reference_text(footprint, nome, 0, -corpo_r,
                           thickness=larg_silk)
        add_value_text(footprint, nome, 0, corpo_r,
                       thickness=larg_fab)

        # Corpo retangular
        draw_fab_rect(footprint, corpo_x0, -corpo_r, corpo_x1, corpo_r,
                      larg_fab)
        draw_silkscreen_rect(footprint, corpo_x0, -corpo_r, corpo_x1,
                             corpo_r, larg_silk)

        # Leads (fios nos F.Fab)
        footprint.append(Line(start=[x_pin1, 0], end=[corpo_x0, 0],
                              layer='F.Fab', width=larg_fab))
        footprint.append(Line(start=[x_pin2, 0], end=[corpo_x1, 0],
                              layer='F.Fab', width=larg_fab))

        # Courtyard
        cy_x0 = x_pin1 - pad_diam / 2 - margem_cy
        cy_x1 = x_pin2 + pad_diam / 2 + margem_cy
        cy_y0 = -corpo_r - margem_cy
        cy_y1 =  corpo_r + margem_cy
        draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    # --- Marcador pino 1 ---
    draw_pin1_marker(footprint, x_pin1 - pad_diam / 2 - 0.3, 0,
                     style='dot', size=0.5, line_width=larg_silk)

    # --- Pads THT: pino 1 quadrado, pino 2 circular ---
    ov = build_override_map(dados, pad_diam, pad_diam)
    add_pth_pad(footprint, 1, x_pin1, 0, pad_diam, furo_diam,
                shape=Pad.SHAPE_RECT, size=ov.get('1'))
    add_pth_pad(footprint, 2, x_pin2, 0, pad_diam, furo_diam,
                shape=Pad.SHAPE_CIRCLE, size=ov.get('2'))

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='through_hole', dados=dados)

    log.info("  [Footprint v2 axial_pth] %s  |  esp=%smm", nome, espacamento)
    log.info("  [Footprint v2 axial_pth] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão 2: radial_pth
# 3+ pads em cluster — TO-92, TO-220, transistores
# =============================================================================

def _gerar_radial_pth(dados, caminho_saida):
    """Gera footprint para componentes radiais PTH com 3+ pads em linha.

    YAML esperado:
        padrao: radial_pth
        nome: "TO-92_BCE"
        pinos:
            total: 3
            pitch: 1.27        # espaçamento entre pads adjacentes
            diametro_pad: 1.6
            diametro_furo: 0.8
        corpo:
            formato: dshape     # ou cilindro
            diametro: 5.0
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "TO-92.step"
            descricao: "Transistor TO-92"
            tags: "transistor to-92 pth"
    """
    nome      = dados['nome']
    total     = _int(dados, 'pinos', 'total', default=3)
    pitch     = _float(dados, 'pinos', 'pitch')
    pad_diam  = _float(dados, 'pinos', 'diametro_pad')
    furo_diam = _float(dados, 'pinos', 'diametro_furo')
    corpo_diam = _float(dados, 'corpo', 'diametro', default=5.0)
    margem_cy  = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk  = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab   = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d  = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao  = _get(dados, 'kicad', 'descricao', default='')
    tags       = _get(dados, 'kicad', 'tags', default='')

    corpo_r = corpo_diam / 2

    # Posições X dos pinos centrados na origem
    x_pins = []
    for i in range(total):
        x = -(total - 1) * pitch / 2 + i * pitch
        x_pins.append(x)

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, -corpo_r,
                       thickness=larg_silk)
    add_value_text(footprint, nome, 0, corpo_r,
                   thickness=larg_fab)

    # --- Corpo ---
    formato = _get(dados, 'corpo', 'formato', default='dshape')
    if formato == 'dshape':
        draw_dshape(footprint, corpo_r, 'F.SilkS', larg_silk)
        draw_dshape(footprint, corpo_r, 'F.Fab', larg_fab)
    elif formato == 'cilindro':
        draw_circle_segments(footprint, 0, 0, corpo_r, 'F.SilkS', larg_silk)
        draw_circle_segments(footprint, 0, 0, corpo_r, 'F.Fab', larg_fab)
    else:
        # retangulo genérico
        x0, y0, x1, y1 = _body_rect(dados)
        draw_silkscreen_rect(footprint, x0, y0, x1, y1, larg_silk)
        draw_fab_rect(footprint, x0, y0, x1, y1, larg_fab)

    # --- Courtyard ---
    cy_x0 = x_pins[0] - pad_diam / 2 - margem_cy
    cy_x1 = x_pins[-1] + pad_diam / 2 + margem_cy
    cy_y0 = -corpo_r - margem_cy
    cy_y1 =  corpo_r + margem_cy
    draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    # --- Pads THT: pino 1 quadrado, demais circulares ---
    ov = build_override_map(dados, pad_diam, pad_diam)
    for i, xp in enumerate(x_pins):
        num = i + 1
        shp = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        add_pth_pad(footprint, num, xp, 0, pad_diam, furo_diam, shape=shp,
                    size=ov.get(str(num)))

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='through_hole', dados=dados)

    log.info("  [Footprint v2 radial_pth] %s  |  %d pinos  |  pitch=%smm", nome, total, pitch)
    log.info("  [Footprint v2 radial_pth] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão 3: dual_pth
# 2 fileiras de pads PTH — DIP
# =============================================================================

def _gerar_dual_pth(dados, caminho_saida):
    """Gera footprint para CIs DIP (dual in-line, PTH).

    Numeração KiCad: pino 1 = top-left, desce pelo lado esquerdo,
    depois do pino N/2 sobe pelo lado direito (sentido horário).

    YAML esperado:
        padrao: dual_pth
        nome: "DIP-8"
        pinos:
            total: 8
            pitch: 2.54
            diametro_pad: 1.6
            diametro_furo: 0.8
        corpo:
            largura: 6.35       # entre bordas do corpo
            comprimento: 9.0    # altura do corpo
            afastamento_colunas: 7.62  # entre centros das 2 colunas
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "DIP-8.step"
            descricao: "CI DIP 8 pinos"
            tags: "dip ci pth"
    """
    nome        = dados['nome']
    total       = _int(dados, 'pinos', 'total')
    pitch       = _float(dados, 'pinos', 'pitch')
    pad_diam    = _float(dados, 'pinos', 'diametro_pad')
    furo_diam   = _float(dados, 'pinos', 'diametro_furo')
    corpo_larg  = _float(dados, 'corpo', 'largura')
    corpo_comp  = _float(dados, 'corpo', 'comprimento')
    afastamento = _float(dados, 'corpo', 'afastamento_colunas')
    margem_cy   = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk   = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab    = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d   = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao   = _get(dados, 'kicad', 'descricao', default='')
    tags        = _get(dados, 'kicad', 'tags', default='')

    meio     = total // 2
    y_inicio = -(meio - 1) * pitch / 2

    x_esq = -afastamento / 2
    x_dir =  afastamento / 2

    corpo_x0 = -corpo_larg / 2
    corpo_x1 =  corpo_larg / 2
    corpo_y0 = -corpo_comp / 2
    corpo_y1 =  corpo_comp / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, corpo_y0,
                       thickness=larg_silk)
    add_value_text(footprint, nome, 0, corpo_y1,
                   thickness=larg_fab)

    # --- Corpo retangular ---
    draw_fab_rect(footprint, corpo_x0, corpo_y0, corpo_x1, corpo_y1, larg_fab)
    draw_silkscreen_rect(footprint, corpo_x0, corpo_y0, corpo_x1, corpo_y1,
                         larg_silk)

    # --- Marcador pino 1: chanfro no canto superior esquerdo ---
    arco_r = 1.0
    draw_pin1_marker(footprint, corpo_x0, corpo_y0, style='chamfer',
                     size=arco_r, line_width=larg_silk)

    # --- Courtyard ---
    cy_x0 = x_esq - pad_diam / 2 - margem_cy
    cy_x1 = x_dir + pad_diam / 2 + margem_cy
    cy_y0 = y_inicio - pad_diam / 2 - margem_cy
    cy_y1 = y_inicio + (meio - 1) * pitch + pad_diam / 2 + margem_cy
    draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    # --- Pads THT ---
    ov = build_override_map(dados, pad_diam, pad_diam)

    # Lado esquerdo: pinos 1..meio (top → bottom)
    for i in range(meio):
        num = i + 1
        py  = y_inicio + i * pitch
        shp = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        add_pth_pad(footprint, num, x_esq, py, pad_diam, furo_diam, shape=shp,
                    size=ov.get(str(num)))

    # Lado direito: pinos meio+1..total (bottom → top)
    for i in range(meio):
        num = meio + 1 + i
        py  = y_inicio + (meio - 1 - i) * pitch
        add_pth_pad(footprint, num, x_dir, py, pad_diam, furo_diam,
                    shape=Pad.SHAPE_CIRCLE, size=ov.get(str(num)))

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='through_hole', dados=dados)

    log.info("  [Footprint v2 dual_pth] %s  |  %d pinos  |  pitch=%smm", nome, total, pitch)
    log.info("  [Footprint v2 dual_pth] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão: single_row_pth
# 1 fileira de pads PTH — pin header 1xN
# =============================================================================

def _gerar_single_row_pth(dados, caminho_saida):
    """Gera footprint de FILEIRA ÚNICA PTH — pin header 1xN.

    Existe porque `conector_pth` caía no `dual_pth`, que é de DUAS fileiras:
    `total // 2` descartava o pino ímpar (1x3 saía com 2 pads) e o
    `afastamento_colunas` ausente colapsava as duas colunas em x=0, empilhando
    os pads. Um header 1xN não é um DIP com metade dos pinos.

    Os pads ficam numa coluna em x=0, pino 1 no topo (Y do KiCad cresce para
    baixo) — a convenção da biblioteca oficial do KiCad para PinHeader_1xN.

    YAML esperado:
        padrao: single_row_pth      (ou tipo: conector_pth via shim)
        nome: "Conn_01x06_PinHeader"
        pinos:
            total: 6
            pitch: 2.54
            diametro_pad: 1.7
            diametro_furo: 1.0
        corpo:                      # opcional — derivado dos pads se ausente
            largura: 2.54
            comprimento: 15.24
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
    """
    nome      = dados['nome']
    total     = _int(dados, 'pinos', 'total')
    pitch     = _float(dados, 'pinos', 'pitch')
    pad_diam  = _float(dados, 'pinos', 'diametro_pad')
    furo_diam = _float(dados, 'pinos', 'diametro_furo')
    margem_cy = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab  = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao = _get(dados, 'kicad', 'descricao', default='')
    tags      = _get(dados, 'kicad', 'tags', default='')

    if total < 1:
        raise ValueError(f"'{nome}': padrão 'single_row_pth' requer pinos.total >= 1.")
    if pitch <= 0:
        raise ValueError(f"'{nome}': padrão 'single_row_pth' requer pinos.pitch > 0.")

    # Corpo: os YAMLs de header não trazem `corpo` — derivar do pitch e da
    # contagem, como faz a biblioteca do KiCad (uma tira de 1 pitch de largura).
    corpo_larg = _float(dados, 'corpo', 'largura', default=0) or pitch
    corpo_comp = _float(dados, 'corpo', 'comprimento', default=0) or (total * pitch)

    y_inicio = -(total - 1) * pitch / 2
    corpo_x0, corpo_x1 = -corpo_larg / 2, corpo_larg / 2
    corpo_y0, corpo_y1 = -corpo_comp / 2, corpo_comp / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, corpo_y0, thickness=larg_silk)
    add_value_text(footprint, nome, 0, corpo_y1, thickness=larg_fab)

    # --- Corpo (silk + fab) ---
    draw_silkscreen_rect(footprint, corpo_x0, corpo_y0, corpo_x1, corpo_y1, larg_silk)
    draw_fab_rect(footprint, corpo_x0, corpo_y0, corpo_x1, corpo_y1, larg_fab)

    # --- Marcador do pino 1 ---
    draw_pin1_marker(footprint, corpo_x0 - 0.3, y_inicio, style='arrow',
                     size=0.5, line_width=larg_silk)

    # --- Pads: uma coluna em x=0, pino 1 quadrado ---
    ov = build_override_map(dados, pad_diam, pad_diam)
    pads_bbox = []
    for i in range(total):
        num = i + 1
        py  = y_inicio + i * pitch
        shp = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        add_pth_pad(footprint, num, 0, py, pad_diam, furo_diam, shape=shp,
                    size=ov.get(str(num)))
        w, h = ov.get(str(num), (pad_diam, pad_diam))
        pads_bbox.append((num, 0, py, w, h))

    check_pad_collisions(pads_bbox, nome)

    # --- Courtyard: envolve pads e corpo ---
    cy_x0 = min(corpo_x0, -pad_diam / 2) - margem_cy
    cy_x1 = max(corpo_x1,  pad_diam / 2) + margem_cy
    cy_y0 = min(corpo_y0, y_inicio - pad_diam / 2) - margem_cy
    cy_y1 = max(corpo_y1, y_inicio + (total - 1) * pitch + pad_diam / 2) + margem_cy
    draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='through_hole', dados=dados)

    log.info("  [Footprint v2 single_row_pth] %s  |  %d pinos  |  pitch=%smm",
             nome, total, pitch)


# =============================================================================
# Padrão 4: dual_smd
# 2 fileiras de pads SMD — SOIC, SSOP, SOT-23
# =============================================================================

def _gerar_dual_smd(dados, caminho_saida):
    """Gera footprint para CIs SMD com 2 fileiras (SOIC, SSOP, SOT-23, DPAK).

    Suporta distribuição assimétrica via campo 'distribuicao: [N_esq, N_dir]'.
    Suporta override de tamanho por pino via 'pinos_absolutos'.

    Numeração (simétrica): pinos 1..N/2 esquerda (top→bottom),
                           pinos N/2+1..N direita (bottom→top).
    Numeração (assimétrica): pinos 1..N_esq esquerda (top→bottom),
                             pinos N_esq+1..total direita (centralizados).

    YAML esperado:
        padrao: dual_smd
        nome: "SOIC-8"
        pinos:
            total: 8
            pitch: 1.27
            distribuicao: [4, 4]   # opcional, default = [total/2, total/2]
            tamanho_pad:
                largura: 0.6
                altura: 1.5
        corpo:
            largura: 3.9
            comprimento: 4.9
            afastamento_colunas: 5.4
        pinos_absolutos:           # opcional — override de tamanho por pino
            3:
                pad:
                    largura: 5.4
                    altura: 6.0
    """
    nome        = dados['nome']
    total       = _int(dados, 'pinos', 'total')
    pitch       = _float(dados, 'pinos', 'pitch')
    pad_w       = _float(dados, 'pinos', 'tamanho_pad', 'largura')
    pad_h       = _float(dados, 'pinos', 'tamanho_pad', 'altura')
    corpo_larg  = _float(dados, 'corpo', 'largura')
    corpo_comp  = _float(dados, 'corpo', 'comprimento')
    afastamento = _float(dados, 'corpo', 'afastamento_colunas', default=0)
    margem_cy   = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk   = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab    = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d   = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao   = _get(dados, 'kicad', 'descricao', default='')
    tags        = _get(dados, 'kicad', 'tags', default='')

    # --- Distribuição: [N_esq, N_dir] ---
    distrib = _get(dados, 'pinos', 'distribuicao', default=None)
    if distrib and isinstance(distrib, (list, tuple)) and len(distrib) == 2:
        n_esq = int(distrib[0])
        n_dir = int(distrib[1])
    else:
        n_esq = total // 2
        n_dir = total - n_esq

    # --- Afastamento: auto-calcular se não especificado ---
    if afastamento <= 0:
        afastamento = corpo_larg + pad_w

    x_esq = -afastamento / 2
    x_dir =  afastamento / 2

    # --- Overrides por pino (pinos_absolutos) ---
    pinos_abs = dados.get('pinos_absolutos', {})

    override_map = build_override_map(dados, pad_w, pad_h)

    def _pad_size(num):
        """Retorna (w, h) para o pad num.

        Precedência: `pinos_absolutos[N].pad` (mecanismo nativo deste padrão,
        mais específico) vence `pinos.overrides` (mecanismo geral), que por sua
        vez vence o tamanho padrão.
        """
        ov = pinos_abs.get(num, pinos_abs.get(str(num), None))
        if ov and 'pad' in ov:
            ow = float(ov['pad'].get('largura', pad_w))
            oh = float(ov['pad'].get('altura', pad_h))
            return ow, oh
        return override_map.get(str(num), (pad_w, pad_h))

    # --- Posições dos pads ---
    # Lado esquerdo: n_esq pads, centralizados verticalmente, espaçados por pitch
    y_inicio_esq = -(n_esq - 1) * pitch / 2

    # Lado direito: n_dir pads, centralizados verticalmente, espaçados por pitch
    # Se pitch=0 e n_dir=1 (ex: DPAK tab), o pad fica em Y=0
    if n_dir == 1:
        pitch_dir = 0
    else:
        pitch_dir = pitch
    y_inicio_dir = -(n_dir - 1) * pitch_dir / 2

    corpo_x0 = -corpo_larg / 2
    corpo_x1 =  corpo_larg / 2
    corpo_y0 = -corpo_comp / 2
    corpo_y1 =  corpo_comp / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, corpo_y0,
                       thickness=larg_silk)
    add_value_text(footprint, nome, 0, corpo_y1,
                   thickness=larg_fab)

    # --- Corpo retangular F.Fab ---
    draw_fab_rect(footprint, corpo_x0, corpo_y0, corpo_x1, corpo_y1, larg_fab)

    # --- F.SilkS: apenas top e bottom (lados com pads ficam livres) ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0],
                          layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1],
                          layer='F.SilkS', width=larg_silk))

    # --- Marcador pino 1: chanfro no canto superior esquerdo ---
    arco_r = 0.5
    draw_pin1_marker(footprint, corpo_x0, corpo_y0, style='chamfer',
                     size=arco_r, line_width=larg_silk)

    # --- Pads SMD: lado esquerdo (pinos 1..n_esq, top→bottom) ---
    all_pad_bounds = []  # para courtyard

    for i in range(n_esq):
        num = i + 1
        py  = y_inicio_esq + i * pitch
        w, h = _pad_size(num)
        add_smd_pad(footprint, num, x_esq, py, w, h)
        all_pad_bounds.append((x_esq - w/2, py - h/2, x_esq + w/2, py + h/2))

    # --- Pads SMD: lado direito ---
    if n_esq == n_dir:
        # Simétrico: numeração espelhada (bottom→top) — padrão SOIC/SSOP
        for i in range(n_dir):
            num = n_esq + 1 + i
            py  = y_inicio_dir + (n_dir - 1 - i) * pitch_dir
            w, h = _pad_size(num)
            add_smd_pad(footprint, num, x_dir, py, w, h)
            all_pad_bounds.append((x_dir - w/2, py - h/2, x_dir + w/2, py + h/2))
    else:
        # Assimétrico: numeração sequencial (top→bottom) — DPAK, SOT-223
        for i in range(n_dir):
            num = n_esq + 1 + i
            py  = y_inicio_dir + i * pitch_dir
            w, h = _pad_size(num)
            add_smd_pad(footprint, num, x_dir, py, w, h)
            all_pad_bounds.append((x_dir - w/2, py - h/2, x_dir + w/2, py + h/2))

    # --- Thermal pad (se definido explicitamente) ---
    thermal = _get(dados, 'pinos', 'thermal_pad', default=None)
    if thermal:
        tw = float(thermal.get('largura', 0))
        th = float(thermal.get('altura', 0))
        paste_ratio = read_paste_ratio(thermal)
        if tw > 0 and th > 0:
            add_thermal_pad(footprint, 0, 0, tw, th, paste_ratio)
            all_pad_bounds.append((-tw/2, -th/2, tw/2, th/2))

    # --- Courtyard (baseado nos bounds reais de todos os pads) ---
    if all_pad_bounds:
        cy_x0 = min(b[0] for b in all_pad_bounds) - margem_cy
        cy_y0 = min(b[1] for b in all_pad_bounds) - margem_cy
        cy_x1 = max(b[2] for b in all_pad_bounds) + margem_cy
        cy_y1 = max(b[3] for b in all_pad_bounds) + margem_cy
    else:
        cy_x0 = x_esq - pad_w / 2 - margem_cy
        cy_x1 = x_dir + pad_w / 2 + margem_cy
        cy_y0 = -corpo_comp / 2 - margem_cy
        cy_y1 =  corpo_comp / 2 + margem_cy
    draw_courtyard_raw(footprint, cy_x0, cy_y0, cy_x1, cy_y1)

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='smd', dados=dados)

    log.info("  [Footprint v2 dual_smd] %s  |  %d pinos [%d+%d]  |  pitch=%smm",
             nome, total, n_esq, n_dir, pitch)
    log.info("  [Footprint v2 dual_smd] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão 5: quad_smd
# 4 lados de pads SMD — QFP, QFN, castellated
# =============================================================================

def _gerar_quad_smd(dados, caminho_saida):
    """Gera footprint para CIs SMD com 4 lados (QFP, QFN, castellated).

    Numeração horária a partir do canto superior-esquerdo:
      Esquerdo  → 1 .. n_esq          (cima → baixo)
      Base      → n_esq+1 .. +n_base  (esq  → dir)
      Direito   → +1 .. +n_dir        (baixo → cima)
      Topo      → +1 .. +n_topo       (dir  → esq)

    YAML esperado:
        padrao: quad_smd
        nome: "QFP-32"
        pinos:
            pitch: 0.8
            tamanho_pad:
                largura: 0.5
                altura: 1.2
            lados:
                esquerdo: 8
                base: 8
                direito: 8
                topo: 8
            # OU: por_lado: 8 (mesmo número em todos os lados)
        corpo:  # ou pcb:
            largura: 7.0
            altura: 7.0
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "QFP-32.step"
            descricao: "CI QFP 32 pinos"
            tags: "qfp smd ci"
    """
    nome      = dados['nome']
    pitch     = _float(dados, 'pinos', 'pitch')
    pad_w_def = _float(dados, 'pinos', 'tamanho_pad', 'largura')
    pad_h_def = _float(dados, 'pinos', 'tamanho_pad', 'altura')
    margem_cy = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab  = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao = _get(dados, 'kicad', 'descricao', default='')
    tags      = _get(dados, 'kicad', 'tags', default='')

    # Dimensões do corpo/PCB
    pcb_largura = _float(dados, 'pcb', 'largura', default=0)
    pcb_altura  = _float(dados, 'pcb', 'altura', default=0)
    if pcb_largura == 0:
        pcb_largura = _float(dados, 'corpo', 'largura', default=7.0)
    if pcb_altura == 0:
        pcb_altura = _float(dados, 'corpo', 'altura', default=0)
        if pcb_altura == 0:
            pcb_altura = _float(dados, 'corpo', 'comprimento', default=7.0)

    # Número de pinos por lado
    lados = _get(dados, 'pinos', 'lados', default=None)
    if lados:
        n_esq  = int(lados.get('esquerdo', 0))
        n_base = int(lados.get('base', 0))
        n_dir  = int(lados.get('direito', 0))
        n_topo = int(lados.get('topo', 0))
    else:
        por_lado = _int(dados, 'pinos', 'por_lado', default=0)
        if por_lado > 0:
            n_esq = n_base = n_dir = n_topo = por_lado
        else:
            total = _int(dados, 'pinos', 'total', default=0)
            por_lado = total // 4
            n_esq = n_base = n_dir = n_topo = por_lado

    total = n_esq + n_base + n_dir + n_topo

    # --- Validação: `total` declarado tem que bater com a distribuição ---
    # Quando `lados`/`por_lado` estavam presentes, um `pinos.total` divergente
    # era descartado em silêncio: o Stx3 declarava total: 32 com por_lado: 16 e
    # saía com 64 pads, sem erro nenhum. E na divisão automática o resto sumia
    # calado (total: 30 → 30//4 = 7 por lado → 28 pads, faltando 2).
    # Contradição agora é erro: melhor não gerar do que gerar errado.
    total_declarado = _int(dados, 'pinos', 'total', default=0)
    if total_declarado and total_declarado != total:
        raise ValueError(
            f"'{nome}': pinos.total={total_declarado} contradiz a distribuição "
            f"por lado (esquerdo={n_esq}, base={n_base}, direito={n_dir}, "
            f"topo={n_topo} → {total} pads). Ajuste o total ou declare os lados "
            f"explicitamente com pinos.lados (use 0 nos lados sem pinos)."
        )

    # Bordas do corpo
    x_min = -(pcb_largura / 2)
    x_max =  (pcb_largura / 2)
    y_min = -(pcb_altura / 2)
    y_max =  (pcb_altura / 2)

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, y_min,
                       thickness=larg_silk)
    add_value_text(footprint, nome, 0, y_max,
                   thickness=larg_fab)

    # --- Corpo retangular ---
    draw_silkscreen_rect(footprint, x_min, y_min, x_max, y_max, larg_silk)
    draw_fab_rect(footprint, x_min, y_min, x_max, y_max, larg_fab)

    # --- Courtyard ---
    draw_courtyard(footprint, x_min, y_min, x_max, y_max,
                   margin=margem_cy)

    # --- Calcular posições dos pads ---
    pad_num = 1
    pads_info = []  # lista de (num, x, y, w, h)

    # Overrides de tamanho — aceita as duas formas do schema (dict e lista)
    override_map = build_override_map(dados, pad_w_def, pad_h_def)

    def _pad_size(num):
        """Retorna (w, h) para o pad num, considerando overrides."""
        return override_map.get(str(num), (pad_w_def, pad_h_def))

    # `pinos.numeracao` permite fixar onde a numeração de um lado começa, em
    # vez de seguir a contagem corrida (esquerdo → base → direito → topo).
    # Útil quando o datasheet numera assim. Sobreposições viram erro logo
    # abaixo — pad duplicado seria netlist errada.
    numeracao  = _get(dados, 'pinos', 'numeracao', default=None) or {}
    inicio_esq = numeracao.get('inicio_esquerdo')
    inicio_dir = numeracao.get('inicio_direito')

    # Esquerdo: cima → baixo (pads orientados horizontalmente)
    if n_esq > 0:
        if inicio_esq is not None:
            pad_num = int(inicio_esq)
        y_start = -(n_esq - 1) * pitch / 2
        for i in range(n_esq):
            w, h = _pad_size(pad_num)
            px = x_min
            py = y_start + i * pitch
            pads_info.append((pad_num, px, py, w, h, False))
            pad_num += 1

    # Base: esquerda → direita (pads orientados verticalmente)
    if n_base > 0:
        x_start = -(n_base - 1) * pitch / 2
        for i in range(n_base):
            w, h = _pad_size(pad_num)
            px = x_start + i * pitch
            py = y_max
            # Para base/topo, w e h se trocam (pad perpendicular à borda)
            pads_info.append((pad_num, px, py, h, w, True))
            pad_num += 1

    # Direito: baixo → cima (pads orientados horizontalmente)
    if n_dir > 0:
        if inicio_dir is not None:
            pad_num = int(inicio_dir)
        y_start = -(n_dir - 1) * pitch / 2
        for i in range(n_dir):
            w, h = _pad_size(pad_num)
            px = x_max
            py = y_start + (n_dir - 1 - i) * pitch
            pads_info.append((pad_num, px, py, w, h, False))
            pad_num += 1

    # Topo: direita → esquerda (pads orientados verticalmente)
    if n_topo > 0:
        x_start = -(n_topo - 1) * pitch / 2
        for i in range(n_topo):
            w, h = _pad_size(pad_num)
            px = x_start + (n_topo - 1 - i) * pitch
            py = y_min
            pads_info.append((pad_num, px, py, h, w, True))
            pad_num += 1

    # --- Validação: numeração não pode repetir ---
    # `pinos.numeracao` fixa o início de um lado; se colidir com a contagem
    # corrida dos outros, dois pads saem com o mesmo número — e pad duplicado
    # é netlist errada, o tipo de defeito que só aparece na placa montada.
    numeros = [p[0] for p in pads_info]
    repetidos = sorted({n for n in numeros if numeros.count(n) > 1})
    if repetidos:
        raise ValueError(
            f"'{nome}': pinos.numeracao gerou pads duplicados {repetidos}. "
            f"A contagem corre esquerdo → base → direito → topo "
            f"(esquerdo={n_esq}, base={n_base}, direito={n_dir}, topo={n_topo}); "
            f"um inicio_* que caia sobre outro lado colide. Ajuste os inícios "
            f"ou remova pinos.numeracao para usar a numeração sequencial."
        )

    # --- Marcador pino 1 ---
    if pads_info:
        p1 = pads_info[0]
        mx = p1[1] - pad_w_def * 0.6 if not p1[5] else p1[1]
        my = p1[2]
        draw_pin1_marker(footprint, mx, my, style='dot',
                         size=0.5, line_width=larg_silk)

    # --- Criar pads SMD ---
    for num, px, py, w, h, _rotated in pads_info:
        add_smd_pad(footprint, num, px, py, w, h)

    # --- Thermal pad (se definido) ---
    thermal = _get(dados, 'pinos', 'thermal_pad', default=None)
    if thermal:
        tw = float(thermal.get('largura', 0))
        th = float(thermal.get('altura', 0))
        paste_ratio = read_paste_ratio(thermal)
        if tw > 0 and th > 0:
            add_thermal_pad(footprint, 0, 0, tw, th, paste_ratio)

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='smd', dados=dados)

    log.info("  [Footprint v2 quad_smd] %s  |  %d pads", nome, total)
    log.info("  [Footprint v2 quad_smd] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão 6: custom
# Pads em posições totalmente arbitrárias — antenas, baterias, supercapacitores
# =============================================================================

def _gerar_custom(dados, caminho_saida):
    """Gera footprint com pads em posições arbitrárias definidas no YAML.

    Cada pad é definido individualmente com posição, tamanho e formato.
    Cobre 100% dos componentes possíveis — antenas patch, baterias coin cell,
    supercapacitores, conectores exóticos, módulos RF, etc.

    YAML esperado:
        padrao: custom
        nome: "Antena_Patch_GPS"
        pads:
          - numero: 1
            nome: "SIGNAL"
            tipo_eletrico: "passive"
            x: 0.0
            y: 0.0
            largura: 1.2
            altura: 1.2
            formato: "retangulo"       # retangulo|circulo|oval|roundrect
            montagem: "smd"            # smd|pth
            furo: 0.0                  # só para pth
          - numero: 2
            nome: "GND"
            tipo_eletrico: "power_in"
            x: -10.0
            y: -10.0
            largura: 2.0
            altura: 2.0
            formato: "retangulo"
            montagem: "smd"
        corpo:
            largura: 25.0
            comprimento: 25.0
            formato: retangulo         # retangulo|cilindro
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "Antena.step"
            descricao: "Antena patch GPS 25x25mm"
            tags: "antena gps patch smd"
    """
    nome       = dados['nome']
    pads_list  = dados.get('pads', [])
    margem_cy  = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk  = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab   = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d  = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao  = _get(dados, 'kicad', 'descricao', default='')
    tags       = _get(dados, 'kicad', 'tags', default='')

    if not pads_list:
        raise ValueError(f"'{nome}': padrão 'custom' requer lista 'pads' no YAML.")

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Mapeamento de formatos ---
    SHAPE_MAP = {
        'retangulo': Pad.SHAPE_RECT,
        'rect':      Pad.SHAPE_RECT,
        'circulo':   Pad.SHAPE_CIRCLE,
        'circle':    Pad.SHAPE_CIRCLE,
        'oval':      Pad.SHAPE_OVAL,
        'roundrect': Pad.SHAPE_ROUNDRECT,
    }

    # --- Criar pads ---
    has_pth = False
    has_smd = False
    all_x = []
    all_y = []
    # Bounding boxes para a checagem de colisao. O `custom` e o unico padrao em
    # que as posicoes sao escritas a mao — nos parametricos elas sao calculadas.
    # E' aqui, portanto, que da' para colidir, e ate agora nada checava.
    pads_bbox = []

    for i, pad_def in enumerate(pads_list):
        num       = pad_def.get('numero', i + 1)
        px        = float(pad_def.get('x', 0))
        py        = float(pad_def.get('y', 0))
        pw        = float(pad_def.get('largura', 1.0))
        ph        = float(pad_def.get('altura', 1.0))
        pads_bbox.append((num, px, py, pw, ph))
        fmt_str   = pad_def.get('formato', 'retangulo')
        montagem  = pad_def.get('montagem', 'smd')
        furo      = float(pad_def.get('furo', 0))
        rr_ratio  = float(pad_def.get('roundrect_ratio', 0.25))

        shape = SHAPE_MAP.get(fmt_str, Pad.SHAPE_RECT)

        if montagem == 'pth' or furo > 0:
            has_pth = True
            # Pad through-hole
            pad_size = max(pw, ph)
            if shape == Pad.SHAPE_CIRCLE:
                pad_size_val = pad_size
            else:
                pad_size_val = [pw, ph]

            footprint.append(Pad(
                number=str(num),
                type=Pad.TYPE_THT,
                shape=shape if shape != Pad.SHAPE_ROUNDRECT else Pad.SHAPE_RECT,
                at=[px, py],
                size=pad_size_val if isinstance(pad_size_val, list) else pad_size_val,
                drill=furo,
                layers=['*.Cu', '*.Mask'],
            ))
            validate_annular_ring(pad_size, furo)
        else:
            has_smd = True
            # Pad SMD
            pad_kwargs = dict(
                number=str(num),
                type=Pad.TYPE_SMT,
                shape=shape,
                at=[px, py],
                size=[pw, ph],
                layers=['F.Cu', 'F.Paste', 'F.Mask'],
            )
            if shape == Pad.SHAPE_ROUNDRECT:
                pad_kwargs['round_rect_ratio'] = rr_ratio

            footprint.append(Pad(**pad_kwargs))

        # Rastrear extensão para courtyard
        all_x.extend([px - pw / 2, px + pw / 2])
        all_y.extend([py - ph / 2, py + ph / 2])

    # --- Colisao entre pads ---
    check_pad_collisions(pads_bbox, nome)

    # --- Corpo ---
    body_info = _draw_body(footprint, dados, larg_silk, larg_fab)

    # Expandir extensão com corpo se for retangular
    if isinstance(body_info, tuple) and len(body_info) == 4:
        bx0, by0, bx1, by1 = body_info
        all_x.extend([bx0, bx1])
        all_y.extend([by0, by1])
    elif isinstance(body_info, tuple) and len(body_info) == 3:
        cx, cy, r = body_info
        all_x.extend([cx - r, cx + r])
        all_y.extend([cy - r, cy + r])

    # --- Courtyard ---
    if all_x and all_y:
        cx0 = min(all_x) - margem_cy
        cy0 = min(all_y) - margem_cy
        cx1 = max(all_x) + margem_cy
        cy1 = max(all_y) + margem_cy
        draw_courtyard_raw(footprint, cx0, cy0, cx1, cy1)

    # --- Textos ---
    text_y_top = min(all_y) - 1.5 if all_y else -3.0
    text_y_bot = max(all_y) + 1.5 if all_y else 3.0
    add_reference_text(footprint, nome, 0, text_y_top, thickness=larg_silk)
    add_value_text(footprint, nome, 0, text_y_bot, thickness=larg_fab)

    # --- Pin 1 marker ---
    if pads_list:
        p1 = pads_list[0]
        p1x = float(p1.get('x', 0))
        p1y = float(p1.get('y', 0))
        p1w = float(p1.get('largura', 1.0))
        draw_pin1_marker(footprint, p1x - p1w / 2 - 0.5, p1y,
                         style='dot', layer='F.SilkS')

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Determinar atributo ---
    if has_smd and has_pth:
        attr = 'smd'  # Componentes mistos tratam como SMD
    elif has_smd:
        attr = 'smd'
    else:
        attr = 'through_hole'

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, attr=attr, dados=dados)

    log.info("  [Footprint v2 custom] %s  |  %d pads (%s)",
             nome, len(pads_list), attr)
    log.info("  [Footprint v2 custom] Arquivo: %s", caminho_saida)


# =============================================================================
# Padrão 7: bga
# Grid de pads SMD circulares — BGA (Ball Grid Array)
# =============================================================================

def _row_label(row_idx):
    """Converte índice de linha (0-based) em label: 0→A, 1→B, ..., 25→Z, 26→AA."""
    label = ''
    n = row_idx
    while True:
        label = chr(ord('A') + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label


def _gerar_bga(dados, caminho_saida):
    """Gera footprint para encapsulamentos BGA (Ball Grid Array).

    Cria uma grid de pads SMD circulares com labels A1, A2... B1, B2...
    Suporta exclusão de balls específicas via lista 'excluir'.

    YAML esperado:
        padrao: bga
        nome: "BGA256_17x17"
        pinos:
            linhas: 16          # linhas (A-P)
            colunas: 16         # colunas (1-16)
            pitch: 1.0          # espaçamento entre balls
            diametro_pad: 0.5   # diâmetro do pad circular
            excluir: []         # balls removidas e.g. ["A1", "P16"]
        corpo:
            largura: 17.0
            comprimento: 17.0
        margens:
            courtyard: 0.5
            silkscreen: 0.12
            fab_line: 0.10
        kicad:
            modelo_3d: "BGA256.step"
            descricao: "BGA-256 17x17mm"
            tags: "bga smd"
    """
    nome       = dados['nome']
    linhas     = _int(dados, 'pinos', 'linhas', default=10)
    colunas    = _int(dados, 'pinos', 'colunas', default=10)
    pitch      = _float(dados, 'pinos', 'pitch', default=0.8)
    pad_diam   = _float(dados, 'pinos', 'diametro_pad', default=0.4)
    excluir    = set(_get(dados, 'pinos', 'excluir', default=[]) or [])
    margem_cy  = _float(dados, 'margens', 'courtyard', default=0.5)
    larg_silk  = _float(dados, 'margens', 'silkscreen', default=0.12)
    larg_fab   = _float(dados, 'margens', 'fab_line', default=0.10)
    modelo_3d  = _get(dados, 'kicad', 'modelo_3d', default=None)
    descricao  = _get(dados, 'kicad', 'descricao', default='')
    tags       = _get(dados, 'kicad', 'tags', default='')

    # Dimensões do corpo
    corpo_larg = _float(dados, 'corpo', 'largura',
                        default=(colunas - 1) * pitch + pitch * 2)
    corpo_comp = _float(dados, 'corpo', 'comprimento',
                        default=(linhas - 1) * pitch + pitch * 2)
    if corpo_comp == 0:
        corpo_comp = _float(dados, 'corpo', 'altura',
                            default=(linhas - 1) * pitch + pitch * 2)

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Grid origin (centro) ---
    grid_x0 = -(colunas - 1) * pitch / 2
    grid_y0 = -(linhas - 1) * pitch / 2

    # --- Corpo retangular ---
    bx0 = -corpo_larg / 2
    bx1 =  corpo_larg / 2
    by0 = -corpo_comp / 2
    by1 =  corpo_comp / 2

    draw_silkscreen_rect(footprint, bx0, by0, bx1, by1, larg_silk)
    draw_fab_rect(footprint, bx0, by0, bx1, by1, larg_fab)

    # --- Textos ---
    add_reference_text(footprint, nome, 0, by0, thickness=larg_silk)
    add_value_text(footprint, nome, 0, by1, thickness=larg_fab)

    # --- Courtyard ---
    draw_courtyard(footprint, bx0, by0, bx1, by1, margin=margem_cy)

    # --- Marcador pino A1 (canto superior-esquerdo) ---
    a1_x = grid_x0
    a1_y = grid_y0
    draw_pin1_marker(footprint, bx0 - 0.3, by0 - 0.3,
                     style='dot', size=0.6, line_width=larg_silk)

    # --- Pads SMD circulares ---
    # Overrides são endereçados pelo nome da bola ("A1"), não por índice.
    override_map = build_override_map(dados, pad_diam, pad_diam)
    n_pads = 0
    for row in range(linhas):
        row_lbl = _row_label(row)
        for col in range(colunas):
            pin_name = f"{row_lbl}{col + 1}"
            if pin_name in excluir:
                continue

            px = grid_x0 + col * pitch
            py = grid_y0 + row * pitch

            w, h = override_map.get(pin_name, (pad_diam, pad_diam))
            add_smd_pad(footprint, pin_name, px, py, w, h,
                        shape=Pad.SHAPE_CIRCLE if w == h else Pad.SHAPE_OVAL)
            n_pads += 1

    # --- Modelo 3D ---
    add_3d_model(footprint, modelo_3d, dados=dados, nome_padrao=nome)

    # --- Salvar ---
    save_footprint(footprint, caminho_saida, v6=True, attr='smd', dados=dados)

    log.info("  [Footprint v2 bga] %s  |  %d balls (%dx%d, excl=%d)",
             nome, n_pads, linhas, colunas, len(excluir))
    log.info("  [Footprint v2 bga] Arquivo: %s", caminho_saida)


# =============================================================================
# Registro de padrões e dispatcher principal
# =============================================================================

_PADROES = {
    'axial_pth':  _gerar_axial_pth,
    'radial_pth': _gerar_radial_pth,
    'dual_pth':   _gerar_dual_pth,
    'dual_smd':   _gerar_dual_smd,
    'quad_smd':   _gerar_quad_smd,
    'single_row_pth': _gerar_single_row_pth,
    'custom':     _gerar_custom,
    'bga':        _gerar_bga,
}

# Mapeamento tipo (v1) → padrão (v2) para compatibilidade
_TIPO_PARA_PADRAO = {
    'resistor_pth':    'axial_pth',
    'diodo_pth':       'axial_pth',
    'led_pth':         'axial_pth',
    'capacitor_pth':   'axial_pth',
    'crystal_hc49':    'axial_pth',
    'transistor_to92': 'radial_pth',
    'ci_dip':          'dual_pth',
    'ci_soic':         'dual_smd',
    'conector_pth':    'single_row_pth',
    'castellated':     'quad_smd',
}


def gerar_footprint_universal(dados, caminho_saida):
    """Dispatcher principal — gera footprint conforme o padrão definido no YAML.

    O campo 'padrao' no dicionário YAML determina qual função geradora usar:
      - axial_pth:  2 pads em linha (resistor, diodo, LED, cristal, capacitor)
      - radial_pth: 3+ pads em cluster (TO-92, TO-220)
      - dual_pth:   2 fileiras de pads PTH (DIP)
      - dual_smd:   2 fileiras de pads SMD (SOIC, SSOP, SOT-23)
      - quad_smd:   4 lados de pads SMD (QFP, QFN, castellated)
      - custom:     pads em posições arbitrárias (antenas, baterias, etc.)

    Compatibilidade: se 'padrao' não existir mas 'tipo' sim, converte
    automaticamente via mapeamento _TIPO_PARA_PADRAO.

    Parâmetros:
        dados        : dicionário com dados do YAML do componente
        caminho_saida: caminho para o arquivo .kicad_mod de saída

    Raises:
        ValueError: se o padrão não for suportado
    """
    padrao = dados.get('padrao')

    # Compatibilidade: tipo (v1) → padrao (v2)
    if not padrao:
        tipo = dados.get('tipo', '')
        padrao = _TIPO_PARA_PADRAO.get(tipo)
        if padrao:
            log.info("  [Footprint v2] tipo '%s' → padrao '%s' (compat)", tipo, padrao)

    fn = _PADROES.get(padrao)
    if fn is None:
        raise ValueError(
            f"Padrão '{padrao}' não suportado. "
            f"Use: {list(_PADROES.keys())}"
        )
    return fn(dados, caminho_saida)


# =============================================================================
# Conveniência: listar padrões disponíveis
# =============================================================================

def listar_padroes():
    """Retorna lista de padrões de pads suportados."""
    return list(_PADROES.keys())
