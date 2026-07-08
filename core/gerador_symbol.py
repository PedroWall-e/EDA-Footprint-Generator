# =============================================================================
# gerador_symbol.py
# Gerador de símbolos esquemáticos KiCad (.kicad_sym)
# Compatibilidade: KiCad 6.x / 7.x / 8.x  (S-Expression format)
#
# Cada componente gera UM arquivo .kicad_sym com UM símbolo.
# Importar no KiCad: Schematic Editor → Preferences → Manage Symbol Libraries
#
# Tipos suportados (mesmos do gerador_footprint.py):
#   resistor_pth, diodo_pth, led_pth, capacitor_pth,
#   transistor_to92, crystal_hc49,
#   conector_pth, ci_dip, ci_soic, castellated
#
# IMPORTANTE — sistema de coordenadas do símbolo KiCad:
#   X: positivo para a DIREITA
#   Y: positivo para CIMA  (oposto ao footprint e ao SVG!)
# =============================================================================

import os


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
PIN_LEN  = 2.54   # comprimento padrão do stub do pino (mm)
FONT_SZ  = 1.27   # tamanho de fonte padrão (mm)
STROKE_W = 0.0    # espessura de linha (0 = padrão KiCad)


# ---------------------------------------------------------------------------
# Funções auxiliares — formatação S-Expression
# ---------------------------------------------------------------------------

def _f(v: float) -> str:
    """Formata número com 4 casas decimais."""
    return f"{float(v):.4f}"


def _font(sz: float = FONT_SZ) -> str:
    return f"(size {_f(sz)} {_f(sz)})"


def _pin(ptype: str, style: str, x: float, y: float,
         angle: int, length: float,
         name: str, number: str, hide_name: bool = False) -> str:
    """
    Gera um pino no formato KiCad.
    (x, y) = ponto de conexão do fio (extremidade externa)
    angle   = direção do stub em relação ao corpo:
              0   → pino vem da ESQUERDA (stub vai para a direita)
              90  → pino vem de BAIXO   (stub vai para cima)
              180 → pino vem da DIREITA (stub vai para a esquerda)
              270 → pino vem de CIMA    (stub vai para baixo)
    """
    hn = " (hide yes)" if hide_name else ""
    return (
        f'      (pin {ptype} {style}\n'
        f'        (at {_f(x)} {_f(y)} {angle})\n'
        f'        (length {_f(length)})\n'
        f'        (name "{name}" (effects (font {_font()}){hn}))\n'
        f'        (number "{number}" (effects (font {_font()})))\n'
        f'      )'
    )


def _poly(pts: list, fill: str = "none") -> str:
    """Gera uma polyline fechada ou aberta."""
    pts_s = " ".join(f"(xy {_f(x)} {_f(y)})" for x, y in pts)
    return (
        f'      (polyline\n'
        f'        (pts {pts_s})\n'
        f'        (stroke (width {_f(STROKE_W)}) (type default))\n'
        f'        (fill (type {fill}))\n'
        f'      )'
    )


def _rect(x1: float, y1: float, x2: float, y2: float,
          fill: str = "background") -> str:
    return (
        f'      (rectangle\n'
        f'        (start {_f(x1)} {_f(y1)})\n'
        f'        (end {_f(x2)} {_f(y2)})\n'
        f'        (stroke (width {_f(STROKE_W)}) (type default))\n'
        f'        (fill (type {fill}))\n'
        f'      )'
    )


def _circle(cx: float, cy: float, r: float, fill: str = "none") -> str:
    return (
        f'      (circle\n'
        f'        (center {_f(cx)} {_f(cy)})\n'
        f'        (radius {_f(r)})\n'
        f'        (stroke (width {_f(STROKE_W)}) (type default))\n'
        f'        (fill (type {fill}))\n'
        f'      )'
    )


def _wrap(nome: str, body_items: list, pin_items: list,
          ref_prefix: str, value_str: str,
          footprint: str = "", datasheet: str = "~", descricao: str = "",
          ref_at: tuple = (0, 3.81), val_at: tuple = (0, -3.81),
          pin_names_hidden: bool = False,
          pin_numbers_hidden: bool = True) -> str:
    """Envolve body + pins em um símbolo KiCad completo."""
    body = "\n".join(body_items)
    pins = "\n".join(pin_items)
    pnh  = " (hide yes)" if pin_names_hidden else ""
    pn_hide = "(hide yes)" if pin_numbers_hidden else "(hide no)"
    return (
        f'  (symbol "{nome}"\n'
        f'    (pin_numbers {pn_hide})\n'
        f'    (pin_names (offset 1.016){pnh})\n'
        f'    (exclude_from_sim no)\n'
        f'    (in_bom yes)\n'
        f'    (on_board yes)\n'
        f'    (property "Reference" "{ref_prefix}"\n'
        f'      (at {_f(ref_at[0])} {_f(ref_at[1])} 0)\n'
        f'      (effects (font {_font()}))\n'
        f'    )\n'
        f'    (property "Value" "{value_str}"\n'
        f'      (at {_f(val_at[0])} {_f(val_at[1])} 0)\n'
        f'      (effects (font {_font()}))\n'
        f'    )\n'
        f'    (property "Footprint" "{footprint}"\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font {_font()}) (hide yes))\n'
        f'    )\n'
        f'    (property "Datasheet" "{datasheet}"\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font {_font()}) (hide yes))\n'
        f'    )\n'
        f'    (property "Description" "{descricao}"\n'
        f'      (at 0 0 0)\n'
        f'      (effects (font {_font()}) (hide yes))\n'
        f'    )\n'
        f'    (symbol "{nome}_0_1"\n'
        f'{body}\n'
        f'    )\n'
        f'    (symbol "{nome}_1_1"\n'
        f'{pins}\n'
        f'    )\n'
        f'  )'
    )


def _lib(symbols: list) -> str:
    """Envolve símbolos em uma biblioteca .kicad_sym."""
    return (
        "(kicad_symbol_lib\n"
        "  (version 20231120)\n"
        '  (generator "CAM_CAD_Plataforma")\n'
        '  (generator_version "2.0")\n'
        + "\n".join(symbols)
        + "\n)\n"
    )


# ---------------------------------------------------------------------------
# Helpers de acesso ao YAML
# ---------------------------------------------------------------------------
def _ref(d): return d.get("kicad", {}).get("referencia", "U?")
def _val(d): return d.get("kicad", {}).get("valor", d.get("nome", ""))
def _desc(d): return d.get("kicad", {}).get("descricao", "")


def _pn_get(pn: dict, num: int, default: str = None) -> str:
    """Busca nome do pino tentando chave int e str.

    O YAML parser interpreta '1: GND' como chave int(1), mas
    '"1": GND' como chave str("1"). Esta função aceita ambos.
    """
    if default is None:
        default = f"Pin_{num}"
    return pn.get(str(num), pn.get(num, default))


def _pt_get(pt: dict, num: int, default: str = "bidirectional") -> str:
    """Busca tipo elétrico do pino tentando chave int e str."""
    return pt.get(str(num), pt.get(num, default))


def _max_pin_name_len(pn: dict, pin_numbers: list) -> float:
    """Retorna largura estimada (mm) do nome de pino mais longo.

    Estimativa: FONT_SZ * 0.7 * len(nome)  (largura média de caractere monospace).
    Mínimo retornado: 0.
    """
    if not pin_numbers:
        return 0
    max_len = 0
    for num in pin_numbers:
        name = _pn_get(pn, num)
        # Remove marcadores KiCad (~{...}) para calcular largura visual
        clean = name.replace('~{', '').replace('}', '')
        max_len = max(max_len, len(clean))
    return max_len * FONT_SZ * 0.75


# ===========================================================================
# Geradores por tipo
# ===========================================================================


def _sym_resistor_pth(dados: dict) -> str:
    """Símbolo de resistor: corpo retangular, 2 pinos passivos."""
    nome = dados["nome"]
    body = [_rect(-1.016, -0.508, 1.016, 0.508, fill="none")]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.524, "~", "1", hide_name=True),
        _pin("passive", "line",  2.54, 0, 180, 1.524, "~", "2", hide_name=True),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 1.27), val_at=(0, -1.27),
                 pin_names_hidden=True)


def _sym_diodo_pth(dados: dict) -> str:
    """Símbolo de diodo: triângulo + barra de catodo."""
    nome = dados["nome"]
    body = [
        # Triângulo preenchido (anodo → catodo)
        _poly([(-1.016, -1.016), (-1.016, 1.016), (1.016, 0), (-1.016, -1.016)],
              fill="background"),
        # Barra do catodo
        _poly([(1.016, -1.016), (1.016, 1.016)]),
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.524, "A", "1"),
        _pin("passive", "line",  2.54, 0, 180, 1.524, "K", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -2.54))


def _sym_led_pth(dados: dict) -> str:
    """Símbolo de LED: diodo + duas setas de emissão de luz."""
    nome = dados["nome"]
    body = [
        _poly([(-1.016, -1.016), (-1.016, 1.016), (1.016, 0), (-1.016, -1.016)],
              fill="background"),
        _poly([(1.016, -1.016), (1.016, 1.016)]),
        # Seta de luz 1 (diagonal subindo)
        _poly([(0.508, 1.524), (1.778, 2.794)]),
        _poly([(1.778, 2.794), (1.270, 2.794), (1.778, 2.794), (1.778, 2.286)]),
        # Seta de luz 2 (mais à esquerda)
        _poly([(-0.127, 1.524), (1.143, 2.794)]),
        _poly([(1.143, 2.794), (0.635, 2.794), (1.143, 2.794), (1.143, 2.286)]),
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.524, "A", "1"),
        _pin("passive", "line",  2.54, 0, 180, 1.524, "K", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 3.302), val_at=(0, -2.54))


def _sym_capacitor_pth(dados: dict) -> str:
    """Símbolo de capacitor eletrolítico polarizado."""
    nome = dados["nome"]
    body = [
        # Placa positiva (linha vertical)
        _poly([(-0.508, -1.778), (-0.508, 1.778)]),
        # Placa negativa (linha vertical)
        _poly([(0.508, -1.778), (0.508, 1.778)]),
        # Sinal + (próximo ao pino positivo)
        _poly([(-2.032, 0.508), (-2.032, 1.524)]),   # traço vertical do +
        _poly([(-2.540, 1.016), (-1.524, 1.016)]),   # traço horizontal do +
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   2.032, "+", "1"),
        _pin("passive", "line",  2.54, 0, 180, 2.032, "-", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -2.54))


def _sym_transistor_to92(dados: dict) -> str:
    """Símbolo NPN BJT: círculo + linhas internas + seta no emissor."""
    nome    = dados["nome"]
    pinagem = dados.get("pinos", {}).get("pinagem", "CBE").upper()

    # Mapear pinagem string → número do pino no símbolo
    # Ex: "CBE" → C=1, B=2, E=3
    role_to_num: dict = {}
    for i, role in enumerate(pinagem[:3]):
        role_to_num[role] = str(i + 1)
    b_num = role_to_num.get("B", "2")
    c_num = role_to_num.get("C", "1")
    e_num = role_to_num.get("E", "3")

    body = [
        _circle(0, 0, 1.905),                          # círculo do transistor
        _poly([(-1.778, 0), (0.508, 0)]),              # linha conectando pino B a base
        _poly([(0.508, -1.016), (0.508, 1.016)]),      # linha base interna
        _poly([(0.508,  0.635), (1.270,  1.905)]),     # linha do coletor
        _poly([(0.508, -0.635), (1.270, -1.905)]),     # linha do emissor
        # Seta NPN no emissor (saindo)
        _poly([(0.762, -1.397), (1.270, -1.905), (1.524, -1.143), (0.762, -1.397)], fill="background"),
    ]
    pins = [
        _pin("passive", "line", -3.81, 0,     0,   2.032, "B", b_num),
        _pin("passive", "line",  1.27, 3.81,  270, 1.905, "C", c_num),
        _pin("passive", "line",  1.27, -3.81,  90, 1.905, "E", e_num),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(-2.032, 3.302), val_at=(-2.032, -3.302))


def _sym_crystal_hc49(dados: dict) -> str:
    """Símbolo de cristal: duas barras flanqueando um retângulo."""
    nome = dados["nome"]
    body = [
        # Barra esquerda
        _poly([(-0.635, -1.524), (-0.635, 1.524)]),
        # Corpo retangular central
        _rect(-0.635, -0.762, 0.635, 0.762, fill="none"),
        # Barra direita
        _poly([(0.635, -1.524), (0.635, 1.524)]),
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.905, "1", "1", hide_name=True),
        _pin("passive", "line",  2.54, 0, 180, 1.905, "2", "2", hide_name=True),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.286), val_at=(0, -2.286),
                 pin_names_hidden=True)


def _sym_conector_pth(dados: dict) -> str:
    """Símbolo de conector: retângulo com todos os pinos na esquerda."""
    nome  = dados["nome"]
    total = int(dados["pinos"]["total"])
    pn    = dados.get("pin_names", {})   # {"1":"VCC","2":"GND",...} — opcional

    body_w_fixed = 5.08

    # --- Calcular largura dinâmica baseada nos nomes dos pinos ---
    all_pins = list(range(1, total + 1))
    name_w = _max_pin_name_len(pn, all_pins)
    # Conector tem pinos só na esquerda, nome precisa caber dentro do corpo
    body_w = max(body_w_fixed, name_w + 2.54)

    body_h = total * 2.54 + 1.27
    x_l, x_r = -body_w / 2, body_w / 2
    y_t, y_b  =  body_h / 2, -body_h / 2

    def _y(i):  # i=0 → topo, i=total-1 → base
        return ((total - 1) / 2.0 - i) * 2.54

    body = [_rect(x_l, y_t, x_r, y_b, fill="background")]
    pins = [
        _pin("passive", "line",
             x_l - PIN_LEN, _y(i), 0, PIN_LEN,
             _pn_get(pn, i + 1), str(i + 1))
        for i in range(total)
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, y_t + 1.27), val_at=(0, y_b - 1.27))


def _sym_ci_generico(dados: dict) -> str:
    """
    Símbolo genérico para CI DIP/SOIC.
    Pinos 1..N_esq na esquerda (topo→base), pinos N_esq+1..N na direita (base→topo).
    Suporta total ímpar (ex: 3 pinos → 2 esquerda, 1 direita).
    Campo opcional 'pin_names' no YAML: {"1":"VCC","2":"GND",...}
    """
    nome  = dados["nome"]
    total = int(dados["pinos"]["total"])
    # Distribuição assimétrica: lado esquerdo recebe o pino extra se ímpar
    n_esq = (total + 1) // 2
    n_dir = total - n_esq
    pn    = dados.get("pin_names", {})
    pt    = dados.get("pin_types", {})

    body_w_fixed = 10.16

    # --- Calcular largura dinâmica baseada nos nomes dos pinos ---
    left_pins  = list(range(1, n_esq + 1))
    right_pins = list(range(n_esq + 1, total + 1))
    name_w_left  = _max_pin_name_len(pn, left_pins)
    name_w_right = _max_pin_name_len(pn, right_pins)
    # Largura mínima = nomes de ambos os lados + margem central
    body_w_names = name_w_left + name_w_right + 2.54
    body_w = max(body_w_fixed, body_w_names)

    max_side = max(n_esq, n_dir, 1)
    body_h = max_side * 2.54 + 1.27
    x_l, x_r = -body_w / 2, body_w / 2
    y_t, y_b  =  body_h / 2, -body_h / 2

    def _y_left(i):   # pin 1 ao topo, pin n_esq ao fundo
        return ((n_esq - 1) / 2.0 - i) * 2.54

    def _y_right(j):  # pin n_esq+1 ao fundo, pin total ao topo
        return (j - (n_dir - 1) / 2.0) * 2.54

    body = [
        _rect(x_l, y_t, x_r, y_b, fill="background"),
        # Notch de pino 1 (semicírculo no canto superior esquerdo)
        _poly([(x_l, _y_left(0) + 1.27), (x_l + 1.27, _y_left(0) + 1.27),
               (x_l + 1.27, _y_left(0))]),
    ]

    pins = []
    for i in range(n_esq):
        num  = i + 1
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         x_l - PIN_LEN, _y_left(i), 0, PIN_LEN,
                         name, str(num)))

    for j in range(n_dir):
        num  = n_esq + 1 + j
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         x_r + PIN_LEN, _y_right(j), 180, PIN_LEN,
                         name, str(num)))

    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, y_t + 1.27), val_at=(0, y_b - 1.27),
                 pin_numbers_hidden=False)


def _sym_castellated(dados: dict) -> str:
    """
    Símbolo para módulo castellated com 2 ou 4 lados.
    Usa o mesmo layout de IC genérico com retângulo + pinos distribuídos.
    Campo opcional 'pin_names' no YAML.
    """
    nome   = dados["nome"]
    pn     = dados.get("pin_names", {})
    pt     = dados.get("pin_types", {})

    lados_cfg = dados.get("pinos", {}).get("lados")
    if lados_cfg:
        n_esq  = int(lados_cfg.get("esquerdo", 0))
        n_base = int(lados_cfg.get("base", 0))
        n_dir  = int(lados_cfg.get("direito", 0))
        n_topo = int(lados_cfg.get("topo", 0))
    else:
        n_por  = int(dados["pinos"].get("por_lado", 0))
        n_esq, n_base, n_dir, n_topo = n_por, 0, n_por, 0

    total  = n_esq + n_base + n_dir + n_topo
    max_lr = max(n_esq, n_dir, 1)
    max_tb = max(n_topo, n_base, 0)

    body_h = max_lr * 2.54 + 1.27

    # --- Calcular largura dinâmica baseada nos nomes dos pinos ---
    body_w_fixed = max(10.16, max_tb * 2.54 + 5.08) if max_tb else 10.16
    # Estimar nomes mais longos nos lados esquerdo e direito
    left_pins  = list(range(1, n_esq + 1))
    right_start = n_esq + n_base + 1
    right_pins = list(range(right_start, right_start + n_dir))
    name_w_left  = _max_pin_name_len(pn, left_pins)
    name_w_right = _max_pin_name_len(pn, right_pins)
    body_w_names = name_w_left + name_w_right + 2.54
    body_w = max(body_w_fixed, body_w_names)

    x_l, x_r = -body_w / 2, body_w / 2
    y_t, y_b  =  body_h / 2, -body_h / 2

    def _y_side(n, i):   # topo (i=0) → base (i=n-1)
        return ((n - 1) / 2.0 - i) * 2.54

    def _x_side(n, i):   # esquerda (i=0) → direita (i=n-1)
        return (i - (n - 1) / 2.0) * 2.54

    body = [_rect(x_l, y_t, x_r, y_b, fill="background")]
    pins = []
    num  = 1

    # Esquerdo: cima → baixo
    for i in range(n_esq):
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         x_l - PIN_LEN, _y_side(n_esq, i), 0, PIN_LEN,
                         name, str(num)))
        num += 1

    # Base: esq → dir
    for i in range(n_base):
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         _x_side(n_base, i), y_b - PIN_LEN, 90, PIN_LEN,
                         name, str(num)))
        num += 1

    # Direito: baixo → cima
    for i in reversed(range(n_dir)):
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         x_r + PIN_LEN, _y_side(n_dir, i), 180, PIN_LEN,
                         name, str(num)))
        num += 1

    # Topo: dir → esq
    for i in reversed(range(n_topo)):
        name = _pn_get(pn, num)
        pins.append(_pin(_pt_get(pt, num), "line",
                         _x_side(n_topo, i), y_t + PIN_LEN, 270, PIN_LEN,
                         name, str(num)))
        num += 1

    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, y_t + 1.27), val_at=(0, y_b - 1.27),
                 pin_numbers_hidden=False)


def _row_label_sym(row_idx):
    """Converte índice de linha (0-based) para label: 0→A, 1→B, ..., 25→Z, 26→AA."""
    label = ''
    n = row_idx
    while True:
        label = chr(ord('A') + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label


def _sym_bga(dados: dict) -> str:
    """Símbolo para BGA: distribui pinos nos 4 lados do retângulo.

    Para BGAs grandes (ex: 256 pinos), divide igualmente nos 4 lados:
    - Esquerda: linhas A-D  (primeiras linhas)
    - Base:     linhas E-H  (próximas)
    - Direita:  linhas I-L  (próximas)
    - Topo:     linhas M-P  (restantes)

    Cada pino mantém seu nome real (A1, B3, etc.).
    """
    nome    = dados['nome']
    pinos   = dados.get('pinos', {})
    linhas  = int(pinos.get('linhas', 10))
    colunas = int(pinos.get('colunas', 10))
    excluir = set(pinos.get('excluir', []))
    pn      = dados.get('pin_names', {})
    pt      = dados.get('pin_types', {})

    # Construir lista de todos os pinos válidos na ordem da grid
    all_pins = []
    for row in range(linhas):
        row_lbl = _row_label_sym(row)
        for col in range(colunas):
            pin_name = f"{row_lbl}{col + 1}"
            if pin_name not in excluir:
                all_pins.append(pin_name)

    total = len(all_pins)

    # Dividir pinos nos 4 lados igualmente
    q = total // 4
    r = total % 4
    n_esq  = q + (1 if r > 0 else 0)
    n_base = q + (1 if r > 1 else 0)
    n_dir  = q + (1 if r > 2 else 0)
    n_topo = total - n_esq - n_base - n_dir

    side_esq  = all_pins[:n_esq]
    side_base = all_pins[n_esq:n_esq + n_base]
    side_dir  = all_pins[n_esq + n_base:n_esq + n_base + n_dir]
    side_topo = all_pins[n_esq + n_base + n_dir:]

    # Dimensões do corpo (proporcional ao número de pinos por lado)
    max_lr = max(n_esq, n_dir, 1)
    max_tb = max(n_topo, n_base, 1)

    body_h = max_lr * 2.54 + 2.54
    body_w_fixed = max(max_tb * 2.54 + 2.54, body_h)  # manter ~quadrado

    # --- Calcular largura dinâmica baseada nos nomes dos pinos ---
    # BGA usa nomes como A1, P16 etc.
    left_pin_nums = list(range(1, len(side_esq) + 1))
    right_pin_nums = list(range(len(side_esq) + len(side_base) + 1,
                                len(side_esq) + len(side_base) + len(side_dir) + 1))
    # Estimar largura dos nomes (BGA usa nomes curtos, mas por segurança)
    name_w_left  = _max_pin_name_len(pn, left_pin_nums) if pn else max(len(s) for s in side_esq) * FONT_SZ * 0.75 if side_esq else 0
    name_w_right = _max_pin_name_len(pn, right_pin_nums) if pn else max(len(s) for s in side_dir) * FONT_SZ * 0.75 if side_dir else 0
    body_w_names = name_w_left + name_w_right + 2.54
    body_w = max(body_w_fixed, body_w_names)

    x_l, x_r = -body_w / 2, body_w / 2
    y_t, y_b =  body_h / 2, -body_h / 2

    def _y_side(n, i):  # distribui verticalmente
        return ((n - 1) / 2.0 - i) * 2.54

    def _x_side(n, i):  # distribui horizontalmente
        return (i - (n - 1) / 2.0) * 2.54

    body = [
        _rect(x_l, y_t, x_r, y_b, fill="background"),
        # Marcador A1 (círculo no canto sup-esq)
        _circle(x_l + 1.5, y_t - 1.5, 0.5, fill="background"),
    ]

    pin_items = []

    # Esquerda: cima → baixo
    for i, pname in enumerate(side_esq):
        num_str = pname  # usar nome como número (A1, B2, etc.)
        display_name = pn.get(pname, pn.get(str(i+1), pname))
        pin_items.append(_pin(
            pt.get(pname, 'bidirectional'), 'line',
            x_l - PIN_LEN, _y_side(n_esq, i), 0, PIN_LEN,
            display_name, num_str, hide_name=True))

    # Base: esq → dir
    for i, pname in enumerate(side_base):
        display_name = pn.get(pname, pn.get(str(n_esq+i+1), pname))
        pin_items.append(_pin(
            pt.get(pname, 'bidirectional'), 'line',
            _x_side(n_base, i), y_b - PIN_LEN, 90, PIN_LEN,
            display_name, pname, hide_name=True))

    # Direita: baixo → cima
    for i, pname in enumerate(reversed(side_dir)):
        display_name = pn.get(pname, pn.get(str(n_esq+n_base+n_dir-i), pname))
        pin_items.append(_pin(
            pt.get(pname, 'bidirectional'), 'line',
            x_r + PIN_LEN, _y_side(n_dir, i), 180, PIN_LEN,
            display_name, pname, hide_name=True))

    # Topo: dir → esq
    for i, pname in enumerate(reversed(side_topo)):
        display_name = pn.get(pname, pn.get(str(total-i), pname))
        pin_items.append(_pin(
            pt.get(pname, 'bidirectional'), 'line',
            _x_side(n_topo, i), y_t + PIN_LEN, 270, PIN_LEN,
            display_name, pname, hide_name=True))

    return _wrap(nome, body, pin_items, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, y_t + 2.54), val_at=(0, y_b - 2.54),
                 pin_numbers_hidden=False,
                 pin_names_hidden=True)


# ===========================================================================
# Novos geradores — MOSFETs
# ===========================================================================

def _sym_mosfet_n(dados: dict) -> str:
    """Símbolo N-Channel MOSFET: gate, drain, source com seta apontando PARA o canal."""
    nome = dados["nome"]
    pn   = dados.get("pin_names", {})
    g_num = _pn_get(pn, 1, "G")
    d_num = _pn_get(pn, 2, "D")
    s_num = _pn_get(pn, 3, "S")

    body = [
        _circle(0, 0, 2.54),                             # corpo circular
        # Gate: linha horizontal da esquerda + barra vertical paralela ao canal
        _poly([(-2.54, 0), (-1.27, 0)]),                  # conexão gate → corpo
        _poly([(-1.27, -1.524), (-1.27, 1.524)]),         # barra do gate
        # Canal: linha vertical (drain → source)
        _poly([(0, -1.524), (0, -0.508)]),                # canal inferior
        _poly([(0,  0.508), (0,  1.524)]),                # canal superior
        _poly([(0, -0.508), (0, 0.508)]),                 # canal central
        # Drain: linha para cima
        _poly([(0,  1.524), (0,  2.54)]),                 # drain stub
        # Source: linha para baixo
        _poly([(0, -1.524), (0, -2.54)]),                 # source stub
        # Conexão drain horizontal
        _poly([(0,  1.524), (1.27,  1.524)]),
        _poly([(1.27,  1.524), (1.27,  2.54)]),
        # Conexão source horizontal
        _poly([(0, -1.524), (1.27, -1.524)]),
        _poly([(1.27, -1.524), (1.27, -2.54)]),
        # Seta no source apontando PARA o canal (N-channel)
        _poly([(-0.508, -0.508), (0, 0), (0.508, -0.508), (-0.508, -0.508)],
              fill="background"),
        # Body diode connection
        _poly([(0, 0), (1.27, 0)]),
    ]
    pins = [
        _pin("input",   "line", -5.08, 0,     0,   PIN_LEN, "G", str(g_num)),
        _pin("passive", "line",  1.27,  5.08,  270, PIN_LEN, "D", str(d_num)),
        _pin("passive", "line",  1.27, -5.08,  90,  PIN_LEN, "S", str(s_num)),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(-3.81, 3.81), val_at=(-3.81, -3.81))


def _sym_mosfet_p(dados: dict) -> str:
    """Símbolo P-Channel MOSFET: seta apontando PARA FORA do canal + círculo no gate."""
    nome = dados["nome"]
    pn   = dados.get("pin_names", {})
    g_num = _pn_get(pn, 1, "G")
    d_num = _pn_get(pn, 2, "D")
    s_num = _pn_get(pn, 3, "S")

    body = [
        _circle(0, 0, 2.54),                             # corpo circular
        # Gate: linha horizontal + barra vertical
        _poly([(-2.54, 0), (-1.524, 0)]),                 # conexão gate (com espaço pro círculo)
        _circle(-1.397, 0, 0.127),                        # círculo invertido no gate
        _poly([(-1.27, -1.524), (-1.27, 1.524)]),         # barra do gate
        # Canal: linha vertical (drain → source)
        _poly([(0, -1.524), (0, -0.508)]),
        _poly([(0,  0.508), (0,  1.524)]),
        _poly([(0, -0.508), (0, 0.508)]),
        # Drain: linha para cima
        _poly([(0,  1.524), (0,  2.54)]),
        # Source: linha para baixo
        _poly([(0, -1.524), (0, -2.54)]),
        # Conexão drain horizontal
        _poly([(0,  1.524), (1.27,  1.524)]),
        _poly([(1.27,  1.524), (1.27,  2.54)]),
        # Conexão source horizontal
        _poly([(0, -1.524), (1.27, -1.524)]),
        _poly([(1.27, -1.524), (1.27, -2.54)]),
        # Seta no source apontando PARA FORA do canal (P-channel)
        _poly([(-0.508, 0.508), (0, 0), (0.508, 0.508), (-0.508, 0.508)],
              fill="background"),
        # Body diode connection
        _poly([(0, 0), (1.27, 0)]),
    ]
    pins = [
        _pin("input",   "line", -5.08, 0,     0,   PIN_LEN, "G", str(g_num)),
        _pin("passive", "line",  1.27,  5.08,  270, PIN_LEN, "D", str(d_num)),
        _pin("passive", "line",  1.27, -5.08,  90,  PIN_LEN, "S", str(s_num)),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(-3.81, 3.81), val_at=(-3.81, -3.81))


# ===========================================================================
# Novos geradores — Regulador, Op-Amp
# ===========================================================================

def _sym_regulador(dados: dict) -> str:
    """Símbolo de regulador de tensão 3 pinos: IN (esq), GND (baixo), OUT (dir)."""
    nome = dados["nome"]
    pn   = dados.get("pin_names", {})
    in_name  = _pn_get(pn, 1, "IN")
    gnd_name = _pn_get(pn, 2, "GND")
    out_name = _pn_get(pn, 3, "OUT")

    # Corpo: retangulo 7.62 x 5.08 (3x2 unidades de grid) - minimo
    bw_fixed, bh = 7.62, 5.08

    # --- Calcular largura dinamica baseada nos nomes dos pinos ---
    name_w_left  = _max_pin_name_len(pn, [1])
    name_w_right = _max_pin_name_len(pn, [3])
    bw = max(bw_fixed, name_w_left + name_w_right + 2.54)

    x_l, x_r = -bw / 2, bw / 2
    y_t, y_b =  bh / 2, -bh / 2

    body = [
        _rect(x_l, y_t, x_r, y_b, fill="background"),
    ]
    pins = [
        _pin("input",        "line", x_l - PIN_LEN, 0,           0,   PIN_LEN, in_name,  "1"),
        _pin("power_in",     "line", 0,              y_b - PIN_LEN, 90,  PIN_LEN, gnd_name, "2"),
        _pin("power_out",    "line", x_r + PIN_LEN,  0,          180,  PIN_LEN, out_name, "3"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, y_t + 1.27), val_at=(0, y_b - 2.54),
                 pin_numbers_hidden=False)


def _sym_opamp(dados: dict) -> str:
    """Símbolo de amplificador operacional: triângulo + pinos +/- e saída.

    3 pinos (básico) ou 5 pinos (com alimentação V+/V-).
    """
    nome  = dados["nome"]
    pn    = dados.get("pin_names", {})
    total = int(dados.get('pinos', {}).get('total', 5))

    # Triângulo apontando para a direita
    tri_pts = [(-3.81, -3.81), (-3.81, 3.81), (3.81, 0), (-3.81, -3.81)]

    body = [
        _poly(tri_pts, fill="background"),
        # Símbolo + na entrada não-inversora (superior)
        _poly([(-2.54, 1.27), (-1.524, 1.27)]),           # traço horizontal
        _poly([(-2.032, 0.762), (-2.032, 1.778)]),        # traço vertical
        # Símbolo - na entrada inversora (inferior)
        _poly([(-2.54, -1.27), (-1.524, -1.27)]),         # traço horizontal
    ]

    # Nomes dos pinos
    inp_name  = _pn_get(pn, 1, "+")
    inn_name  = _pn_get(pn, 2, "-")
    out_name  = _pn_get(pn, 3, "OUT")

    pins = [
        # Entrada não-inversora (+) — acima
        _pin("input",  "line", -6.35,  1.27, 0,   PIN_LEN, inp_name, "1"),
        # Entrada inversora (-) — abaixo
        _pin("input",  "line", -6.35, -1.27, 0,   PIN_LEN, inn_name, "2"),
        # Saída
        _pin("output", "line",  6.35,  0,    180, PIN_LEN, out_name, "3"),
    ]

    if total >= 5:
        vp_name = _pn_get(pn, 4, "V+")
        vn_name = _pn_get(pn, 5, "V-")
        pins.extend([
            _pin("power_in", "line", 0,  5.08,  270, PIN_LEN, vp_name, "4"),
            _pin("power_in", "line", 0, -5.08,   90, PIN_LEN, vn_name, "5"),
        ])

    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 5.08), val_at=(0, -5.08),
                 pin_numbers_hidden=False)


# ===========================================================================
# Novos geradores — Passivos (indutor, fusível, bateria)
# ===========================================================================

def _sym_indutor(dados: dict) -> str:
    """Símbolo de indutor/bobina: 4 arcos (semicírculos) entre 2 pinos."""
    nome = dados["nome"]
    import math
    # 4 arcos, cada um com raio 0.508, centros espaçados em 1.016
    body = []
    n_arcs = 4
    arc_r  = 0.508
    total_w = n_arcs * 2 * arc_r  # 4.064
    x_start = -total_w / 2

    for k in range(n_arcs):
        cx = x_start + arc_r + k * 2 * arc_r
        # Aproximar semicírculo superior com polyline (8 segmentos)
        pts = []
        for s in range(9):
            angle = math.pi * s / 8  # 0 → π
            px = cx + arc_r * math.cos(angle)
            py = arc_r * math.sin(angle)  # semicírculo para cima
            pts.append((px, py))
        body.append(_poly(pts))

    # Linhas de conexão aos pinos
    body.append(_poly([(-PIN_LEN, 0), (x_start, 0)]))
    body.append(_poly([(x_start + total_w, 0), (PIN_LEN, 0)]))

    pins = [
        _pin("passive", "line", -2.54 - PIN_LEN, 0, 0,   PIN_LEN, "~", "1", hide_name=True),
        _pin("passive", "line",  2.54 + PIN_LEN, 0, 180, PIN_LEN, "~", "2", hide_name=True),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -1.27),
                 pin_names_hidden=True)


def _sym_fusivel(dados: dict) -> str:
    """Símbolo de fusível: retângulo fino com entalhe/abertura interna."""
    nome = dados["nome"]
    body = [
        # Corpo retangular fino
        _rect(-1.27, -0.508, 1.27, 0.508, fill="none"),
        # Fio interno em S (representando o elemento fusível)
        _poly([(-1.27, 0), (-0.635, 0.381), (0, 0), (0.635, -0.381), (1.27, 0)]),
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.27, "~", "1", hide_name=True),
        _pin("passive", "line",  2.54, 0, 180, 1.27, "~", "2", hide_name=True),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 1.27), val_at=(0, -1.27),
                 pin_names_hidden=True)


def _sym_bateria(dados: dict) -> str:
    """Símbolo de bateria: duas placas verticais (longa=+, curta=-)."""
    nome = dados["nome"]
    body = [
        # Placa positiva (longa)
        _poly([(-0.508, -1.524), (-0.508, 1.524)]),
        # Placa negativa (curta)
        _poly([(0.508, -0.762), (0.508, 0.762)]),
        # Símbolo + (próximo ao terminal positivo)
        _poly([(-1.778, 0.508), (-1.778, 1.27)]),         # vertical
        _poly([(-2.159, 0.889), (-1.397, 0.889)]),        # horizontal
        # Símbolo - (próximo ao terminal negativo)
        _poly([(1.397, 0.889), (2.159, 0.889)]),          # horizontal
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   2.032, "+", "1"),
        _pin("passive", "line",  2.54, 0, 180, 2.032, "-", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -2.54))


# ===========================================================================
# Novos geradores — Antena, Diodo Zener, Diodo Schottky
# ===========================================================================

def _sym_antena(dados: dict) -> str:
    """Símbolo de antena: V invertido com linha vertical para baixo. 1 pino."""
    nome = dados["nome"]
    body = [
        # Linha vertical (da base ao ponto de encontro)
        _poly([(0, -1.27), (0, 2.54)]),
        # V invertido (duas diagonais para cima)
        _poly([(-1.524, 1.27), (0, 3.81), (1.524, 1.27)]),
    ]
    pins = [
        _pin("passive", "line", 0, -3.81, 90, PIN_LEN, "ANT", "1"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(2.54, 2.54), val_at=(2.54, 0))


def _sym_diodo_zener(dados: dict) -> str:
    """Símbolo de diodo Zener: triângulo + barra de catodo com extremidades dobradas (Z)."""
    nome = dados["nome"]
    body = [
        # Triângulo preenchido (anodo → catodo)
        _poly([(-1.016, -1.016), (-1.016, 1.016), (1.016, 0), (-1.016, -1.016)],
              fill="background"),
        # Barra do catodo com extremidades em Z
        _poly([(0.762, -1.270), (1.016, -1.016), (1.016, 1.016), (1.270, 1.270)]),
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.524, "A", "1"),
        _pin("passive", "line",  2.54, 0, 180, 1.524, "K", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -2.54))


def _sym_diodo_schottky(dados: dict) -> str:
    """Símbolo de diodo Schottky: triângulo + barra de catodo com extremidades em S."""
    nome = dados["nome"]
    body = [
        # Triângulo preenchido (anodo → catodo)
        _poly([(-1.016, -1.016), (-1.016, 1.016), (1.016, 0), (-1.016, -1.016)],
              fill="background"),
        # Barra do catodo com extremidades em S (curvas opostas)
        _poly([(0.762, -1.016), (0.762, -0.762), (1.016, -0.762)]),       # curva inferior
        _poly([(1.016, -1.016), (1.016, 1.016)]),                         # barra central
        _poly([(1.016, 0.762), (1.270, 0.762), (1.270, 1.016)]),          # curva superior
    ]
    pins = [
        _pin("passive", "line", -2.54, 0, 0,   1.524, "A", "1"),
        _pin("passive", "line",  2.54, 0, 180, 1.524, "K", "2"),
    ]
    return _wrap(nome, body, pins, _ref(dados), _val(dados),
                 footprint=dados.get('kicad', {}).get('footprint_lib', ''),
                 datasheet=dados.get('datasheet_url', '~'),
                 descricao=_desc(dados),
                 ref_at=(0, 2.54), val_at=(0, -2.54))


# ===========================================================================
# Dispatcher principal
# ===========================================================================

_DISPATCH = {
    # Originais
    'resistor_pth':    _sym_resistor_pth,
    'diodo_pth':       _sym_diodo_pth,
    'led_pth':         _sym_led_pth,
    'capacitor_pth':   _sym_capacitor_pth,
    'transistor_to92': _sym_transistor_to92,
    'crystal_hc49':    _sym_crystal_hc49,
    'conector_pth':    _sym_conector_pth,
    'ci_dip':          _sym_ci_generico,
    'ci_soic':         _sym_ci_generico,
    'castellated':     _sym_castellated,
    'bga':             _sym_bga,
    # Novos
    'mosfet_n':        _sym_mosfet_n,
    'mosfet_p':        _sym_mosfet_p,
    'regulador':       _sym_regulador,
    'opamp':           _sym_opamp,
    'indutor':         _sym_indutor,
    'fusivel':         _sym_fusivel,
    'bateria':         _sym_bateria,
    'antena':          _sym_antena,
    'diodo_zener':     _sym_diodo_zener,
    'diodo_schottky':  _sym_diodo_schottky,
    # Aliases (nomes curtos)
    'resistor':        _sym_resistor_pth,
    'capacitor':       _sym_capacitor_pth,
    'diodo':           _sym_diodo_pth,
    'led':             _sym_led_pth,
    'transistor':      _sym_transistor_to92,
    'crystal':         _sym_crystal_hc49,
    'conector':        _sym_conector_pth,
    'ci':              _sym_ci_generico,
    'custom':          _sym_ci_generico,    # padrao/simbolo: custom → CI genérico
}


def _auto_detect_symbol(padrao: str, total_pinos: int, dados: dict):
    """Auto-detecta o melhor template de símbolo baseado no padrão e número de pinos."""
    # Mapeamento direto de padrão
    padrao_map = {
        'bga':      _sym_bga,
        'quad_smd': _sym_castellated,
        'custom':   _sym_ci_generico,
    }
    if padrao in padrao_map:
        return padrao_map[padrao]

    # Auto-detect por número de pinos
    if total_pinos <= 0:
        return _sym_ci_generico
    elif total_pinos == 1:
        return _sym_antena        # single pin → antenna-like
    elif total_pinos == 2:
        return _sym_resistor_pth  # 2 pins → passive (generic resistor shape)
    elif total_pinos == 3:
        return _sym_regulador     # 3 pins → regulator-like (IN/GND/OUT)
    elif total_pinos <= 40:
        return _sym_ci_generico   # standard IC (2 sides)
    else:
        return _sym_castellated   # many pins → 4 sides


def gerar_symbol(dados: dict, caminho_saida: str) -> None:
    """
    Gera o arquivo .kicad_sym para o componente descrito em 'dados'.

    Sistema de prioridade híbrido:
      1. Campo explícito ``simbolo:`` no YAML  (override direto)
      2. Campo ``tipo:`` no YAML               (tipo do componente)
      3. Auto-detecção por ``padrao:`` + contagem de pinos

    Parâmetros
    ----------
    dados         : dicionário carregado do YAML do componente
    caminho_saida : caminho completo do .kicad_sym a ser criado
    """
    tipo      = dados.get('tipo', '')
    padrao    = dados.get('padrao', '')
    simbolo   = dados.get('simbolo', '')      # NEW: override explícito
    nome      = dados.get('nome', 'Componente')
    total_pinos = int(dados.get('pinos', {}).get('total', 0))

    # Componentes com padrao: custom usam "pads:" em vez de "pinos:"
    # → inferir pinos.total para o gerador de símbolo genérico
    if not tipo and padrao and 'pinos' not in dados and 'pads' in dados:
        pads_list = dados['pads']
        # Criar seção pinos sintética para o gerador de símbolo
        dados = dict(dados)  # cópia para não alterar o original
        dados['pinos'] = {'total': len(pads_list)}
        total_pinos = len(pads_list)
        # Se não tem pin_names, gerar a partir dos pads
        if 'pin_names' not in dados:
            dados['pin_names'] = {
                str(p.get('numero', i+1)): p.get('nome', f"Pin_{i+1}")
                for i, p in enumerate(pads_list)
            }
        if 'pin_types' not in dados:
            dados['pin_types'] = {
                str(p.get('numero', i+1)): p.get('tipo_eletrico', 'passive')
                for i, p in enumerate(pads_list)
            }

    # ----- Prioridade 1: campo explícito 'simbolo:' -----
    fn = None
    if simbolo:
        fn = _DISPATCH.get(simbolo)

    # ----- Prioridade 2: campo 'tipo:' -----
    if fn is None and tipo:
        fn = _DISPATCH.get(tipo)

    # ----- Prioridade 3: auto-detecção (padrao + pinos) -----
    if fn is None:
        fn = _auto_detect_symbol(padrao, total_pinos, dados)

    # Identificar qual método foi escolhido para logging
    metodo = 'simbolo' if (simbolo and _DISPATCH.get(simbolo) is fn) else \
             'tipo' if (tipo and _DISPATCH.get(tipo) is fn) else 'auto-detect'

    try:
        # ── Preencher campos que os geradores usam via dados ──────────────
        # Bug #1: Footprint vazio — gerar referência automática
        kicad_cfg = dados.get('kicad', {})
        if not kicad_cfg.get('footprint_lib'):
            # Formato KiCad: "BIBLIOTECA:FOOTPRINT"
            # Usa nome do componente como lib e footprint (biblioteca individual)
            lib_name = kicad_cfg.get('biblioteca', nome)
            dados = dict(dados)  # cópia para não alterar o original
            dados.setdefault('kicad', {})
            if not isinstance(dados['kicad'], dict):
                dados['kicad'] = {}
            dados['kicad']['footprint_lib'] = f"{lib_name}:{nome}"

        # Bug #3: Datasheet vazio — buscar de múltiplos campos
        if not dados.get('datasheet_url') or dados.get('datasheet_url') == '~':
            ds = (kicad_cfg.get('datasheet')
                  or kicad_cfg.get('datasheet_url')
                  or kicad_cfg.get('ficha_tecnica')
                  or dados.get('datasheet')
                  or dados.get('datasheet_url')
                  or '~')
            dados = dict(dados) if not isinstance(dados, dict) else dados
            dados['datasheet_url'] = ds

        sym_content = fn(dados)
        lib_content = _lib([sym_content])

        os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.write(lib_content)

        print(f"  [Symbol] Arquivo gerado: {os.path.basename(caminho_saida)}")
        print(f"  [Symbol] Método: {metodo}  |  Nome: {nome}")
        if simbolo:
            print(f"  [Symbol] simbolo: {simbolo}")
        if tipo:
            print(f"  [Symbol] tipo: {tipo}")
        print(f"  [Symbol] Importar no KiCad: Schematic -> Preferences -> Manage Symbol Libraries")

    except Exception as e:
        print(f"  [Symbol] ERRO ao gerar simbolo: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
