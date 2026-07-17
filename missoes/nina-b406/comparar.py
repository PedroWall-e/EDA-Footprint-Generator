"""Compara o footprint gerado com o oficial da u-blox — por GEOMETRIA.

Rodar com o Python do KiCad:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" missoes/nina-b406/comparar.py

Por que nao usar o script do README: ele compara (x, y, sizeX, sizeY) como
texto e IGNORA a rotacao do pad. Um pad 1,15x0,70 girado 90 tem o mesmo
sizeX/sizeY de um nao girado, mas ocupa cobre TRANSPOSTO. Confiar nele deu
"71/71 identicos" para um footprint cujos pads laterais estavam em curto.

Aqui compara-se a extensao real do cobre (bounding box com a rotacao aplicada)
e checa-se sobreposicao entre pads.
"""
import collections
import sys

import pcbnew

MM = 1e6
LIB_REF, FP_REF = 'referencia', 'NINA_LGA71R_1500X1000X223_PCB'


def extensao(q):
    """(w, h) do cobre no eixo X/Y, ja com a rotacao do pad aplicada."""
    w, h = q.GetSizeX() / MM, q.GetSizeY() / MM
    ang = round(q.GetOrientationDegrees()) % 180
    if ang == 90:
        w, h = h, w
    elif ang != 0:
        raise SystemExit(f'pad {q.GetNumber()}: rotacao {ang} nao suportada aqui')
    return round(w, 3), round(h, 3)


def ler(lib, nome):
    p = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    fp = p.FootprintLoad(lib, nome)
    out = {}
    for q in fp.Pads():
        w, h = extensao(q)
        out[q.GetNumber()] = (round(q.GetPosition().x / MM, 3),
                              round(q.GetPosition().y / MM, 3), w, h)
    return out


def colisoes(pads):
    """Pares de pads cujo cobre se sobrepoe (numeros diferentes = curto)."""
    itens = list(pads.items())
    out = []
    for i in range(len(itens)):
        for j in range(i + 1, len(itens)):
            (na, a), (nb, b) = itens[i], itens[j]
            if na == nb:
                continue          # mesmo net (ex.: pads de um mesmo pino)
            ox = (a[2] + b[2]) / 2 - abs(a[0] - b[0])
            oy = (a[3] + b[3]) / 2 - abs(a[1] - b[1])
            if ox > 1e-6 and oy > 1e-6:
                out.append((na, nb, round(min(ox, oy), 3)))
    return out


def main():
    lib_meu = sys.argv[1] if len(sys.argv) > 1 else '_g'
    fp_meu = sys.argv[2] if len(sys.argv) > 2 else 'NINA_B406'

    ref, meu = ler(LIB_REF, FP_REF), ler(lib_meu, fp_meu)
    print(f'pads: oficial={len(ref)}  gerado={len(meu)}')

    dif = [n for n in ref if ref[n] != meu.get(n)]
    for n in sorted(dif, key=lambda x: int(x))[:12]:
        print(f'  pad {n}: oficial={ref[n]}  gerado={meu.get(n)}')
    print(f'\n=== geometria: {len(ref) - len(dif)}/{len(ref)} pads identicos '
          f'| divergentes: {len(dif)} ===')

    for rot, pads in (('OFICIAL', ref), ('GERADO', meu)):
        c = colisoes(pads)
        print(f'  {rot}: {len(c)} sobreposicoes' + (f' -> {c[:3]}' if c else ' (ok)'))

    tam = collections.Counter((p[2], p[3]) for p in meu.values())
    print(f'  extensoes de cobre no gerado: {dict(tam)}')
    return 1 if dif else 0


if __name__ == '__main__':
    raise SystemExit(main())
