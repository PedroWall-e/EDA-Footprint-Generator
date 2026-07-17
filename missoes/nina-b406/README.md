# Missão: gerar o footprint do u-blox NINA-B406

**Objetivo duplo**: gerar o footprint do NINA-B406 pelo EDA Footprint Generator
**e adaptar o gerador** ao que essa peça exigir. Ela é deliberadamente difícil —
é um caso de estresse do motor `custom`.

**O que torna esta missão diferente**: existe um **gabarito oficial** do
fabricante em `referencia/`. Você não está gerando às cegas — dá para **comparar
pad a pad** e saber objetivamente se acertou. Aproveite isso: é raro.

---

## A peça

**u-blox NINA-B406-00B** — módulo Bluetooth LE com **antena de trilha integrada
no próprio módulo** (é o que a diferencia: o B400 tem conector U.FL e o B401 tem
pino de RF).

| | |
|---|---|
| Encapsulamento | **LGA-71** (71 pads) |
| Dimensões | 15,00 × 10,00 × 2,23 mm |
| LCSC | C6614838 (5 un) · Mouser: 1.645 un |
| Datasheet | `datasheet/NINA-B40.pdf` (UBX-19049405 R09) |

## Por que é um bom caso de estresse

O land pattern tem **quatro pitches diferentes** e pads em fileiras escalonadas
com grupos distintos:

| Grupo | Pitch | Tamanho do pad |
|---|---|---|
| Laterais e fileira da antena | `H` = 1,00 mm | `J`×`I` = 1,15 × 0,70 mm |
| Pinos centrais | `P` = 1,15 mm | `O` = 0,70 × 0,70 mm |
| Fileira interna | `Q` = 1,10 mm | `O` = 0,70 × 0,70 mm |
| Fileira externa | `S` = 1,00 mm | `O` = 0,70 × 0,70 mm |
| GND da antena | — | `ZL` = 0,70 × 0,70 mm |

Nenhum padrão paramétrico (`quad_smd`, `bga`) dá conta: **é `padrao: custom`
com os 71 pads explícitos**, posicionados a partir dos offsets em relação ao
pino 1.

## O que já está pronto aqui

| Arquivo | O que é |
|---|---|
| `datasheet/NINA-B40.pdf` | o datasheet completo (40 páginas) |
| `datasheet/figura7-e-8-pad-dimensions.png` | pág. 30 renderizada a 300 dpi — Figuras 7 e 8, com os detalhes A e B ampliados |
| **`tabela22-cotas.md`** | **a Table 22 já extraída** — os 27 parâmetros (A…ZL) em markdown |
| **`referencia/NINA_LGA71R_1500X1000X223_PCB.kicad_mod`** | **o footprint OFICIAL da u-blox** — o gabarito |
| `ler-datasheet-pdf.md` | como ler datasheet sem torrar contexto (ver abaixo) |

## Como ler o datasheet (regra aprendida na marra)

O `ler-datasheet-pdf.md` traz a regra completa. O essencial:

1. **PyMuPDF (`fitz`) para texto e tabelas** — medido: ~70× mais rápido que
   pypdf, e ainda traz tabelas e vetores.
2. **Detecte se a cota está em figura raster**: numa página,
   `len(get_drawings()) ≈ 0` + `len(get_images()) > 0` = a cota está na imagem.
   Aí renderize **só aquela página** a 300 dpi e use visão.
3. **Nunca** OCR do PDF inteiro. **Nunca** medir pixels do desenho — land
   pattern quase sempre está fora de escala; a verdade está no número cotado.

**Boa notícia para esta missão**: o NINA-B40 é **vetorial com as cotas em texto**
(617+ vetores, 0 imagens na seção mecânica). Por isso a `tabela22-cotas.md` já
existe — foi extração direta, sem visão. A figura renderizada serve só para você
**entender o arranjo** (quais pads pertencem a qual grupo), não para medir.

## O gabarito — use como oráculo

`referencia/NINA_LGA71R_1500X1000X223_PCB.kicad_mod` veio da
[biblioteca Altium oficial da u-blox](https://github.com/u-blox/Altium-Designer-Library),
convertida pelo importador nativo do KiCad.

Verificado (reabrindo pelo Python do KiCad):

```
71 pads · 0 com área nula
30 pads de 1,150 × 0,700 mm   = Table 22  J × I   (laterais/antena)
41 pads de 0,700 × 0,700 mm   = Table 22  O       (central/interna/externa)
extensão: X 13,70 mm · Y 8,70 mm
```

Os tamanhos batem com a tabela de cotas — validação cruzada independente.

### Como comparar o seu resultado com o gabarito

```python
# rodar com o Python do KiCad: "C:\Program Files\KiCad\10.0\bin\python.exe"
import pcbnew
p = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

def pads(lib, nome):
    fp = p.FootprintLoad(lib, nome)
    return {q.GetNumber(): (round(q.GetPosition().x/1e6, 3),
                            round(q.GetPosition().y/1e6, 3),
                            round(q.GetSizeX()/1e6, 3),
                            round(q.GetSizeY()/1e6, 3)) for q in fp.Pads()}

ref = pads("referencia", "NINA_LGA71R_1500X1000X223_PCB")
meu = pads("saida",      "NINA_B406")
for n in sorted(ref, key=lambda x: int(x) if x.isdigit() else 0):
    if ref[n] != meu.get(n):
        print(f"pad {n}: oficial={ref[n]}  gerado={meu.get(n)}")
```

⚠️ **A origem provavelmente vai diferir** (o gabarito pode estar centrado no
módulo; o seu, no pino 1). Compare as **posições relativas** — ou alinhe pelo
pino 1 antes de comparar. Divergência sistemática em todos os pads = offset de
origem, não erro de geometria.

## Passos sugeridos

1. Ler `tabela22-cotas.md` e a figura, e mapear **quais pads pertencem a qual
   grupo** (é a parte que exige olho, não conta).
2. Pegar a **pinagem** no datasheet (seção de pin definition) — nomes e números.
3. Montar o YAML com `padrao: custom` e os 71 pads explícitos, derivando as
   posições dos offsets (`D`, `E`, `F`, `K`, `L`, `M`, `N`, `R`, `T`, `U`, `Y`,
   `ZA1`, `ZA2`, `ZB`) em relação ao pino 1.
4. `python cli.py --json validar <yaml>` → depois `gerar`.
5. **Comparar com o gabarito** (script acima). Iterar até bater.
6. **Anotar o que o gerador não deu conta** — é metade da missão.

## O que o gerador talvez precise ganhar

Hipóteses a confirmar durante o trabalho:

- **Grupos de pads nomeados** no YAML (`laterais`, `central`, `interna`…), com
  pitch e tamanho por grupo, para não escrever 71 pads na mão.
- **Posições relativas ao pino 1** em vez de ao centro — é como o datasheet
  cota, e converter na mão é onde o erro entra.
- **Keepout da antena**: o B406 tem antena de trilha e o datasheet exige área
  livre de cobre embaixo/ao redor. O gerador tem como expressar isso?
- **Deteção de colisão** entre pads, dado que são 4 pitches diferentes.

## Regras que valem aqui

- **Não inventar cota.** Tudo tem que sair da `tabela22-cotas.md` ou do PDF.
  Se faltar, dizer que falta — não estimar.
- **Não extrair footprint da figura.** Ela está fora de escala; serve para
  entender o arranjo, não para medir.
- **Documentação junto** — o `AGENTS.md` deste repo exige atualizar `SKILL.md`,
  `MANUAL_YAML_REFERENCIA.yaml`, `schemas/component.schema.json` e `CHANGELOG.md`
  na mesma alteração, se padrões/campos mudarem.
- **`kicad.modelo_3d`**: se omitir, agora referencia `<nome>.step`
  automaticamente (corrigido em 2026-07-17). Para biblioteca compartilhada, usar
  variável do KiCad: `modelo_3d: "${MINHA_LIB_3DSHAPES}/Peca.step"`.

## Contexto: por que isso importa

No projeto **EDA AS CODE Data Frontier** a regra é: footprint vem do EasyEDA
(`ato create part <LCSC_ID>`); quando a peça não existe lá, vem da **biblioteca
do fabricante**; e **só então** do gerador. O NINA-B406 foi resolvido pela via
do fabricante — então esta missão **não é urgente para aquela placa**.

Ela existe para **fazer o gerador crescer**: se ele der conta de um LGA-71 com
4 pitches e antena integrada, dá conta de quase qualquer módulo. E, como há
gabarito, o sucesso é **medível** — não é opinião.
