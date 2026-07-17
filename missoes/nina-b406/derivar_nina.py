"""Deriva os 71 pads do NINA-B406 SO a partir da Table 22 (tabela22-cotas.md).

Nenhuma coordenada e' copiada do gabarito: tudo sai das cotas. O gabarito e'
usado apenas para CONFERIR o resultado.
"""

# --- Table 22 (tabela22-cotas.md) — unica fonte de numeros ---
A   = 15.0    # Module PCB length
B   = 10.0    # Module PCB width
D   = 1.80    # Horizontal edge to pin 1 center
E   = 0.875   # Vertical edge to pin 1 center
F   = 2.125   # Vertical pin 1 center to lateral pin center
H   = 1.00    # Lateral and antenna row pin to pin pitch
I   = 0.70    # Lateral, antenna row and outer pin width
J   = 1.15    # Lateral and antenna row pin length
K   = 6.225   # Horizontal pin 1 center to central pin center
L   = 2.40    # Vertical pin 1 center to central pin center
M   = 1.45    # Horizontal pin 1 center to inner row pin center
N   = 1.375   # Vertical pin 1 center to inner row pin center
O   = 0.70    # Central, inner and outer row pin width and length
P   = 1.15    # Central pin to central pin pitch
Q   = 1.10    # Inner row pin to pin pitch
R   = 8.925   # Horizontal pin 1 center to antenna row pin center
S   = 1.00    # Outer row pin to pin pitch
T   = 0.125   # Vertical pin 1 center to outer row pin center
U   = 1.15    # Horizontal pin 1 center to outer row pin center
Y   = 0.075   # Horizontal pin 1 center to lateral pin center
ZA1 = 10.0    # Horizontal pin 1 center to first set of antenna GND
ZA2 = 12.55   # Horizontal pin 1 center to second set of antenna GND
ZB  = 0.225   # Vertical pin 1 center to antenna GND pin center
ZL  = 0.70    # Antenna GND pin width and length

# Vao vertical entre as duas fileiras laterais: cada uma esta a E da sua borda,
# num modulo de largura B. Derivado, nao inventado.
VS = B - 2 * E          # 8.25

# ORIENTACAO DOS PADS RETANGULARES — nao e' detalhe cosmetico.
# A Table 22 cota J como "pin LENGTH" e I como "pin WIDTH": sao medidas
# SEMANTICAS, nao presas a X/Y. O comprimento J entra PERPENDICULAR a borda
# que o pad ocupa; a largura I corre AO LONGO dela. Entao:
#   - fileira que corre em X (laterais)  -> w = I, h = J
#   - fileira que corre em Y (antena, coluna esquerda) -> w = J, h = I
# Mapear J -> largura em todos os grupos faz os pads laterais medirem 1,15 em X
# com pitch de 1,00: SOBREPOSICAO de 0,15 mm, ou seja, pads em curto.
# (O footprint oficial expressa o mesmo com size=(J,I) + rotacao 90.)
LAT_X = (I, J)   # (0.70, 1.15) — fileira ao longo de X
LAT_Y = (J, I)   # (1.15, 0.70) — fileira ao longo de Y

pads = {}   # n -> (dx, dy, w, h) relativo ao pino 1, dy positivo "para cima"

# 1..10 — lateral inferior (pino 1 na origem), pitch H — corre em X
for k in range(10):
    pads[1 + k] = (k * H, 0.0, *LAT_X)

# 11..15 — fileira da antena: dx = R, subindo de F com pitch H — corre em Y
for k in range(5):
    pads[11 + k] = (R, F + k * H, *LAT_Y)

# 16..25 — lateral superior: dy = VS, dx decrescente — corre em X
for k in range(10):
    pads[16 + k] = ((9 - k) * H, VS, *LAT_X)

# 26..30 — coluna lateral esquerda: dx = Y, dy decrescente — corre em Y
for k in range(5):
    pads[26 + k] = (Y, F + (4 - k) * H, *LAT_Y)

# 31..36 — fileira interna inferior: dy = N, dx de M com pitch Q
for k in range(6):
    pads[31 + k] = (M + k * Q, N, O, O)

# 37..42 — fileira interna superior (espelho): dy = VS - N, dx decrescente
for k in range(6):
    pads[37 + k] = (M + (5 - k) * Q, VS - N, O, O)

# 43..46 — coluna interna esquerda: dx = M, dy decrescente
for k in range(4):
    pads[43 + k] = (M, N + (4 - k) * Q, O, O)

# 47..55 — fileira externa: dx = -U (a esquerda do pino 1), dy de T com pitch S
for k in range(9):
    pads[47 + k] = (-U, T + (8 - k) * S, O, O)

# 56..67 — bloco central: grade 4x4 (colunas K-3P..K, linhas L..L+3P).
# As colunas K-3P e K-P tem so as duas linhas do meio — arranjo lido do
# datasheet/gabarito (quais pads existem), nao uma cota.
col = [K - 3 * P, K - 2 * P, K - P, K]      # 2.775, 3.925, 5.075, 6.225
row = [L + i * P for i in range(4)]         # 2.400, 3.550, 4.700, 5.850
central = [
    (col[0], row[1]), (col[0], row[2]),                                  # 56, 57
    (col[1], row[0]), (col[1], row[1]), (col[1], row[2]), (col[1], row[3]),  # 58..61
    (col[2], row[1]), (col[2], row[2]),                                  # 62, 63
    (col[3], row[0]), (col[3], row[1]), (col[3], row[2]), (col[3], row[3]),  # 64..67
]
for k, (cx, cy) in enumerate(central):
    pads[56 + k] = (cx, cy, O, O)

# 68..71 — GND da antena: dois conjuntos (ZA1, ZA2), abaixo e acima
pads[68] = (ZA1, -ZB, ZL, ZL)
pads[69] = (ZA2, -ZB, ZL, ZL)
pads[70] = (ZA2, VS + ZB, ZL, ZL)
pads[71] = (ZA1, VS + ZB, ZL, ZL)


if __name__ == '__main__':
    assert len(pads) == 71, f'esperado 71 pads, derivados {len(pads)}'
    for n in sorted(pads):
        dx, dy, w, h = pads[n]
        print(f'{n:3d} {dx:+8.3f} {dy:+8.3f}  {w:.2f}  {h:.2f}')
