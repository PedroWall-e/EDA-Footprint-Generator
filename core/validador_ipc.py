"""
Validador IPC-7351B para dados de footprint.

Valida dados YAML de footprint contra os padrões IPC-7351B ANTES da geração,
identificando erros críticos (que impedem geração), avisos (geração continua)
e mensagens informativas.

Checks implementados:
  1. Campos obrigatórios (nome, tipo/padrao)
  2. Annular ring mínimo (PTH, IPC Class 2)
  3. Clearance mínimo entre pads adjacentes
  4. Courtyard mínimo (SMD vs PTH)
  5. Silkscreen sobre pads
  6. Tamanho mínimo de furo
  7. Tamanho mínimo de pad
  8. Pitch vs tamanho de pad (sobreposição)
  9. Campos KiCad obrigatórios
 10. Dimensões do corpo > 0
"""

import logging

log = logging.getLogger(__name__)


# =============================================================================
# Resultado de validação
# =============================================================================

class IPCValidationResult:
    """Acumula erros, avisos e informações da validação IPC."""

    def __init__(self):
        self.errors = []      # Falhas críticas (impede geração)
        self.warnings = []    # Avisos (geração continua)
        self.info = []        # Informações

    @property
    def ok(self):
        """True se não há erros críticos."""
        return len(self.errors) == 0

    def __str__(self):
        lines = []
        for e in self.errors:   lines.append(f'ERRO: {e}')
        for w in self.warnings: lines.append(f'AVISO: {w}')
        for i in self.info:     lines.append(f'INFO: {i}')
        return '\n'.join(lines)

    def __repr__(self):
        return (f'IPCValidationResult('
                f'errors={len(self.errors)}, '
                f'warnings={len(self.warnings)}, '
                f'info={len(self.info)})')


# =============================================================================
# Constantes IPC-7351B
# =============================================================================

# Annular ring mínimo — IPC Class 2 (Standard)
MIN_ANNULAR_RING_MM = 0.15

# Clearance mínimo entre bordas de pads adjacentes
MIN_PAD_CLEARANCE_MM = 0.10

# Courtyard mínimo
MIN_COURTYARD_SMD_MM = 0.25
MIN_COURTYARD_PTH_MM = 0.50

# Tamanho mínimo de furo (fabricação)
MIN_DRILL_MM = 0.20

# Tamanho mínimo de pad em qualquer dimensão
MIN_PAD_DIM_MM = 0.20

# Tipos de componente considerados PTH
_PTH_TYPES = {
    'diodo_pth', 'resistor_pth', 'ci_dip', 'conector_pth',
    'led_pth', 'capacitor_pth', 'transistor_to92', 'crystal_hc49',
}

# Tipos de componente considerados SMD
_SMD_TYPES = {
    'ci_soic', 'castellated', 'ci_qfn', 'ci_tqfp', 'smd',
}


# =============================================================================
# Helpers internos
# =============================================================================

def _get_nested(dados, *keys, default=None):
    """Navega em dict aninhado com segurança."""
    current = dados
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, default)
        else:
            return default
    return current


def _is_pth(dados):
    """Determina se o componente é PTH com base no tipo/padrao."""
    tipo = dados.get('tipo', '')
    padrao = dados.get('padrao', '')
    # PTH explícito
    if tipo in _PTH_TYPES:
        return True
    # Possui furos definidos
    if _get_nested(dados, 'pinos', 'diametro_furo') is not None:
        return True
    # Padrões PTH
    if padrao and any(t in padrao.lower() for t in ['dip', 'to-', 'to92', 'pth', 'tht']):
        return True
    return False


def _is_smd(dados):
    """Determina se o componente é SMD com base no tipo/padrao."""
    tipo = dados.get('tipo', '')
    padrao = dados.get('padrao', '')
    if tipo in _SMD_TYPES:
        return True
    if padrao and any(t in padrao.lower() for t in ['soic', 'smd', 'qfn', 'qfp', 'sot', 'ssop']):
        return True
    # Se tem tamanho_pad mas não tem furo, provável SMD
    if (_get_nested(dados, 'pinos', 'tamanho_pad') is not None and
            _get_nested(dados, 'pinos', 'diametro_furo') is None):
        return True
    return False


# =============================================================================
# Checks individuais
# =============================================================================

def _check_required_fields(dados, result):
    """Check 1: Campos obrigatórios — nome e (tipo ou padrao)."""
    if 'nome' not in dados or not dados['nome']:
        result.errors.append(
            'Campo obrigatório "nome" ausente ou vazio')

    if 'tipo' not in dados and 'padrao' not in dados:
        result.errors.append(
            'Deve existir ao menos "tipo" ou "padrao" para identificar '
            'o tipo de componente')
    elif not dados.get('tipo') and not dados.get('padrao'):
        result.errors.append(
            'Campos "tipo" e "padrao" estão ambos vazios')


def _check_annular_ring(dados, result):
    """Check 2: Annular ring mínimo (PTH, IPC Class 2).

    (diametro_pad - diametro_furo) / 2 >= 0.15mm
    """
    if not _is_pth(dados):
        return

    pad_diam = _get_nested(dados, 'pinos', 'diametro_pad')
    drill_diam = _get_nested(dados, 'pinos', 'diametro_furo')

    if pad_diam is None or drill_diam is None:
        return  # sem dados suficientes para validar

    try:
        pad_diam = float(pad_diam)
        drill_diam = float(drill_diam)
    except (ValueError, TypeError):
        result.errors.append(
            f'diametro_pad ({pad_diam}) ou diametro_furo ({drill_diam}) '
            f'não são numéricos')
        return

    ring = (pad_diam - drill_diam) / 2
    if ring < MIN_ANNULAR_RING_MM:
        result.errors.append(
            f'Annular ring {ring:.3f}mm < mínimo IPC Class 2 '
            f'({MIN_ANNULAR_RING_MM}mm). '
            f'pad={pad_diam}mm, furo={drill_diam}mm. '
            f'Aumente diametro_pad ou reduza diametro_furo.')
    else:
        result.info.append(
            f'Annular ring OK: {ring:.3f}mm >= {MIN_ANNULAR_RING_MM}mm')


def _check_pad_clearance(dados, result):
    """Check 3: Clearance mínimo entre bordas de pads adjacentes >= 0.10mm.

    Usa pitch e tamanho de pad para calcular a distância entre bordas.
    """
    pitch = _get_nested(dados, 'pinos', 'pitch')
    if pitch is None:
        # Tentar espaçamento (componentes axiais)
        pitch = _get_nested(dados, 'pinos', 'espacamento')
    if pitch is None:
        return  # sem pitch, não dá para validar

    try:
        pitch = float(pitch)
    except (ValueError, TypeError):
        return

    # Determinar tamanho do pad ao longo do pitch
    pad_along_pitch = None

    # SMD: tamanho_pad.altura (paralelo ao pitch na maioria dos layouts)
    tp = _get_nested(dados, 'pinos', 'tamanho_pad')
    if isinstance(tp, dict):
        # Para ICs (DIP/SOIC), pads estão ao longo de Y, pitch em Y
        pad_along_pitch = tp.get('altura')

    # PTH: diametro_pad
    if pad_along_pitch is None:
        pad_along_pitch = _get_nested(dados, 'pinos', 'diametro_pad')

    if pad_along_pitch is None:
        return

    try:
        pad_along_pitch = float(pad_along_pitch)
    except (ValueError, TypeError):
        return

    gap = pitch - pad_along_pitch
    if gap < MIN_PAD_CLEARANCE_MM:
        result.errors.append(
            f'Clearance entre pads adjacentes {gap:.3f}mm < mínimo '
            f'{MIN_PAD_CLEARANCE_MM}mm. '
            f'pitch={pitch}mm, pad={pad_along_pitch}mm. '
            f'Pads podem estar se sobrepondo!')
    else:
        result.info.append(
            f'Pad clearance OK: {gap:.3f}mm >= {MIN_PAD_CLEARANCE_MM}mm')


def _check_courtyard(dados, result):
    """Check 4: Courtyard deve existir e ser >= 0.25mm (SMD) ou >= 0.50mm (PTH)."""
    courtyard = _get_nested(dados, 'margens', 'courtyard')

    if courtyard is None:
        result.warnings.append(
            'Courtyard não definido em margens.courtyard. '
            'Recomendado >= 0.25mm (SMD) ou >= 0.50mm (PTH)')
        return

    try:
        courtyard = float(courtyard)
    except (ValueError, TypeError):
        result.errors.append(
            f'margens.courtyard ({courtyard}) não é numérico')
        return

    if _is_pth(dados):
        min_cy = MIN_COURTYARD_PTH_MM
        tipo_str = 'PTH'
    else:
        min_cy = MIN_COURTYARD_SMD_MM
        tipo_str = 'SMD'

    if courtyard < min_cy:
        result.warnings.append(
            f'Courtyard {courtyard}mm < recomendado IPC para {tipo_str} '
            f'({min_cy}mm)')
    else:
        result.info.append(
            f'Courtyard OK: {courtyard}mm >= {min_cy}mm ({tipo_str})')


def _check_silkscreen_on_pads(dados, result):
    """Check 5: Aviso se silkscreen pode sobrepor pads.

    Compara a margem de silkscreen com a extensão dos pads além do corpo.
    """
    silk_margin = _get_nested(dados, 'margens', 'silkscreen')
    if silk_margin is None:
        return

    # Para componentes com corpo e pads que se estendem além
    corpo = dados.get('corpo', {})
    pinos = dados.get('pinos', {})

    if not corpo or not pinos:
        return

    # Verificar em componentes DIP/SOIC onde pads se estendem além do corpo
    largura_corpo = corpo.get('largura')
    afastamento = corpo.get('afastamento_colunas')

    if largura_corpo is not None and afastamento is not None:
        try:
            largura_corpo = float(largura_corpo)
            afastamento = float(afastamento)
            # Se o silkscreen é desenhado na borda do corpo e os pads estão
            # no afastamento, ok. Mas se o corpo é tão largo que toca os pads...
            pad_extent = afastamento / 2

            # Para SMD, verificar se tamanho_pad.largura se estende além
            tp = _get_nested(dados, 'pinos', 'tamanho_pad')
            if isinstance(tp, dict):
                pad_w = float(tp.get('largura', 0))
                pad_inner_edge = afastamento / 2 - pad_w / 2
                silk_edge = largura_corpo / 2
                if silk_edge > pad_inner_edge:
                    result.warnings.append(
                        f'Silkscreen do corpo (±{silk_edge:.2f}mm) pode '
                        f'sobrepor pads (borda interna ±{pad_inner_edge:.2f}mm). '
                        f'Considere recuar o silkscreen.')
        except (ValueError, TypeError):
            pass


def _check_drill_size(dados, result):
    """Check 6: Tamanho mínimo de furo >= 0.20mm (fabricação)."""
    drill = _get_nested(dados, 'pinos', 'diametro_furo')
    if drill is None:
        return

    try:
        drill = float(drill)
    except (ValueError, TypeError):
        result.errors.append(
            f'diametro_furo ({drill}) não é numérico')
        return

    if drill < MIN_DRILL_MM:
        result.errors.append(
            f'Furo {drill:.3f}mm < mínimo de fabricação ({MIN_DRILL_MM}mm)')
    else:
        result.info.append(
            f'Drill OK: {drill:.3f}mm >= {MIN_DRILL_MM}mm')


def _check_pad_size(dados, result):
    """Check 7: Pads devem ser >= 0.20mm em ambas as dimensões."""
    # PTH: diâmetro do pad
    pad_diam = _get_nested(dados, 'pinos', 'diametro_pad')
    if pad_diam is not None:
        try:
            pd = float(pad_diam)
            if pd < MIN_PAD_DIM_MM:
                result.errors.append(
                    f'Pad PTH diâmetro {pd:.3f}mm < mínimo ({MIN_PAD_DIM_MM}mm)')
        except (ValueError, TypeError):
            pass

    # SMD: tamanho_pad
    tp = _get_nested(dados, 'pinos', 'tamanho_pad')
    if isinstance(tp, dict):
        for dim_name, dim_key in [('largura', 'largura'), ('altura', 'altura')]:
            val = tp.get(dim_key)
            if val is not None:
                try:
                    v = float(val)
                    if v < MIN_PAD_DIM_MM:
                        result.errors.append(
                            f'Pad SMD {dim_name} {v:.3f}mm < '
                            f'mínimo ({MIN_PAD_DIM_MM}mm)')
                except (ValueError, TypeError):
                    pass


def _check_pitch_vs_pad(dados, result):
    """Check 8: Aviso se pad > pitch (pads sobrepostos)."""
    pitch = _get_nested(dados, 'pinos', 'pitch')
    if pitch is None:
        return

    try:
        pitch = float(pitch)
    except (ValueError, TypeError):
        return

    # SMD
    tp = _get_nested(dados, 'pinos', 'tamanho_pad')
    if isinstance(tp, dict):
        for dim_key in ['largura', 'altura']:
            val = tp.get(dim_key)
            if val is not None:
                try:
                    v = float(val)
                    if v > pitch:
                        result.warnings.append(
                            f'Pad {dim_key} ({v}mm) > pitch ({pitch}mm). '
                            f'Pads podem estar se sobrepondo!')
                except (ValueError, TypeError):
                    pass

    # PTH
    pad_diam = _get_nested(dados, 'pinos', 'diametro_pad')
    if pad_diam is not None:
        try:
            pd = float(pad_diam)
            if pd > pitch:
                result.warnings.append(
                    f'Pad diâmetro ({pd}mm) > pitch ({pitch}mm). '
                    f'Pads podem estar se sobrepondo!')
        except (ValueError, TypeError):
            pass


def _check_kicad_fields(dados, result):
    """Check 9: Campos KiCad recomendados — referencia, descricao, tags."""
    kicad = dados.get('kicad', {})
    if not isinstance(kicad, dict):
        result.warnings.append(
            'Seção "kicad" ausente ou inválida. '
            'Recomendado: referencia, descricao, tags')
        return

    for campo in ['referencia', 'descricao', 'tags']:
        if campo not in kicad or not kicad[campo]:
            result.warnings.append(
                f'Campo kicad.{campo} ausente ou vazio')


def _check_body_dimensions(dados, result):
    """Check 10: Dimensões do corpo devem ser > 0."""
    corpo = dados.get('corpo', {})
    if not isinstance(corpo, dict) or not corpo:
        # Corpo pode não existir para todos os tipos
        return

    for dim_key in ['largura', 'comprimento', 'diametro', 'altura']:
        val = corpo.get(dim_key)
        if val is not None:
            try:
                v = float(val)
                if v <= 0:
                    result.errors.append(
                        f'corpo.{dim_key} = {v}mm — deve ser > 0')
            except (ValueError, TypeError):
                result.errors.append(
                    f'corpo.{dim_key} ({val}) não é numérico')


# =============================================================================
# Função principal de validação
# =============================================================================

_ALL_CHECKS = [
    _check_required_fields,
    _check_annular_ring,
    _check_pad_clearance,
    _check_courtyard,
    _check_silkscreen_on_pads,
    _check_drill_size,
    _check_pad_size,
    _check_pitch_vs_pad,
    _check_kicad_fields,
    _check_body_dimensions,
]


def validar_yaml(dados: dict) -> IPCValidationResult:
    """Valida dados YAML de footprint contra padrões IPC-7351B.

    Executa todos os checks e retorna um IPCValidationResult com
    erros, avisos e informações.

    Args:
        dados: dict com os dados do YAML carregado.

    Returns:
        IPCValidationResult com o resultado da validação.
    """
    result = IPCValidationResult()

    if not isinstance(dados, dict):
        result.errors.append('Dados de entrada não são um dicionário válido')
        return result

    for check_fn in _ALL_CHECKS:
        try:
            check_fn(dados, result)
        except Exception as e:
            result.warnings.append(
                f'Erro interno no check {check_fn.__name__}: {e}')

    # Resumo
    nome = dados.get('nome', '<sem nome>')
    tipo = dados.get('tipo', dados.get('padrao', '<sem tipo>'))
    if result.ok:
        log.info(f'IPC validação OK para "{nome}" ({tipo}): '
                 f'{len(result.warnings)} avisos, {len(result.info)} info')
    else:
        log.error(f'IPC validação FALHOU para "{nome}" ({tipo}): '
                  f'{len(result.errors)} erros, {len(result.warnings)} avisos')

    return result
