# =============================================================================
# importar_lcsc.py
# Importa um componente do LCSC/EasyEDA e gera o YAML do nosso formato.
#
# Filosofia: NÃO copiamos o desenho do símbolo do EasyEDA (geometria arbitrária,
# muitas vezes fora de padrão). Extraímos os DADOS — número, nome e posição de
# cada pino/pad — e emitimos um `padrao: custom`, deixando o nosso gerador
# produzir símbolo + footprint NATIVOS, que passam por IPC, colisão e pela
# conferência símbolo × footprint. A saída é conferível; uma cópia não seria.
#
# O que dá para extrair (e o que não dá):
#   - Pads: shape, posição, tamanho e furo — dados funcionais, vêm do datasheet.
#   - Pinos: número e nome — factual.
#   - Tipo elétrico do pino: o EasyEDA quase nunca o informa (fica 0) — então
#     NÃO inventamos; sai como padrão do gerador e o usuário refina se quiser.
#   - Contorno do corpo: aproximado pela caixa dos pads (o silk é recortado dos
#     pads de qualquer forma). O outline exato do EasyEDA não é extraído aqui.
#
# Conversão de unidades VALIDADA contra o NE555 (C7593, SOIC-8): as coordenadas
# do EasyEDA são em 10 mil; mm = (valor - origem) * 10 * 0.0254. O Y é negado
# para seguir a convenção do KiCad (pino 1 no topo).
#
# AVISOS (leia antes de depender disto):
#   - CÓDIGO x DADOS: este módulo é código original, sob a licença do projeto
#     (GPL-3.0) — não deriva do easyeda2kicad (AGPL-3.0). Mas os DADOS que ele
#     baixa (a geometria de cada componente) pertencem ao EasyEDA/LCSC e aos
#     fabricantes, não a nós. Gerar footprints a partir deles é prática comum
#     (cotas de datasheet não são obra criativa), mas o resultado NÃO é "livre
#     de qualquer direito" — confira a política do LCSC/EasyEDA antes de
#     redistribuir em massa ou comercialmente. Isto não é aconselhamento
#     jurídico.
#   - API NÃO-OFICIAL: usamos o endpoint interno easyeda.com/api/..., não
#     documentado para uso externo. Pode mudar, pode bloquear (responde 403 sem
#     cabeçalho de navegador) e está sujeito aos Termos de Serviço do EasyEDA.
#     Sem garantia de continuidade nem de autorização explícita.
# =============================================================================

import json
import logging
import re
import urllib.request

log = logging.getLogger(__name__)

_API = 'https://easyeda.com/api/products/{}/components?version=6.4.19.5'

# Cabeçalhos de navegador: a API responde 403 sem eles.
_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/120.0 Safari/537.36'),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://easyeda.com/',
    'Origin': 'https://easyeda.com',
}

# 1 unidade EasyEDA = 10 mil = 0.254 mm.
_ESCALA_MM = 10 * 0.0254

# EasyEDA shape → formato do nosso schema.
_FORMATO = {
    'ELLIPSE': 'circulo',
    'RECT': 'retangulo',
    'OVAL': 'oval',
    'POLYGON': 'retangulo',   # aproxima; o schema não tem polígono de pad
}


def _mm(valor, origem=0.0):
    """Converte coordenada/tamanho do EasyEDA para mm."""
    return round((float(valor) - origem) * _ESCALA_MM, 4)


def buscar_lcsc(codigo, timeout=25):
    """Baixa o JSON do componente pela API do EasyEDA. Devolve o dict `result`.

    Levanta ValueError com mensagem limpa em 403/404/componente inexistente, e
    deixa erros de rede subirem (URLError) para o chamador tratar.
    """
    codigo = str(codigo).strip().upper()
    if not re.fullmatch(r'C\d+', codigo):
        raise ValueError(
            f"código LCSC inválido: {codigo!r} — esperado algo como 'C7593'")

    req = urllib.request.Request(_API.format(codigo), headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise ValueError(
                "EasyEDA recusou a requisição (403). A API pode estar "
                "bloqueando este IP/cabeçalho — tente de outra rede.") from e
        raise ValueError(f"EasyEDA respondeu HTTP {e.code} para {codigo}") from e

    if not data.get('success') or not data.get('result'):
        raise ValueError(f"componente {codigo} não encontrado no EasyEDA/LCSC")
    return data['result']


def parse_pinos(result):
    """Extrai {numero: nome} do símbolo do EasyEDA.

    Cada pino é `P~<settings>^^<...>^^<nome>^^<numero>^^...`. O número está no
    bloco de settings (índice 3); o nome, no bloco de texto cujo rótulo não é
    puramente numérico.
    """
    pinos = {}
    ds = result.get('dataStr') or {}
    for s in ds.get('shape', []):
        if not s.startswith('P~'):
            continue
        segs = s.split('^^')
        f0 = segs[0].split('~')
        if len(f0) < 4:
            continue
        numero = f0[3]
        nome = ''
        for seg in segs[1:]:
            p = seg.split('~')
            # bloco de texto: [disp, x, y, rot, TEXTO, ancora(end/start), ...]
            if len(p) >= 6 and p[5] in ('start', 'end') and p[4] \
                    and not p[4].lstrip('-').isdigit():
                nome = p[4]
                break
        pinos[str(numero)] = nome
    return pinos


def parse_pads(result):
    """Extrai a lista de pads do footprint do EasyEDA, já em mm.

    Devolve dicts no formato do nosso `custom_pad`. O Y é negado (convenção
    KiCad). Pad girado 90°/270° troca largura↔altura, porque o nosso custom_pad
    não tem campo de rotação e a extensão do cobre é o que importa.
    """
    pkg = (result.get('packageDetail') or {}).get('dataStr') or {}
    head = pkg.get('head') or {}
    ox = float(head.get('x', 0) or 0)
    oy = float(head.get('y', 0) or 0)

    pads = []
    for s in pkg.get('shape', []):
        if not s.startswith('PAD~'):
            continue
        f = s.split('~')
        if len(f) < 12:
            continue
        shape = f[1]
        cx, cy = float(f[2]), float(f[3])
        w, h = _mm(f[4]), _mm(f[5])
        layer = f[6]
        numero = f[8]
        furo_raio = float(f[9] or 0)
        rot = abs(float(f[11] or 0)) % 180.0

        if abs(rot - 90.0) < 1e-6:
            w, h = h, w   # cobre ocupa transposto

        pad = {
            # o schema exige inteiro; pad textual (ex.: BGA 'A1') fica como está
            'numero': int(numero) if str(numero).isdigit() else numero,
            'x': _mm(cx, ox),
            'y': -_mm(cy, oy),        # Y do KiCad cresce para baixo
            'largura': w,
            'altura': h,
            'formato': _FORMATO.get(shape, 'retangulo'),
            'montagem': 'pth' if furo_raio > 0 or layer == '11' else 'smd',
        }
        if furo_raio > 0:
            pad['furo'] = round(furo_raio * 2 * _ESCALA_MM, 4)
        pads.append(pad)

    if shape not in _FORMATO and pads:
        log.warning("shape de pad '%s' não mapeado — usei retângulo", shape)
    return pads


def _nome_seguro(titulo, codigo):
    """Identificador de arquivo/símbolo a partir do título do componente."""
    base = re.sub(r'[^A-Za-z0-9]+', '_', (titulo or '').strip()).strip('_')
    if not base:
        return codigo
    # não duplica o código quando o título já o contém (ex.: 'SS34(C8678)')
    if re.search(rf'(^|_){re.escape(codigo)}($|_)', base, re.IGNORECASE):
        return base
    return f"{base}_{codigo}"


def montar_yaml(result, codigo):
    """Monta o dict do nosso YAML a partir do `result` do EasyEDA."""
    pads = parse_pads(result)
    if not pads:
        raise ValueError(
            f"{codigo}: o componente não tem pads de footprint no EasyEDA")
    nomes = parse_pinos(result)

    # nome do pino também no pad (o gerador de símbolo custom lê dos pads)
    for p in pads:
        chave = str(p['numero'])
        if nomes.get(chave):
            p['nome'] = nomes[chave]

    # corpo aproximado: caixa que engloba os pads (o silk é recortado deles)
    xs = [p['x'] for p in pads]
    ys = [p['y'] for p in pads]
    larg = [p['largura'] for p in pads]
    alt = [p['altura'] for p in pads]
    corpo_larg = round(max(x + w / 2 for x, w in zip(xs, larg))
                       - min(x - w / 2 for x, w in zip(xs, larg)), 3)
    corpo_comp = round(max(y + h / 2 for y, h in zip(ys, alt))
                       - min(y - h / 2 for y, h in zip(ys, alt)), 3)

    titulo = result.get('title') or codigo
    nome = _nome_seguro(titulo, codigo)
    dados = {
        'nome': nome,
        'padrao': 'custom',
        'corpo': {'largura': corpo_larg or 1.0, 'comprimento': corpo_comp or 1.0},
        'pads': pads,
        'kicad': {
            'descricao': (result.get('description') or titulo)[:200],
            'tags': f"lcsc {codigo}",
            'datasheet': f"https://www.lcsc.com/product-detail/{codigo}.html",
        },
    }
    if nomes:
        dados['pin_names'] = {k: v for k, v in nomes.items() if v}
    return dados


def importar(codigo, timeout=25):
    """Busca no LCSC e devolve o dict do YAML pronto para gerar/salvar."""
    return montar_yaml(buscar_lcsc(codigo, timeout=timeout), str(codigo).upper())
