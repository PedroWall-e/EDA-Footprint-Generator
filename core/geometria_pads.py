# =============================================================================
# geometria_pads.py
# FONTE ÚNICA DE VERDADE para geometria de pads (posição + tamanho).
#
# Usada por:
#   - gerador_footprint.py  (footprint 2D .kicad_mod)
#   - gerador_universal.py  (modelo 3D CadQuery + STEP)
#   - gerador_symbol.py     (símbolo esquemático .kicad_sym — só numeração/lado)
#
# Garante que footprint, 3D e símbolo usem as MESMAS posições e tamanhos,
# eliminando bugs de divergência.
# =============================================================================

from dataclasses import dataclass, field


@dataclass
class PadInfo:
    """Informação completa de um pad individual."""
    num: int          # número do pino (1-indexed)
    x: float          # posição X do centro (mm) — sistema KiCad (Y+ = baixo)
    y: float          # posição Y do centro (mm)
    w: float          # tamanho perpendicular à borda do PCB (largura do pad)
    h: float          # tamanho paralelo à borda do PCB (altura do pad)
    lado: str         # 'esquerdo', 'base', 'direito', 'topo'
    horizontal: bool  # True para pads na base/topo (dimensões trocadas no KiCad)


# =============================================================================
# Funções auxiliares (antes eram duplicadas em gerador_footprint e universal)
# =============================================================================

def _posicoes_centradas(n: int, pitch: float) -> list:
    """
    Retorna 'n' posições centradas em zero, espaçadas por 'pitch'.
    Equivale às antigas posicoes_y() / posicoes_x() duplicadas nos geradores.

    Exemplo: n=3, pitch=2.54 → [-2.54, 0.0, 2.54]
    """
    if n <= 0:
        return []
    comp = (n - 1) * pitch
    p0 = -comp / 2
    return [p0 + i * pitch for i in range(n)]


def _contar_lados(dados: dict) -> tuple:
    """
    Lê a configuração de pinos por lado do YAML.
    Suporta ambos os formatos: 'lados' (novo) e 'por_lado' (legado).

    Retorna: (n_esq, n_base, n_dir, n_topo)
    """
    lados_cfg = dados.get('pinos', {}).get('lados')
    if lados_cfg:
        n_esq  = int(lados_cfg.get('esquerdo', 0))
        n_base = int(lados_cfg.get('base', 0))
        n_dir  = int(lados_cfg.get('direito', 0))
        n_topo = int(lados_cfg.get('topo', 0))
    else:
        # Modo legado: 2 lados simétricos (RM200, STX3, etc.)
        n_por  = int(dados['pinos'].get('por_lado', 0))
        n_esq  = n_por
        n_base = 0
        n_dir  = n_por
        n_topo = 0
    return n_esq, n_base, n_dir, n_topo


def _construir_override_map(dados: dict, pad_w_def: float, pad_h_def: float) -> dict:
    """
    Constrói o mapa de overrides de tamanho (sistema legado).
    Formato no YAML:
        overrides:
          - numeros: [1, 9, 16]
            largura: 2.5
            altura: 1.2

    Retorna: {num: (w, h), ...}
    """
    override_map = {}
    for ov in dados.get('pinos', {}).get('overrides', []):
        w = float(ov.get('largura', pad_w_def))
        h = float(ov.get('altura', pad_h_def))
        for n in ov.get('numeros', []):
            override_map[int(n)] = (w, h)
    return override_map


# =============================================================================
# FUNÇÃO PRINCIPAL — calcular_pads()
# =============================================================================

def calcular_pads(dados: dict) -> list:
    """
    FONTE ÚNICA DE VERDADE para posição e tamanho de todos os pads.

    Resolve em ordem:
      1. Posições regulares (pitch uniforme, centrado em cada borda)
      2. Overrides de tamanho (sistema legado — retrocompatibilidade)
      3. Pinos absolutos (novo — posição e/ou tamanho individual)

    Parâmetros
    ----------
    dados : dict
        Dicionário do YAML do componente.

    Retorna
    -------
    list[PadInfo]
        Lista ordenada de todos os pads com posição e tamanho final.

    Ordem de iteração (padrão KiCad para castellated):
        Esquerdo: cima → baixo
        Base:     esquerda → direita
        Direito:  baixo → cima (reversed)
        Topo:     direita → esquerda (reversed)
    """
    # ── 1. Ler parâmetros do YAML ──
    pitch     = float(dados['pinos']['pitch'])
    pad_w_def = float(dados['pinos']['tamanho_pad']['largura'])   # perpendicular à borda
    pad_h_def = float(dados['pinos']['tamanho_pad']['altura'])    # paralelo à borda
    pcb_w     = float(dados['pcb']['largura'])
    pcb_h     = float(dados['pcb']['altura'])

    # ── 2. Pinos por lado ──
    n_esq, n_base, n_dir, n_topo = _contar_lados(dados)

    # ── 3. Coordenadas das bordas do PCB ──
    x_min = -(pcb_w / 2)
    x_max =  (pcb_w / 2)
    y_min = -(pcb_h / 2)
    y_max =  (pcb_h / 2)

    # ── 4. Construir lista de pads com posições regulares ──
    pads = []
    num = 1

    # Esquerdo: cima → baixo
    if n_esq > 0:
        for y in _posicoes_centradas(n_esq, pitch):
            pads.append(PadInfo(num, x_min, y, pad_w_def, pad_h_def,
                                'esquerdo', False))
            num += 1

    # Base: esquerda → direita
    if n_base > 0:
        for x in _posicoes_centradas(n_base, pitch):
            pads.append(PadInfo(num, x, y_max, pad_w_def, pad_h_def,
                                'base', True))
            num += 1

    # Direito: baixo → cima (reversed)
    if n_dir > 0:
        for y in reversed(_posicoes_centradas(n_dir, pitch)):
            pads.append(PadInfo(num, x_max, y, pad_w_def, pad_h_def,
                                'direito', False))
            num += 1

    # Topo: direita → esquerda (reversed)
    if n_topo > 0:
        for x in reversed(_posicoes_centradas(n_topo, pitch)):
            pads.append(PadInfo(num, x, y_min, pad_w_def, pad_h_def,
                                'topo', True))
            num += 1

    # ── 5. Aplicar overrides de tamanho (sistema legado) ──
    override_map = _construir_override_map(dados, pad_w_def, pad_h_def)
    for pad in pads:
        if pad.num in override_map:
            pad.w, pad.h = override_map[pad.num]

    # ── 6. Aplicar pinos_absolutos (novo — posição + tamanho individual) ──
    pinos_abs = dados.get('pinos', {}).get('pinos_absolutos', {})
    for num_str, cfg in pinos_abs.items():
        idx = int(num_str) - 1
        if 0 <= idx < len(pads):
            # Override de posição
            pos = cfg.get('posicao', {})
            if 'x' in pos:
                pads[idx].x = float(pos['x'])
            if 'y' in pos:
                pads[idx].y = float(pos['y'])
            # Override de tamanho
            pad_cfg = cfg.get('pad', {})
            if 'largura' in pad_cfg:
                pads[idx].w = float(pad_cfg['largura'])
            if 'altura' in pad_cfg:
                pads[idx].h = float(pad_cfg['altura'])

    return pads


# =============================================================================
# Funções auxiliares para consumidores
# =============================================================================

def pad_size_kicad(pad: PadInfo) -> list:
    """
    Retorna [size_x, size_y] no formato KiCad para um pad.
    Para pads horizontais (base/topo), as dimensões são trocadas.
    """
    if pad.horizontal:
        return [pad.h, pad.w]   # swap para pads na base/topo
    return [pad.w, pad.h]

