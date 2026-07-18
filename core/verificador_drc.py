"""
Verificador DRC (Design Rule Check) para footprints gerados.

Complementa o validador IPC com regras adicionais focadas em
Design Rule Check (DRC) que verificam a integridade geométrica
e a manufacturabilidade do footprint gerado.

Regras implementadas:
  1. Largura mínima de trace/pad  (>= 0.15mm)
  2. Clearance cobre-borda        (pads >= 0.25mm da borda do corpo)
  3. Expansão de solder mask       (default 0.05mm, aviso se pad pequeno)
  4. Clearance pad-silkscreen      (silk não deve sobrepor pads, >= 0.1mm)
  5. Distância mínima furo-a-furo  (>= 0.5mm entre PTH holes)
  6. Thermal relief                (aviso se thermal pad > 25mm² sem relief)
  7. Aspect ratio de pad           (aviso se largura/altura > 5:1)
  8. Verificação de simetria       (aviso se layout não é simétrico)
"""

import logging
import math
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# =============================================================================
# Resultado DRC
# =============================================================================

@dataclass
class DRCResult:
    """Acumula resultados da verificação DRC."""
    ok: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    info: list = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def __str__(self):
        lines = []
        for e in self.errors:   lines.append(f'ERRO DRC: {e}')
        for w in self.warnings: lines.append(f'AVISO DRC: {w}')
        for i in self.info:     lines.append(f'INFO DRC: {i}')
        return '\n'.join(lines)

    def __repr__(self):
        return (f'DRCResult(ok={self.ok}, '
                f'errors={len(self.errors)}, '
                f'warnings={len(self.warnings)}, '
                f'info={len(self.info)})')


# =============================================================================
# Constantes DRC
# =============================================================================

MIN_TRACE_WIDTH_MM = 0.15        # Regra 1: largura mínima de pad/trace
MIN_COPPER_TO_EDGE_MM = 0.25     # Regra 2: clearance cobre-borda
DEFAULT_MASK_EXPANSION_MM = 0.05 # Regra 3: expansão de solder mask
MIN_MASK_PAD_DIM_MM = 0.20       # Regra 3: pad mínimo para solder mask
MIN_PAD_SILK_CLEARANCE_MM = 0.10 # Regra 4: clearance pad-silkscreen
MIN_DRILL_TO_DRILL_MM = 0.50     # Regra 5: distância mínima furo-a-furo
THERMAL_PAD_AREA_THRESHOLD = 25.0  # Regra 6: área limite (mm²) para thermal relief
MAX_PAD_ASPECT_RATIO = 5.0       # Regra 7: aspect ratio máximo
SYMMETRY_TOLERANCE_MM = 0.01     # Regra 8: tolerância de simetria


# =============================================================================
# Default rules (todas habilitadas)
# =============================================================================

DEFAULT_RULES = {
    'min_trace_width':       True,
    'copper_to_edge':        True,
    'solder_mask_expansion': True,
    'pad_silk_clearance':    True,
    'min_drill_to_drill':    True,
    'thermal_relief':        True,
    'pad_aspect_ratio':      True,
    'symmetry_check':        True,
}


# =============================================================================
# Helpers
# =============================================================================

def _get(dados, *keys, default=None):
    """Navega em dict aninhado com segurança."""
    current = dados
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, default)
        else:
            return default
    return current


def _to_float(val, default=None):
    """Converte valor para float com segurança."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_pad_dims(dados):
    """Retorna (largura, altura) do pad em mm, ou (None, None)."""
    tp = _get(dados, 'pinos', 'tamanho_pad')
    if isinstance(tp, dict):
        w = _to_float(tp.get('largura'))
        h = _to_float(tp.get('altura'))
        return w, h

    # PTH: diâmetro do pad (quadrado/circular)
    diam = _to_float(_get(dados, 'pinos', 'diametro_pad'))
    if diam is not None:
        return diam, diam

    return None, None


def _get_body_dims(dados):
    """Retorna (largura, comprimento) do corpo em mm, ou (None, None)."""
    corpo = dados.get('corpo', {})
    if not isinstance(corpo, dict):
        return None, None
    w = _to_float(corpo.get('largura'))
    h = _to_float(corpo.get('comprimento'))
    return w, h


# =============================================================================
# Regra 1: Largura mínima de trace/pad
# =============================================================================

def _check_min_trace_width(dados, result):
    """Verifica se a menor dimensão de pad >= 0.15mm."""
    pad_w, pad_h = _get_pad_dims(dados)

    checked = False
    if pad_w is not None and pad_w > 0:
        checked = True
        if pad_w < MIN_TRACE_WIDTH_MM:
            result.add_error(
                f'Largura do pad ({pad_w:.3f}mm) < mínimo DRC '
                f'({MIN_TRACE_WIDTH_MM}mm)')
    if pad_h is not None and pad_h > 0:
        checked = True
        if pad_h < MIN_TRACE_WIDTH_MM:
            result.add_error(
                f'Altura do pad ({pad_h:.3f}mm) < mínimo DRC '
                f'({MIN_TRACE_WIDTH_MM}mm)')

    if checked and (pad_w is None or pad_w >= MIN_TRACE_WIDTH_MM) and \
                   (pad_h is None or pad_h >= MIN_TRACE_WIDTH_MM):
        result.add_info(
            f'Largura mínima de pad OK: '
            f'{min(x for x in (pad_w, pad_h) if x is not None):.3f}mm '
            f'>= {MIN_TRACE_WIDTH_MM}mm')


# =============================================================================
# Regra 2: Clearance cobre-borda
# =============================================================================

def _check_copper_to_edge(dados, result):
    """Verifica se pads estão >= 0.25mm da borda do corpo."""
    body_w, body_h = _get_body_dims(dados)
    if body_w is None and body_h is None:
        return

    # Verificar afastamento de colunas (DIP/SOIC/QFP)
    afastamento = _to_float(_get(dados, 'corpo', 'afastamento_colunas'))

    if afastamento is not None and body_w is not None:
        pad_w, _ = _get_pad_dims(dados)
        if pad_w is not None:
            # Borda externa do pad vs borda do corpo
            pad_outer = afastamento / 2 + pad_w / 2
            body_edge = body_w / 2
            clearance = pad_outer - body_edge
            # Se os pads se estendem além do corpo, OK (é normal para ICs)
            # Mas se pads estão DENTRO do corpo, verificar clearance à borda
            if pad_outer < body_edge:
                if (body_edge - pad_outer) < MIN_COPPER_TO_EDGE_MM:
                    result.add_warning(
                        f'Pad está a {body_edge - pad_outer:.3f}mm da borda do '
                        f'corpo — recomendado >= {MIN_COPPER_TO_EDGE_MM}mm')
                    return

    # Verificar pitch ao longo do corpo
    pitch = _to_float(_get(dados, 'pinos', 'pitch'))
    num_pinos = _to_float(_get(dados, 'pinos', 'quantidade'))

    if pitch is not None and num_pinos is not None and body_h is not None:
        num_por_lado = num_pinos / 2
        if num_por_lado > 0:
            span = (num_por_lado - 1) * pitch
            _, pad_h = _get_pad_dims(dados)
            if pad_h is not None:
                pad_extent = span / 2 + pad_h / 2
                body_extent = body_h / 2
                if pad_extent > body_extent:
                    pass  # Pads fora do corpo — normal
                elif (body_extent - pad_extent) < MIN_COPPER_TO_EDGE_MM:
                    result.add_warning(
                        f'Pads estão a {body_extent - pad_extent:.3f}mm '
                        f'da borda do corpo ao longo do comprimento — '
                        f'recomendado >= {MIN_COPPER_TO_EDGE_MM}mm')
                    return

    result.add_info(f'Clearance cobre-borda verificado')


# =============================================================================
# Regra 3: Expansão de solder mask
# =============================================================================

def _check_solder_mask(dados, result):
    """Verifica se pad é grande o suficiente para solder mask."""
    pad_w, pad_h = _get_pad_dims(dados)
    if pad_w is None and pad_h is None:
        return

    mask_expansion = _to_float(
        _get(dados, 'margens', 'solder_mask'), DEFAULT_MASK_EXPANSION_MM)

    dims_to_check = []
    if pad_w is not None:
        dims_to_check.append(('largura', pad_w))
    if pad_h is not None:
        dims_to_check.append(('altura', pad_h))

    has_warning = False
    for dim_name, dim_val in dims_to_check:
        effective = dim_val + 2 * mask_expansion
        if dim_val < MIN_MASK_PAD_DIM_MM:
            result.add_warning(
                f'Pad {dim_name} ({dim_val:.3f}mm) muito pequeno para '
                f'solder mask (expansão {mask_expansion}mm). '
                f'Abertura efetiva: {effective:.3f}mm — pode haver '
                f'problemas de registro.')
            has_warning = True

    if not has_warning:
        result.add_info(
            f'Solder mask expansion OK (expansão={mask_expansion}mm)')


# =============================================================================
# Regra 4: Clearance pad-silkscreen
# =============================================================================

def _check_pad_silk_clearance(dados, result):
    """Estima a folga pad-silkscreen a partir do YAML.

    Estimativa, não veredito: o YAML não diz QUAIS linhas de silk o padrão
    desenha. Medido no arquivo gerado, `ci_dip` desenha o retângulo fechado
    (as linhas verticais em ±largura/2 cruzam os pads), enquanto `dual_smd`
    desenha só as linhas de topo e base — ali a linha vertical que esta regra
    imagina não existe. Por isso o achado sai como AVISO e a prova fica com
    `verificar_drc_arquivo()`, que lê a geometria real.

    `margens.silkscreen` é a ESPESSURA da linha (sai como `(width ...)` no
    .kicad_mod), não um recuo do corpo: a linha é desenhada em ±largura/2 e se
    espalha meia espessura para cada lado.
    """
    silk_width = _to_float(_get(dados, 'margens', 'silkscreen'))
    if silk_width is None:
        return

    corpo = dados.get('corpo', {})
    if not isinstance(corpo, dict):
        return

    body_w = _to_float(corpo.get('largura'))
    afastamento = _to_float(corpo.get('afastamento_colunas'))

    if body_w is None or afastamento is None:
        return

    pad_w, _ = _get_pad_dims(dados)
    if pad_w is None:
        return

    pad_inner_edge = afastamento / 2 - pad_w / 2
    pad_outer_edge = afastamento / 2 + pad_w / 2
    silk_edge = body_w / 2 + silk_width / 2

    # A linha vertical do silk só toca o pad se cair DENTRO do vão do pad.
    # Se ela passa por fora (silk_edge >= pad_outer_edge), os pads estão
    # inteiramente dentro do corpo — caso do box header, onde a subtração
    # ingênua acusava sobreposição inexistente.
    if silk_edge >= pad_outer_edge:
        result.add_info(
            f'Silk fora do vão dos pads (silk={silk_edge:.3f}mm >= '
            f'borda externa do pad={pad_outer_edge:.3f}mm) — sem cruzamento')
        return

    clearance = pad_inner_edge - silk_edge
    if clearance < 0:
        result.add_warning(
            f'Provável silkscreen sobre pads: linha de silk em '
            f'{silk_edge:.3f}mm cai dentro do pad (borda interna '
            f'{pad_inner_edge:.3f}mm, externa {pad_outer_edge:.3f}mm) — '
            f'sobreposição de {abs(clearance):.3f}mm se o padrão desenhar o '
            f'retângulo fechado. Confirme com verificar_drc_arquivo().')
    elif clearance < MIN_PAD_SILK_CLEARANCE_MM:
        result.add_warning(
            f'Clearance pad-silkscreen ({clearance:.3f}mm) < '
            f'recomendado ({MIN_PAD_SILK_CLEARANCE_MM}mm). '
            f'Considere recuar o silkscreen.')
    else:
        result.add_info(
            f'Clearance pad-silk OK: {clearance:.3f}mm >= '
            f'{MIN_PAD_SILK_CLEARANCE_MM}mm')


# =============================================================================
# Regra 5: Distância mínima furo-a-furo
# =============================================================================

def _check_min_drill_to_drill(dados, result):
    """Verifica distância mínima entre furos PTH >= 0.5mm."""
    drill = _to_float(_get(dados, 'pinos', 'diametro_furo'))
    if drill is None:
        return  # Não é PTH

    pitch = _to_float(_get(dados, 'pinos', 'pitch'))
    if pitch is None:
        pitch = _to_float(_get(dados, 'pinos', 'espacamento'))
    if pitch is None:
        return

    # Distância entre bordas dos furos = pitch - diâmetro_furo
    drill_gap = pitch - drill
    if drill_gap < MIN_DRILL_TO_DRILL_MM:
        result.add_error(
            f'Distância entre furos ({drill_gap:.3f}mm) < mínimo DRC '
            f'({MIN_DRILL_TO_DRILL_MM}mm). '
            f'pitch={pitch}mm, furo={drill}mm. '
            f'Risco de fragilidade da PCB entre furos.')
    else:
        result.add_info(
            f'Distância furo-a-furo OK: {drill_gap:.3f}mm >= '
            f'{MIN_DRILL_TO_DRILL_MM}mm')


# =============================================================================
# Regra 6: Thermal relief
# =============================================================================

def _check_thermal_relief(dados, result):
    """Aviso se thermal pad > 25mm² sem thermal relief pattern."""
    # Verificar thermal pad / exposed pad
    thermal = dados.get('thermal_pad', dados.get('exposed_pad', {}))
    if not isinstance(thermal, dict):
        return

    tw = _to_float(thermal.get('largura'))
    th = _to_float(thermal.get('altura') or thermal.get('comprimento'))

    if tw is None or th is None:
        # Tentar tamanho único (quadrado)
        ts = _to_float(thermal.get('tamanho'))
        if ts is not None:
            tw = th = ts
        else:
            return

    area = tw * th
    has_relief = thermal.get('thermal_relief', False)
    has_vias = thermal.get('vias', False) or thermal.get('thermal_vias', False)

    if area > THERMAL_PAD_AREA_THRESHOLD:
        if not has_relief and not has_vias:
            result.add_warning(
                f'Thermal pad grande ({tw:.2f}×{th:.2f}mm = {area:.1f}mm²) '
                f'sem thermal relief ou vias térmicas definidas. '
                f'Considere adicionar thermal_relief: true ou vias térmicas '
                f'para melhorar a soldabilidade.')
        else:
            result.add_info(
                f'Thermal pad {area:.1f}mm² com relief/vias — OK')
    else:
        result.add_info(f'Thermal pad {area:.1f}mm² < limite ({THERMAL_PAD_AREA_THRESHOLD}mm²) — OK')


# =============================================================================
# Regra 7: Aspect ratio de pad
# =============================================================================

def _check_pad_aspect_ratio(dados, result):
    """Aviso se aspect ratio do pad > 5:1."""
    pad_w, pad_h = _get_pad_dims(dados)
    if pad_w is None or pad_h is None:
        return
    if pad_w <= 0 or pad_h <= 0:
        return

    ratio = max(pad_w, pad_h) / min(pad_w, pad_h)

    if ratio > MAX_PAD_ASPECT_RATIO:
        result.add_warning(
            f'Aspect ratio do pad ({pad_w:.3f}×{pad_h:.3f}mm = '
            f'{ratio:.1f}:1) excede {MAX_PAD_ASPECT_RATIO:.0f}:1. '
            f'Pads muito alongados podem ter problemas de soldabilidade.')
    else:
        result.add_info(
            f'Aspect ratio do pad OK: {ratio:.1f}:1 <= '
            f'{MAX_PAD_ASPECT_RATIO:.0f}:1')


# =============================================================================
# Regra 8: Verificação de simetria
# =============================================================================

def _check_symmetry(dados, result):
    """Aviso se o layout de pads não é simétrico para dual/quad packages."""
    tipo = dados.get('tipo', '')
    padrao = dados.get('padrao', '')
    tipo_lower = f'{tipo} {padrao}'.lower()

    # Verificar apenas para pacotes duais/quad
    is_dual = any(k in tipo_lower for k in ['soic', 'dip', 'ssop', 'tssop', 'sop'])
    is_quad = any(k in tipo_lower for k in ['qfp', 'qfn', 'tqfp', 'lqfp'])

    if not is_dual and not is_quad:
        return

    pinos = dados.get('pinos', {})
    if not isinstance(pinos, dict):
        return

    num_pinos = _to_float(pinos.get('quantidade'))
    if num_pinos is None or num_pinos <= 0:
        return
    num_pinos = int(num_pinos)

    if is_dual:
        # Para pacotes duais, número de pinos deve ser par
        if num_pinos % 2 != 0:
            result.add_warning(
                f'Pacote dual ({tipo or padrao}) com número ímpar de '
                f'pinos ({num_pinos}). Layout pode não ser simétrico.')
        else:
            # Verificar se há afastamento de colunas (simetria em X)
            afastamento = _to_float(_get(dados, 'corpo', 'afastamento_colunas'))
            if afastamento is None:
                result.add_warning(
                    f'Pacote dual sem afastamento_colunas definido. '
                    f'Verifique simetria do layout.')
            else:
                result.add_info(
                    f'Simetria dual verificada: {num_pinos} pinos, '
                    f'afastamento={afastamento}mm')

    elif is_quad:
        # Para pacotes quad, número de pinos deve ser divisível por 4
        if num_pinos % 4 != 0:
            result.add_warning(
                f'Pacote quad ({tipo or padrao}) com número de pinos '
                f'({num_pinos}) não divisível por 4. '
                f'Layout pode não ser simétrico.')
        else:
            result.add_info(
                f'Simetria quad verificada: {num_pinos} pinos '
                f'({num_pinos // 4} por lado)')


# =============================================================================
# Mapa de regras
# =============================================================================

_RULE_MAP = {
    'min_trace_width':       _check_min_trace_width,
    'copper_to_edge':        _check_copper_to_edge,
    'solder_mask_expansion': _check_solder_mask,
    'pad_silk_clearance':    _check_pad_silk_clearance,
    'min_drill_to_drill':    _check_min_drill_to_drill,
    'thermal_relief':        _check_thermal_relief,
    'pad_aspect_ratio':      _check_pad_aspect_ratio,
    'symmetry_check':        _check_symmetry,
}


# =============================================================================
# Função principal
# =============================================================================

def verificar_drc(dados: dict, rules: dict = None) -> DRCResult:
    """Executa verificação DRC no componente.

    Args:
        dados: dict com os dados YAML do footprint.
        rules: dict com regras habilitadas/desabilitadas.
               Chaves: nomes das regras (ver DEFAULT_RULES).
               Valores: True (habilitada) ou False (desabilitada).
               Se None, todas as regras são executadas.

    Returns:
        DRCResult com erros, avisos e informações.
    """
    result = DRCResult()

    if not isinstance(dados, dict):
        result.add_error('Dados de entrada não são um dicionário válido')
        return result

    active_rules = dict(DEFAULT_RULES)
    if rules is not None:
        active_rules.update(rules)

    for rule_name, check_fn in _RULE_MAP.items():
        if not active_rules.get(rule_name, True):
            result.add_info(f'Regra "{rule_name}" desabilitada')
            continue
        try:
            check_fn(dados, result)
        except Exception as e:
            result.add_warning(
                f'Erro interno na regra DRC "{rule_name}": {e}')

    # Resumo
    nome = dados.get('nome', '<sem nome>')
    tipo = dados.get('tipo', dados.get('padrao', '<sem tipo>'))
    if result.ok:
        log.info(
            f'DRC OK para "{nome}" ({tipo}): '
            f'{len(result.warnings)} avisos, {len(result.info)} info')
    else:
        log.error(
            f'DRC FALHOU para "{nome}" ({tipo}): '
            f'{len(result.errors)} erros, {len(result.warnings)} avisos')

    return result


# =============================================================================
# DRC sobre o arquivo gerado — geometria real
# =============================================================================

_RE_FP_LINE = re.compile(
    r'\(fp_line\s+\(start\s+(-?[\d.]+)\s+(-?[\d.]+)\)\s+'
    r'\(end\s+(-?[\d.]+)\s+(-?[\d.]+)\)\s+\(layer\s+"?F\.SilkS"?\)')
_RE_PAD = re.compile(
    r'\(pad\s+("([^"]*)"|(\S+))\s+\S+\s+\S+\s+\(at\s+(-?[\d.]+)\s+(-?[\d.]+)'
    r'(?:\s+-?[\d.]+)?\)\s+\(size\s+(-?[\d.]+)\s+(-?[\d.]+)\)')


def _parse_silk_e_pads(conteudo):
    """Lê as linhas de F.SilkS e os pads do .kicad_mod já serializado."""
    silk = [tuple(map(float, m.groups())) for m in _RE_FP_LINE.finditer(conteudo)]
    pads = []
    for m in _RE_PAD.finditer(conteudo):
        numero = m.group(2) if m.group(2) is not None else m.group(3)
        pads.append((numero, float(m.group(4)), float(m.group(5)),
                     float(m.group(6)), float(m.group(7))))
    return silk, pads


def _sobreposicao_segmento_pad(x1, y1, x2, y2, px, py, pw, ph):
    """Comprimento do trecho do segmento que cai dentro do retângulo do pad.

    Só trata segmentos eixo-alinhados — é o que os padrões desenham. Segmento
    diagonal (chanfro do pino 1) retorna None em vez de virar falso negativo
    silencioso disfarçado de zero.
    """
    rx1, rx2 = px - pw / 2, px + pw / 2
    ry1, ry2 = py - ph / 2, py + ph / 2
    if abs(y1 - y2) < 1e-9:
        if not (ry1 < y1 < ry2):
            return 0.0
        return max(0.0, min(max(x1, x2), rx2) - max(min(x1, x2), rx1))
    if abs(x1 - x2) < 1e-9:
        if not (rx1 < x1 < rx2):
            return 0.0
        return max(0.0, min(max(y1, y2), ry2) - max(min(y1, y2), ry1))
    return None


def verificar_drc_arquivo(caminho_kicad_mod, dados=None, rules=None):
    """Executa o DRC sobre o footprint JÁ GERADO, medindo a geometria real.

    Diferente de `verificar_drc(dados)`, que estima pelo YAML, aqui as
    coordenadas são lidas do .kicad_mod. É a única forma de afirmar que o
    silkscreen cruza um pad: o YAML não diz quais linhas o padrão desenha.

    Args:
        caminho_kicad_mod: caminho do .kicad_mod gerado.
        dados: dict do YAML (opcional). Se passado, as regras de
               `verificar_drc()` também rodam, exceto a estimativa
               pad_silk_clearance — aqui ela é medida de verdade.
        rules: mesmo dict de `verificar_drc()`.

    Returns:
        DRCResult. `.ok` False se houver silk sobre pad, pads sobrepostos ou
        modelo 3D comprovadamente ausente.
    """
    result = DRCResult()

    try:
        with open(caminho_kicad_mod, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except OSError as e:
        result.add_error(f'Nao foi possivel ler o footprint gerado: {e}')
        return result

    if dados is not None:
        regras_yaml = dict(rules or {})
        regras_yaml['pad_silk_clearance'] = False
        parcial = verificar_drc(dados, rules=regras_yaml)
        result.errors.extend(parcial.errors)
        result.warnings.extend(parcial.warnings)
        result.info.extend(parcial.info)
        if not parcial.ok:
            result.ok = False

    silk, pads = _parse_silk_e_pads(conteudo)

    # Silk sobre pad — geometria real
    cruzamentos = {}
    for (x1, y1, x2, y2) in silk:
        for (n, px, py, pw, ph) in pads:
            ov = _sobreposicao_segmento_pad(x1, y1, x2, y2, px, py, pw, ph)
            if ov:
                cruzamentos[n] = max(cruzamentos.get(n, 0.0), ov)
    if cruzamentos:
        det = ', '.join(f'{n} ({v:.2f}mm)'
                        for n, v in sorted(cruzamentos.items())[:6])
        mais = (f' e mais {len(cruzamentos) - 6}'
                if len(cruzamentos) > 6 else '')
        result.add_error(
            f'Silkscreen desenhado sobre {len(cruzamentos)} pad(s): '
            f'{det}{mais}. O KiCad acusa isso no DRC da placa; recue ou '
            f'recorte o silk.')
    elif silk and pads:
        result.add_info(
            f'Silkscreen nao cruza pads ({len(silk)} linhas, '
            f'{len(pads)} pads)')

    # Pads sobrepostos — geometria real
    try:
        from footprint_helpers import pad_clearance_report
    except ImportError:
        from core.footprint_helpers import pad_clearance_report
    sobrepostos, curtos = pad_clearance_report(pads)
    for a, b, gap in sobrepostos:
        result.add_error(
            f'Pads {a} e {b} se sobrepoem ({-gap:.3f}mm) — cobre em curto')
    for a, b, gap in curtos:
        result.add_warning(
            f'Folga de {gap:.3f}mm entre os pads {a} e {b} (< 0.2mm)')

    # Modelo 3D órfão
    try:
        from verificador_modelo_3d import verificar_modelo_3d
    except ImportError:
        from core.verificador_modelo_3d import verificar_modelo_3d
    r3d = verificar_modelo_3d(caminho_kicad_mod, dados)
    for ref in r3d.ausentes:
        result.add_error(
            f'Modelo 3D referenciado nao existe: "{ref["caminho_bruto"]}" '
            f'-> {ref["caminho_resolvido"]}')
    for ref in r3d.nao_verificaveis:
        vs = ', '.join(ref['variaveis_nao_resolvidas'])
        result.add_info(
            f'Modelo 3D nao verificavel (variavel ${{{vs}}} nao definida): '
            f'{ref["caminho_bruto"]}')
    for ref in r3d.resolvidos:
        result.add_info(f'Modelo 3D existe: {ref["caminho_resolvido"]}')
    if not r3d.referencias:
        result.add_info('Footprint nao referencia modelo 3D')

    return result
