# =============================================================================
# gerador_footprint.py  [DEPRECATED]
# Módulo de geração de footprint 2D para KiCad (.kicad_mod)
#
# ⚠️  DEPRECATED: Use gerador_footprint_v2.py com o shim tipo→padrao.
#     Este módulo é mantido apenas para compatibilidade reversa.
#     Novos desenvolvimentos devem usar gerador_footprint_v2.py.
#
# Autor: Gerador Automático de Footprints
# Compatibilidade: KiCad 6.x / 7.x / 8.x (formato KiCad)
# =============================================================================

import warnings
warnings.warn(
    "gerador_footprint.py está deprecated. "
    "Use gerador_footprint_v2.py (suporta tipo: via shim automático).",
    DeprecationWarning,
    stacklevel=2,
)

import os
import math
import logging
from geometria_pads import calcular_pads, pad_size_kicad

log = logging.getLogger(__name__)

try:
    from KicadModTree import (
        Footprint,
        FootprintType,
        Text,
        Line,
        Arc,
        Circle,
        Pad,
        Model,
        KicadFileHandler,
    )
    _HAS_FP_TYPE = True
except ImportError:
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
    _HAS_FP_TYPE = False


def _criar_footprint(nome: str, is_smd: bool = False) -> Footprint:
    """Cria Footprint com FootprintType quando disponível (KicadModTree dev)."""
    if _HAS_FP_TYPE:
        ft = FootprintType.SMD if is_smd else FootprintType.THT
        return Footprint(nome, ft)
    return Footprint(nome)


def _salvar_footprint(footprint, caminho_saida: str) -> None:
    """Salva footprint via KicadFileHandler, com pós-processamento v6+ se necessário."""
    handler = KicadFileHandler(footprint)
    if _HAS_FP_TYPE:
        # KicadModTree dev já gera formato v6+ com (footprint ...) nativo
        try:
            handler.writeFile(caminho_saida)
        except PermissionError:
            log.error('Sem permissão para salvar: %s', caminho_saida)
            raise
        except OSError as e:
            log.error('Erro ao salvar footprint: %s (%s)', caminho_saida, e)
            raise
    else:
        # Pós-processamento: converter formato v5 para v6+
        conteudo = handler.serialize() if hasattr(handler, 'serialize') else str(handler)
        if conteudo.lstrip().startswith('(module '):
            import re
            conteudo = conteudo.replace('(module ', '(footprint ', 1)
            conteudo = re.sub(
                r'(\(footprint "[^"]+")',
                r'\1\n  (version 20231120)\n  (generator "DataFrontier")',
                conteudo,
                count=1,
            )
        try:
            with open(caminho_saida, 'w', encoding='utf-8') as f:
                f.write(conteudo)
        except PermissionError:
            log.error('Sem permissão para salvar: %s', caminho_saida)
            raise
        except OSError as e:
            log.error('Erro ao salvar footprint: %s (%s)', caminho_saida, e)
            raise


def gerar_footprint_castellated(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint para módulo SMD com furos castelados.

    Suporta:
      • 2 lados  (modo legado  — usa pinos.por_lado)
      • 4 lados  (modo novo    — usa pinos.lados.{esquerdo, direito, topo, base})
      • Pads de tamanhos distintos via pinos.overrides

    Numeração horária a partir do canto superior-esquerdo:
      Esquerdo  → 1 .. n_esq          (cima → baixo)
      Base      → n_esq+1 .. +n_base  (esq  → dir)
      Direito   → +1 .. +n_dir        (baixo → cima)
      Topo      → +1 .. +n_topo       (dir  → esq)
    """

    # Validação de campos obrigatórios
    campos = ['pcb', 'pinos', 'kicad']
    for c in campos:
        if c not in dados:
            raise ValueError(f'Campo obrigatório ausente no YAML: "{c}"')
    if 'largura' not in dados['pcb'] or 'altura' not in dados['pcb']:
        raise ValueError('pcb.largura e pcb.altura são obrigatórios')
    if 'pitch' not in dados['pinos']:
        raise ValueError('pinos.pitch é obrigatório')
    if 'tamanho_pad' not in dados['pinos']:
        raise ValueError('pinos.tamanho_pad é obrigatório')

    # ── Parâmetros base ───────────────────────────────────────────────────────
    nome_modulo = dados["nome"]
    pcb_largura = float(dados["pcb"]["largura"])
    pcb_altura  = float(dados["pcb"]["altura"])
    pitch       = float(dados["pinos"]["pitch"])
    pad_w_def   = float(dados["pinos"]["tamanho_pad"]["largura"])  # perpendicular à borda
    pad_h_def   = float(dados["pinos"]["tamanho_pad"]["altura"])   # paralelo à borda

    margem_cy = float(dados["margens"]["courtyard"])
    larg_silk = float(dados["margens"]["silkscreen"])
    larg_fab  = float(dados["margens"]["fab_line"])
    modelo_3d = dados["kicad"]["modelo_3d"]
    descricao = dados["kicad"]["descricao"]
    tags      = dados["kicad"]["tags"]

    # ── Posições e tamanhos de pads (fonte única de verdade) ──────────────────
    pads = calcular_pads(dados)

    # Coordenadas das bordas (usadas para silkscreen/fab/courtyard)
    x_min = -(pcb_largura / 2)
    x_max =  (pcb_largura / 2)
    y_min = -(pcb_altura  / 2)
    y_max =  (pcb_altura  / 2)

    # ── Footprint ─────────────────────────────────────────────────────────────
    footprint = Footprint(nome_modulo)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # ── Textos REF / VALUE ────────────────────────────────────────────────────
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text="REF**",
        at=[0, y_min - 1.5], layer="F.SilkS",
        size=[1.0, 1.0], thickness=larg_silk))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome_modulo,
        at=[0, y_max + 1.5], layer="F.Fab",
        size=[1.0, 1.0], thickness=larg_fab))

    # ── Contorno F.SilkS ─────────────────────────────────────────────────────
    for s, e in [([x_min,y_min],[x_max,y_min]), ([x_min,y_max],[x_max,y_max]),
                 ([x_min,y_min],[x_min,y_max]), ([x_max,y_min],[x_max,y_max])]:
        footprint.append(Line(start=s, end=e, layer="F.SilkS", width=larg_silk))

    # ── Contorno F.Fab ────────────────────────────────────────────────────────
    for s, e in [([x_min,y_min],[x_max,y_min]), ([x_min,y_max],[x_max,y_max]),
                 ([x_min,y_min],[x_min,y_max]), ([x_max,y_min],[x_max,y_max])]:
        footprint.append(Line(start=s, end=e, layer="F.Fab", width=larg_fab))

    # ── Courtyard ─────────────────────────────────────────────────────────────
    cy = margem_cy
    for s, e in [([x_min-cy,y_min-cy],[x_max+cy,y_min-cy]),
                 ([x_min-cy,y_max+cy],[x_max+cy,y_max+cy]),
                 ([x_min-cy,y_min-cy],[x_min-cy,y_max+cy]),
                 ([x_max+cy,y_min-cy],[x_max+cy,y_max+cy])]:
        footprint.append(Line(start=s, end=e, layer="F.CrtYd", width=0.05))

    # ── Marcador pino 1 ───────────────────────────────────────────────────────
    if pads:
        px1, py1 = pads[0].x, pads[0].y
        mx = px1 - (pad_w_def * 0.6 if not pads[0].horizontal else 0)
        my = py1
        footprint.append(Line(start=[mx-0.5, my-0.5], end=[mx-0.5, my+0.5],
                               layer="F.SilkS", width=larg_silk))
        footprint.append(Line(start=[mx-0.5, my-0.5], end=[mx,     my-0.5],
                               layer="F.SilkS", width=larg_silk))

    # ── Pads ──────────────────────────────────────────────────────────────────
    for pad in pads:
        footprint.append(Pad(
            number=pad.num,
            type=Pad.TYPE_SMT,
            shape=Pad.SHAPE_RECT,
            at=[pad.x, pad.y],
            size=pad_size_kicad(pad),
            layers=["F.Cu", "F.Paste", "F.Mask"],
        ))

    # ── Modelo 3D ─────────────────────────────────────────────────────────────
    footprint.append(Model(
        filename="${KIPRJMOD}/" + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    # ── Salvar ────────────────────────────────────────────────────────────────
    _salvar_footprint(footprint, caminho_saida)

    log.info("  [Footprint] Arquivo gerado: %s", caminho_saida)
    log.info("  [Footprint] %d pads", len(pads))
    log.info("  [Footprint] Dimensoes: %s mm x %s mm", pcb_largura, pcb_altura)



# =============================================================================
# Gerador: Diodo PTH axial (DO-35, DO-41, DO-204AL, etc.)
# =============================================================================
def gerar_footprint_diodo_pth(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para diodos axiais PTH (through-hole).
    Pinos: 1 = Anodo, 2 = Catodo.
    Orientacao: horizontal, Anodo (pino 1) a esquerda.
    """

    nome          = dados['nome']
    espacamento   = float(dados['pinos']['espacamento'])     # distancia entre centros dos pads
    pad_diam      = float(dados['pinos']['diametro_pad'])    # diametro externo do pad
    furo_diam     = float(dados['pinos']['diametro_furo'])   # diametro do furo (drill)
    corpo_comp    = float(dados['corpo']['comprimento'])     # comprimento do corpo
    corpo_diam    = float(dados['corpo']['diametro'])        # diametro do corpo
    margem_cy     = float(dados['margens']['courtyard'])
    larg_silk     = float(dados['margens']['silkscreen'])
    larg_fab      = float(dados['margens']['fab_line'])
    modelo_3d     = dados['kicad']['modelo_3d']
    descricao     = dados['kicad']['descricao']
    tags          = dados['kicad']['tags']

    # Posicoes
    x_anodo   = -espacamento / 2    # pino 1 (Anodo) a esquerda
    x_catodo  =  espacamento / 2    # pino 2 (Catodo) a direita
    corpo_r   = corpo_diam / 2      # raio do corpo
    corpo_x0  = -corpo_comp / 2     # inicio do corpo
    corpo_x1  =  corpo_comp / 2     # fim do corpo

    # Espessura da banda do catodo (marca de polaridade)
    banda_larg = max(0.6, corpo_comp * 0.12)

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos de referencia e valor ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, -(corpo_r + 1.5)],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_r + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.Fab: contorno real do corpo (retangulo arredondado aproximado) ---
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x1, -corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0,  corpo_r], end=[corpo_x1,  corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x0,  corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, -corpo_r], end=[corpo_x1,  corpo_r], layer='F.Fab', width=larg_fab))
    # Banda do catodo na F.Fab
    bx = corpo_x1 - banda_larg
    footprint.append(Line(start=[bx, -corpo_r], end=[bx, corpo_r], layer='F.Fab', width=larg_fab))

    # --- F.SilkS: silkscreen do corpo ---
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x1 - banda_larg, -corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0,  corpo_r], end=[corpo_x1 - banda_larg,  corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x0,  corpo_r], layer='F.SilkS', width=larg_silk))
    # Banda do catodo (bloco preenchido via duas linhas)
    footprint.append(Line(start=[corpo_x1 - banda_larg, -corpo_r], end=[corpo_x1, -corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1 - banda_larg,  corpo_r], end=[corpo_x1,  corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1 - banda_larg, -corpo_r], end=[corpo_x1 - banda_larg, corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1, -corpo_r], end=[corpo_x1,  corpo_r], layer='F.SilkS', width=larg_silk))
    # Linha catodo larga (marca visual)
    for dy in [-corpo_r * 0.5, 0, corpo_r * 0.5]:
        footprint.append(Line(
            start=[corpo_x1 - banda_larg * 0.6, dy],
            end=[corpo_x1 - banda_larg * 0.1,  dy],
            layer='F.SilkS', width=larg_silk * 2
        ))

    # Leads (fios do anodo e catodo ate a borda do corpo)
    footprint.append(Line(start=[x_anodo, 0], end=[corpo_x0, 0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[x_catodo, 0], end=[corpo_x1, 0], layer='F.Fab', width=larg_fab))

    # --- F.CrtYd: courtyard ---
    cy_x0 = x_anodo   - pad_diam / 2 - margem_cy
    cy_x1 = x_catodo  + pad_diam / 2 + margem_cy
    cy_y0 = -corpo_r - margem_cy
    cy_y1 =  corpo_r + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    # Pino 1: Anodo — pad quadrado (convencao KiCad para pino 1)
    footprint.append(Pad(
        number=1,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_RECT,
        at=[x_anodo, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))
    # Pino 2: Catodo — pad circular
    footprint.append(Pad(
        number=2,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_CIRCLE,
        at=[x_catodo, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)

    log.info("  [Footprint PTH] %s  |  espacamento=%smm  |  furo=%smm", nome, espacamento, furo_diam)
    log.info("  [Footprint PTH] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: Resistor PTH axial (corpo cilíndrico sem banda de polaridade)
# =============================================================================
def gerar_footprint_resistor_pth(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para resistores axiais PTH.
    Semelhante ao diodo PTH, mas sem banda de catodo no corpo.
    O corpo usa uma linha de ondulação (zigzag) no F.Fab para indicar resistência.
    Pino 1 é quadrado, pino 2 é circular.
    """

    nome        = dados['nome']
    espacamento = float(dados['pinos']['espacamento'])
    pad_diam    = float(dados['pinos']['diametro_pad'])
    furo_diam   = float(dados['pinos']['diametro_furo'])
    corpo_comp  = float(dados['corpo']['comprimento'])
    corpo_diam  = float(dados['corpo']['diametro'])
    margem_cy   = float(dados['margens']['courtyard'])
    larg_silk   = float(dados['margens']['silkscreen'])
    larg_fab    = float(dados['margens']['fab_line'])
    modelo_3d   = dados['kicad']['modelo_3d']
    descricao   = dados['kicad']['descricao']
    tags        = dados['kicad']['tags']

    x_pin1   = -espacamento / 2
    x_pin2   =  espacamento / 2
    corpo_r  = corpo_diam / 2
    corpo_x0 = -corpo_comp / 2
    corpo_x1 =  corpo_comp / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, -(corpo_r + 1.5)],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_r + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.Fab: contorno do corpo (retângulo) sem banda ---
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x1, -corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0,  corpo_r], end=[corpo_x1,  corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x0,  corpo_r], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, -corpo_r], end=[corpo_x1,  corpo_r], layer='F.Fab', width=larg_fab))

    # --- F.Fab: ondulação (zigzag) central indicando resistor ---
    n_dentes = 4
    amp      = corpo_r * 0.55
    dx       = corpo_comp / (n_dentes * 2)
    cx       = corpo_x0
    cy       = 0
    toggle   = 1
    for _ in range(n_dentes * 2):
        nx = cx + dx
        ny = amp * toggle
        footprint.append(Line(start=[cx, cy], end=[nx, ny], layer='F.Fab', width=larg_fab))
        cx     = nx
        cy     = ny
        toggle = -toggle
    footprint.append(Line(start=[cx, cy], end=[corpo_x1, 0], layer='F.Fab', width=larg_fab))

    # --- F.SilkS: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x1, -corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0,  corpo_r], end=[corpo_x1,  corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, -corpo_r], end=[corpo_x0,  corpo_r], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1, -corpo_r], end=[corpo_x1,  corpo_r], layer='F.SilkS', width=larg_silk))

    # --- Leads ---
    footprint.append(Line(start=[x_pin1, 0], end=[corpo_x0, 0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[x_pin2, 0], end=[corpo_x1, 0], layer='F.Fab', width=larg_fab))

    # --- Courtyard ---
    cy_x0 = x_pin1  - pad_diam / 2 - margem_cy
    cy_x1 = x_pin2  + pad_diam / 2 + margem_cy
    cy_y0 = -corpo_r - margem_cy
    cy_y1 =  corpo_r + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT: pino 1 quadrado, pino 2 circular ---
    footprint.append(Pad(
        number=1,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_RECT,
        at=[x_pin1, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))
    footprint.append(Pad(
        number=2,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_CIRCLE,
        at=[x_pin2, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint Resistor PTH] %s  |  espacamento=%smm", nome, espacamento)
    log.info("  [Footprint Resistor PTH] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: CI DIP dual in-line THT
# =============================================================================
def gerar_footprint_ci_dip(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para CIs em encapsulamento DIP (through-hole).
    Numeração KiCad: pino 1 = top-left, desce pelo lado esquerdo,
    depois do pino N/2 sobe pelo lado direito (sentido horário).
    Pino 1 é quadrado; demais circulares.
    """
    nome        = dados['nome']
    total       = int(dados['pinos']['total'])
    pitch       = float(dados['pinos']['pitch'])
    pad_diam    = float(dados['pinos']['diametro_pad'])
    furo_diam   = float(dados['pinos']['diametro_furo'])
    corpo_larg  = float(dados['corpo']['largura'])
    corpo_comp  = float(dados['corpo']['comprimento'])
    afastamento = float(dados['corpo']['afastamento_colunas'])
    margem_cy   = float(dados['margens']['courtyard'])
    larg_silk   = float(dados['margens']['silkscreen'])
    larg_fab    = float(dados['margens']['fab_line'])
    modelo_3d   = dados['kicad']['modelo_3d']
    descricao   = dados['kicad']['descricao']
    tags        = dados['kicad']['tags']

    meio        = total // 2
    # Y do pino 1: topo do grupo esquerdo
    y_inicio    = -(meio - 1) * pitch / 2

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
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, corpo_y0 - 1.5],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_y1 + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.Fab: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))

    # --- F.SilkS: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))

    # --- F.SilkS: marcador de pino 1 (arco/chanfro no canto superior esquerdo) ---
    arco_r = 1.0
    # Pequeno arco simulado com duas linhas em L no canto superior esquerdo do corpo
    footprint.append(Line(
        start=[corpo_x0, corpo_y0 + arco_r],
        end=[corpo_x0 + arco_r, corpo_y0],
        layer='F.SilkS', width=larg_silk,
    ))

    # --- Courtyard ---
    cy_x0 = x_esq - pad_diam / 2 - margem_cy
    cy_x1 = x_dir + pad_diam / 2 + margem_cy
    cy_y0 = y_inicio        - pad_diam / 2 - margem_cy
    cy_y1 = y_inicio + (meio - 1) * pitch + pad_diam / 2 + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    # Lado esquerdo: pinos 1..meio (top → bottom)
    for i in range(meio):
        num  = i + 1
        py   = y_inicio + i * pitch
        shp  = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        footprint.append(Pad(
            number=num, type=Pad.TYPE_THT, shape=shp,
            at=[x_esq, py], size=[pad_diam, pad_diam],
            drill=furo_diam, layers=['*.Cu', '*.Mask'],
        ))
    # Lado direito: pinos meio+1..total (bottom → top)
    for i in range(meio):
        num = meio + 1 + i
        py  = y_inicio + (meio - 1 - i) * pitch
        footprint.append(Pad(
            number=num, type=Pad.TYPE_THT, shape=Pad.SHAPE_CIRCLE,
            at=[x_dir, py], size=[pad_diam, pad_diam],
            drill=furo_diam, layers=['*.Cu', '*.Mask'],
        ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint CI DIP] %s  |  %d pinos  |  pitch=%smm", nome, total, pitch)
    log.info("  [Footprint CI DIP] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: CI SOIC (SMD)
# =============================================================================
def gerar_footprint_ci_soic(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para CIs em encapsulamento SOIC (SMD).
    Mesma numeração do DIP mas com pads SMD retangulares.
    Pinos 1..N/2 em X=-afastamento/2, de cima para baixo.
    Pinos N/2+1..N em X=+afastamento/2, de baixo para cima.
    """
    nome        = dados['nome']
    total       = int(dados['pinos']['total'])
    pitch       = float(dados['pinos']['pitch'])
    pad_w       = float(dados['pinos']['tamanho_pad']['largura'])
    pad_h       = float(dados['pinos']['tamanho_pad']['altura'])
    corpo_larg  = float(dados['corpo']['largura'])
    corpo_comp  = float(dados['corpo']['comprimento'])
    afastamento = float(dados['corpo']['afastamento_colunas'])
    margem_cy   = float(dados['margens']['courtyard'])
    larg_silk   = float(dados['margens']['silkscreen'])
    larg_fab    = float(dados['margens']['fab_line'])
    modelo_3d   = dados['kicad']['modelo_3d']
    descricao   = dados['kicad']['descricao']
    tags        = dados['kicad']['tags']

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
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, corpo_y0 - 1.5],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_y1 + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.Fab: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))

    # --- F.SilkS: contorno do corpo (exceto lados com pads) ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))

    # --- F.SilkS: marcador de pino 1 (chanfro no canto superior esquerdo) ---
    arco_r = 0.5
    footprint.append(Line(
        start=[corpo_x0, corpo_y0 + arco_r],
        end=[corpo_x0 + arco_r, corpo_y0],
        layer='F.SilkS', width=larg_silk,
    ))

    # --- Courtyard ---
    cy_x0 = x_esq - pad_w / 2 - margem_cy
    cy_x1 = x_dir + pad_w / 2 + margem_cy
    cy_y0 = y_inicio        - pad_h / 2 - margem_cy
    cy_y1 = y_inicio + (meio - 1) * pitch + pad_h / 2 + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads SMD ---
    # Lado esquerdo: pinos 1..meio (top → bottom)
    for i in range(meio):
        num = i + 1
        py  = y_inicio + i * pitch
        footprint.append(Pad(
            number=num, type=Pad.TYPE_SMT, shape=Pad.SHAPE_RECT,
            at=[x_esq, py], size=[pad_w, pad_h],
            layers=['F.Cu', 'F.Paste', 'F.Mask'],
        ))
    # Lado direito: pinos meio+1..total (bottom → top)
    for i in range(meio):
        num = meio + 1 + i
        py  = y_inicio + (meio - 1 - i) * pitch
        footprint.append(Pad(
            number=num, type=Pad.TYPE_SMT, shape=Pad.SHAPE_RECT,
            at=[x_dir, py], size=[pad_w, pad_h],
            layers=['F.Cu', 'F.Paste', 'F.Mask'],
        ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint CI SOIC] %s  |  %d pinos  |  pitch=%smm", nome, total, pitch)
    log.info("  [Footprint CI SOIC] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: Conector PTH 1 fileira (header)
# =============================================================================
def gerar_footprint_conector_pth(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para conectores de 1 fileira PTH (ex: header 2.54mm).
    Pinos em linha horizontal (Y=0), pitch no eixo X.
    Pino 1 à esquerda e quadrado; demais circulares.
    """
    nome      = dados['nome']
    total     = int(dados['pinos']['total'])
    pitch     = float(dados['pinos']['pitch'])
    pad_diam  = float(dados['pinos']['diametro_pad'])
    furo_diam = float(dados['pinos']['diametro_furo'])
    margem_cy = float(dados['margens']['courtyard'])
    larg_silk = float(dados['margens']['silkscreen'])
    larg_fab  = float(dados['margens']['fab_line'])
    modelo_3d = dados['kicad']['modelo_3d']
    descricao = dados['kicad']['descricao']
    tags      = dados['kicad']['tags']

    # Comprimento total entre centros dos pads extremos
    comprimento = (total - 1) * pitch
    x_inicio    = -comprimento / 2

    # Dimensões do corpo (caixa que envolve todos os pinos)
    corpo_x0 = x_inicio    - pitch / 2
    corpo_x1 = x_inicio + comprimento + pitch / 2
    corpo_y0 = -pitch / 2
    corpo_y1 =  pitch / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, corpo_y0 - 1.5],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_y1 + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.Fab: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))

    # --- F.SilkS: contorno do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))

    # --- F.SilkS: triângulo indicador de pino 1 à esquerda ---
    t_x = corpo_x0 - 0.5
    footprint.append(Line(
        start=[t_x, corpo_y0], end=[t_x, corpo_y1],
        layer='F.SilkS', width=larg_silk,
    ))

    # --- Courtyard ---
    cy_x0 = corpo_x0 - margem_cy
    cy_x1 = corpo_x1 + margem_cy
    cy_y0 = corpo_y0 - margem_cy
    cy_y1 = corpo_y1 + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    for i in range(total):
        num = i + 1
        px  = x_inicio + i * pitch
        shp = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        footprint.append(Pad(
            number=num, type=Pad.TYPE_THT, shape=shp,
            at=[px, 0], size=[pad_diam, pad_diam],
            drill=furo_diam, layers=['*.Cu', '*.Mask'],
        ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint Conector PTH] %s  |  %d pinos  |  pitch=%smm", nome, total, pitch)
    log.info("  [Footprint Conector PTH] Arquivo: %s", caminho_saida)


# =============================================================================
# Utilitário interno: círculo aproximado por N segmentos de linha
# =============================================================================
def _circulo_silkscreen(footprint, cx, cy, r, layer, larg, n_segs=16):
    """Desenha um círculo aproximado por n_segs segmentos de Line."""
    for i in range(n_segs):
        a0 = 2 * math.pi * i / n_segs
        a1 = 2 * math.pi * (i + 1) / n_segs
        footprint.append(Line(
            start=[cx + r * math.cos(a0), cy + r * math.sin(a0)],
            end=[cx + r * math.cos(a1), cy + r * math.sin(a1)],
            layer=layer, width=larg
        ))


# =============================================================================
# Gerador: LED PTH 5mm
# =============================================================================
def gerar_footprint_led_pth(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para LED PTH de 5mm.
    Pino 1 = Anodo (quadrado), Pino 2 = Catodo (circular).
    Corpo visto de cima: círculo com marca de catodo no lado direito.
    """

    nome      = dados['nome']
    espacamento = float(dados['pinos']['espacamento'])
    pad_diam  = float(dados['pinos']['diametro_pad'])
    furo_diam = float(dados['pinos']['diametro_furo'])
    corpo_diam = float(dados['corpo']['diametro'])
    margem_cy = float(dados['margens']['courtyard'])
    larg_silk = float(dados['margens']['silkscreen'])
    larg_fab  = float(dados['margens']['fab_line'])
    modelo_3d = dados['kicad']['modelo_3d']
    descricao = dados['kicad']['descricao']
    tags      = dados['kicad']['tags']

    x_anodo  = -espacamento / 2
    x_catodo =  espacamento / 2
    corpo_r  =  corpo_diam / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, -(corpo_r + 1.5)],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_r + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.SilkS: círculo do corpo (16 segmentos) ---
    _circulo_silkscreen(footprint, 0, 0, corpo_r, 'F.SilkS', larg_silk)
    # Marca do catodo: linha vertical no lado direito do círculo
    footprint.append(Line(
        start=[corpo_r, -corpo_r * 0.5],
        end=[corpo_r,  corpo_r * 0.5],
        layer='F.SilkS', width=larg_silk,
    ))

    # --- F.Fab: círculo do corpo ---
    _circulo_silkscreen(footprint, 0, 0, corpo_r, 'F.Fab', larg_fab)

    # --- F.CrtYd: courtyard (quadrado envolvendo o círculo) ---
    cy = corpo_r + margem_cy
    footprint.append(Line(start=[-cy, -cy], end=[cy, -cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[-cy,  cy], end=[cy,  cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[-cy, -cy], end=[-cy, cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[ cy, -cy], end=[ cy, cy], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    # Pino 1: Anodo — pad quadrado
    footprint.append(Pad(
        number=1,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_RECT,
        at=[x_anodo, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))
    # Pino 2: Catodo — pad circular
    footprint.append(Pad(
        number=2,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_CIRCLE,
        at=[x_catodo, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint LED PTH] %s | d=%smm | esp=%smm", nome, corpo_diam, espacamento)
    log.info("  [Footprint LED PTH] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: Capacitor eletrolítico radial PTH
# =============================================================================
def gerar_footprint_capacitor_pth(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para capacitor eletrolítico radial PTH.
    Pino 1 = positivo (quadrado), Pino 2 = negativo (circular).
    Corpo visto de cima: círculo com marca de polaridade negativa.
    """

    nome       = dados['nome']
    espacamento = float(dados['pinos']['espacamento'])
    pad_diam   = float(dados['pinos']['diametro_pad'])
    furo_diam  = float(dados['pinos']['diametro_furo'])
    corpo_diam = float(dados['corpo']['diametro'])
    margem_cy  = float(dados['margens']['courtyard'])
    larg_silk  = float(dados['margens']['silkscreen'])
    larg_fab   = float(dados['margens']['fab_line'])
    modelo_3d  = dados['kicad']['modelo_3d']
    descricao  = dados['kicad']['descricao']
    tags       = dados['kicad']['tags']

    corpo_r = corpo_diam / 2
    x_pos   = -espacamento / 2   # pino 1 (positivo) à esquerda
    x_neg   =  espacamento / 2   # pino 2 (negativo) à direita

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, -(corpo_r + 1.5)],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_r + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.SilkS: círculo do corpo (16 segmentos) ---
    _circulo_silkscreen(footprint, 0, 0, corpo_r, 'F.SilkS', larg_silk)
    # Faixa de polaridade negativa: linha vertical à direita do círculo
    neg_x = x_neg - pad_diam / 2 - 0.3
    footprint.append(Line(
        start=[neg_x, -0.5],
        end=[neg_x,  0.5],
        layer='F.SilkS', width=larg_silk,
    ))

    # --- F.Fab: círculo do corpo ---
    _circulo_silkscreen(footprint, 0, 0, corpo_r, 'F.Fab', larg_fab)

    # --- F.CrtYd: courtyard (quadrado envolvendo o círculo) ---
    cy = corpo_r + margem_cy
    footprint.append(Line(start=[-cy, -cy], end=[cy, -cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[-cy,  cy], end=[cy,  cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[-cy, -cy], end=[-cy, cy], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[ cy, -cy], end=[ cy, cy], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    # Pino 1: positivo — pad quadrado
    footprint.append(Pad(
        number=1,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_RECT,
        at=[x_pos, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))
    # Pino 2: negativo — pad circular
    footprint.append(Pad(
        number=2,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_CIRCLE,
        at=[x_neg, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint CAP PTH] %s | d=%smm | esp=%smm", nome, corpo_diam, espacamento)
    log.info("  [Footprint CAP PTH] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: Transistor TO-92 (3 pinos, D-shape)
# =============================================================================
def gerar_footprint_transistor_to92(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para transistores em encapsulamento TO-92.
    3 pinos em linha horizontal. Corpo D-shape: plano na frente (y=-corpo_r),
    curvo atrás (semicírculo y >= 0).
    Pino 1 (esquerda) quadrado; pinos 2 e 3 circulares.
    """

    nome      = dados['nome']
    pitch     = float(dados['pinos']['pitch'])
    pad_diam  = float(dados['pinos']['diametro_pad'])
    furo_diam = float(dados['pinos']['diametro_furo'])
    corpo_diam = float(dados['corpo']['diametro'])
    margem_cy = float(dados['margens']['courtyard'])
    larg_silk = float(dados['margens']['silkscreen'])
    larg_fab  = float(dados['margens']['fab_line'])
    modelo_3d = dados['kicad']['modelo_3d']
    descricao = dados['kicad']['descricao']
    tags      = dados['kicad']['tags']

    corpo_r = corpo_diam / 2
    # 3 pinos em linha: pino 1 à esquerda, pino 3 à direita
    x_pins = [-pitch, 0, pitch]

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, -(corpo_r + 1.5)],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_r + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- D-shape helper: linha reta (lado plano) + semicírculo (lado curvo) ---
    def _dshape(footprint, r, layer, larg, n_segs=10):
        """Desenha D-shape: plano em y=-r (frente), curvo em y>=0 (trás)."""
        # Linha reta (lado plano) em y = -r
        footprint.append(Line(
            start=[-r, -r], end=[r, -r],
            layer=layer, width=larg,
        ))
        # Semicírculo do ângulo 180° (pi) a 360° (2*pi): y >= 0
        for i in range(n_segs):
            a0 = math.pi + math.pi * i / n_segs
            a1 = math.pi + math.pi * (i + 1) / n_segs
            footprint.append(Line(
                start=[r * math.cos(a0), r * math.sin(a0)],
                end=[r * math.cos(a1), r * math.sin(a1)],
                layer=layer, width=larg,
            ))

    # --- F.SilkS: D-shape ---
    _dshape(footprint, corpo_r, 'F.SilkS', larg_silk)

    # --- F.Fab: D-shape ---
    _dshape(footprint, corpo_r, 'F.Fab', larg_fab)

    # --- F.CrtYd: bbox do D-shape + pinos + margem ---
    cy_x0 = x_pins[0]  - pad_diam / 2 - margem_cy
    cy_x1 = x_pins[-1] + pad_diam / 2 + margem_cy
    cy_y0 = -corpo_r - margem_cy
    cy_y1 =  corpo_r + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    for i, xp in enumerate(x_pins):
        num = i + 1
        shp = Pad.SHAPE_RECT if num == 1 else Pad.SHAPE_CIRCLE
        footprint.append(Pad(
            number=num,
            type=Pad.TYPE_THT,
            shape=shp,
            at=[xp, 0],
            size=[pad_diam, pad_diam],
            drill=furo_diam,
            layers=['*.Cu', '*.Mask'],
        ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint TO-92] %s | 3 pinos | pitch=%smm", nome, pitch)
    log.info("  [Footprint TO-92] Arquivo: %s", caminho_saida)


# =============================================================================
# Gerador: Cristal HC-49 (2 pinos, corpo retangular horizontal)
# =============================================================================
def gerar_footprint_crystal_hc49(dados: dict, caminho_saida: str) -> None:
    """
    Gera footprint .kicad_mod para cristais em encapsulamento HC-49.
    Corpo retangular horizontal. 2 pinos simétricos.
    Pino 1 quadrado, Pino 2 circular.
    """
    nome       = dados['nome']
    corpo_larg = float(dados['corpo']['largura'])
    corpo_comp = float(dados['corpo']['comprimento'])
    espacamento = float(dados['pinos']['espacamento'])
    pad_diam   = float(dados['pinos']['diametro_pad'])
    furo_diam  = float(dados['pinos']['diametro_furo'])
    margem_cy  = float(dados['margens']['courtyard'])
    larg_silk  = float(dados['margens']['silkscreen'])
    larg_fab   = float(dados['margens']['fab_line'])
    modelo_3d  = dados['kicad']['modelo_3d']
    descricao  = dados['kicad']['descricao']
    tags       = dados['kicad']['tags']

    x_pin1 = -espacamento / 2
    x_pin2 =  espacamento / 2

    # Corpo retangular: largura no eixo X, comprimento no eixo Y
    corpo_x0 = -corpo_larg / 2
    corpo_x1 =  corpo_larg / 2
    corpo_y0 = -corpo_comp / 2
    corpo_y1 =  corpo_comp / 2

    footprint = Footprint(nome)
    footprint.setDescription(descricao)
    footprint.setTags(tags)

    # --- Textos ---
    footprint.append(Text(
        type=Text.TYPE_REFERENCE, text='REF**',
        at=[0, corpo_y0 - 1.5],
        layer='F.SilkS', size=[1.0, 1.0], thickness=larg_silk,
    ))
    footprint.append(Text(
        type=Text.TYPE_VALUE, text=nome,
        at=[0, corpo_y1 + 1.5],
        layer='F.Fab', size=[1.0, 1.0], thickness=larg_fab,
    ))

    # --- F.SilkS: retângulo do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.SilkS', width=larg_silk))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.SilkS', width=larg_silk))

    # --- F.Fab: retângulo do corpo ---
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x1, corpo_y0], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y1], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x0, corpo_y0], end=[corpo_x0, corpo_y1], layer='F.Fab', width=larg_fab))
    footprint.append(Line(start=[corpo_x1, corpo_y0], end=[corpo_x1, corpo_y1], layer='F.Fab', width=larg_fab))

    # --- F.CrtYd: retângulo + pads + margem ---
    cy_x0 = min(corpo_x0, x_pin1 - pad_diam / 2) - margem_cy
    cy_x1 = max(corpo_x1, x_pin2 + pad_diam / 2) + margem_cy
    cy_y0 = corpo_y0 - margem_cy
    cy_y1 = corpo_y1 + margem_cy
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x1, cy_y0], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y1], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x0, cy_y0], end=[cy_x0, cy_y1], layer='F.CrtYd', width=0.05))
    footprint.append(Line(start=[cy_x1, cy_y0], end=[cy_x1, cy_y1], layer='F.CrtYd', width=0.05))

    # --- Pads THT ---
    # Pino 1: quadrado
    footprint.append(Pad(
        number=1,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_RECT,
        at=[x_pin1, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))
    # Pino 2: circular
    footprint.append(Pad(
        number=2,
        type=Pad.TYPE_THT,
        shape=Pad.SHAPE_CIRCLE,
        at=[x_pin2, 0],
        size=[pad_diam, pad_diam],
        drill=furo_diam,
        layers=['*.Cu', '*.Mask'],
    ))

    # --- Modelo 3D ---
    footprint.append(Model(
        filename='${KIPRJMOD}/' + modelo_3d,
        at=[0, 0, 0], scale=[1, 1, 1], rotate=[0, 0, 0],
    ))

    _salvar_footprint(footprint, caminho_saida)
    log.info("  [Footprint Crystal] %s | %sx%smm | esp=%smm", nome, corpo_larg, corpo_comp, espacamento)
    log.info("  [Footprint Crystal] Arquivo: %s", caminho_saida)


# =============================================================================
# Registro de geradores e dispatcher principal
# =============================================================================

_GERADORES_FP = {
    'castellated':     gerar_footprint_castellated,
    'diodo_pth':       gerar_footprint_diodo_pth,
    'resistor_pth':    gerar_footprint_resistor_pth,
    'ci_dip':          gerar_footprint_ci_dip,
    'ci_soic':         gerar_footprint_ci_soic,
    'conector_pth':    gerar_footprint_conector_pth,
    'led_pth':         gerar_footprint_led_pth,
    'capacitor_pth':   gerar_footprint_capacitor_pth,
    'transistor_to92': gerar_footprint_transistor_to92,
    'crystal_hc49':    gerar_footprint_crystal_hc49,
}


def gerar_footprint(dados: dict, caminho_saida: str) -> None:
    """Dispatcher principal — gera footprint 2D conforme o tipo do componente."""
    tipo = dados.get('tipo', '')
    gerador = _GERADORES_FP.get(tipo)
    if not gerador:
        raise ValueError(f"Tipo de componente desconhecido: '{tipo}'. Válidos: {list(_GERADORES_FP)}")
    return gerador(dados, caminho_saida)
