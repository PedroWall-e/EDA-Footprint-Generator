---
name: footprint-de-datasheet
description: |
  Skill para criar o footprint de um módulo/CI a partir do DATASHEET, quando não
  existe preset — LGA, castellated, BGA, QFN e módulos RF (u-blox NINA, Globalstar
  STX3, Quectel, Qualcomm, Nordic, ESP32...). Use quando o usuário pedir para
  gerar footprint a partir de um PDF/datasheet, extrair land pattern, ou quando a
  peça tem pitch irregular, muitos pads, ou não encaixa em padrão paramétrico.
  Palavras-chave: datasheet, land pattern, PDF, cota, módulo, LGA, castellated,
  BGA, QFN, pitch irregular, footprint do zero, u-blox, Globalstar, Quectel.
---

# Skill: Footprint a partir do datasheet

Procedimento para transformar um datasheet em footprint **verificado**. Cada
regra aqui saiu de um erro real desta base — as duas peças de referência
(NINA-B406 LGA-71 e Globalstar STX3) estão em `missoes/`, e o relato do que deu
errado está em `missoes/nina-b406/ACHADOS.md`.

## A regra que atravessa tudo

> **"Gerou sem erro" não quer dizer "está certo".**

Um footprint errado vira placa errada. Nesta base já aconteceu de **três**
verificadores (`validar` com IPC+schema, `gerar`, e um script de comparação)
darem "ok" para um footprint cujos pads laterais estavam **em curto**. Geração
não é o gargalo — **verificação** é. Termine sempre pelo passo 6.

---

## 1. Ler o datasheet sem torrar contexto

```python
import fitz                      # PyMuPDF: ~70x mais rápido que pypdf
d = fitz.open('datasheet.pdf')
for i, pg in enumerate(d):
    print(i+1, len(pg.get_drawings()), len(pg.get_images()), len(pg.get_text()))
```

- **Vetorial com cotas em texto** (`get_drawings()` alto, `get_images()` ≈ 0):
  extraia direto, sem visão. É o caso do NINA-B40.
- **Cota em raster** (`get_drawings()` ≈ 0 + `get_images()` > 0): renderize **só
  aquela página** a 300 dpi e use visão. É o caso do STX3.
- **Nunca** OCR do PDF inteiro. **Nunca** medir pixels do desenho: land pattern
  quase sempre está fora de escala. A verdade está no **número cotado**.
- No Windows, force UTF-8 (`PYTHONUTF8=1`) — emojis/símbolos do PDF quebram o
  `print` em cp1252.

**Procure, nesta ordem:** a tabela de cotas do land pattern (`Table N`), a figura
do land pattern recomendado, a figura de pinagem, e a tabela de pin definition
(nomes e tipos).

## 2. Nunca invente cota

- Todo número sai da tabela de cotas ou do texto do PDF.
- **Se faltar, diga que falta.** Não estime, não "escolha o que cabe".
- Sintoma de cota inventada (real, no `Stx3.yaml`):
  `pitch: 1.778 # único pitch padrão que cabe 16 pinos em 28.70mm`
  — um número escolhido para caber numa **suposição**, não lido do datasheet.
  A suposição estava errada e a peça inteira saiu errada.

## 3. A armadilha da orientação do pad

Quando o datasheet cota **"pin length" × "pin width"**, essas medidas são
**semânticas, não presas a X/Y**:

> o **comprimento** entra **perpendicular** à borda que o pad ocupa;
> a **largura** corre **ao longo** dela.

| Fileira corre em | (largura, altura) |
|---|---|
| X (fileiras de cima/baixo) | (width, length) |
| Y (colunas esquerda/direita) | (length, width) |

**Foi aqui que nasceu o pior bug da missão NINA**: mapear `J`(length)→largura em
todos os grupos fez os pads laterais medirem 1,15 mm em X com pitch 1,00 —
**sobreposição de 0,15 mm, pinos em curto**. O footprint oficial expressa o mesmo
com `size=(J,I)` + rotação 90°.

## 4. O datum: feche a conta nos DOIS eixos

Offsets como "borda → primeiro pad" medem a partir de linhas de referência. Para
descobrir de onde:

1. Some cada eixo: `offset + (n-1)×pitch + pad + offset`.
2. Compare com a dimensão do módulo.
3. **A sobra tem que ser a MESMA nos dois eixos.** Se for, você achou o recuo e o
   datum. Se não, sua leitura está errada.

Exemplo real (STX3): horizontal `.810 - .750 = .060`; vertical
`1.130 - 1.070 = .060` → **`.030`/lado nos dois eixos** ⇒ as linhas de referência
são as *centerlines* dos pads.

> Eu declarei o STX3 "bloqueado por falta de dado" tendo calculado `1.070 ≠ 1.130`
> e **não percebido que o horizontal errava pelos mesmos `.060`**. A coincidência
> *era* a prova. Feche os dois eixos antes de dizer que falta dado.

E cuidado com **quem é simétrico**: no STX3, `.117 ≠ .153` tornam a coluna
assimétrica **de propósito** — quem centra a coluna desloca o campo inteiro
(0,46 mm de erro no silk, achado real).

## 5. Escrever o YAML: declare a REGRA, não o resultado

**Use `grupos_pads`.** Um módulo é quase todo feito de corridas, que é como o
datasheet cota. Cada bloco espelha uma linha da tabela de cotas:

```yaml
origem:
  referencia: pino_1                       # o datasheet cota a partir do pino 1
  da_borda: {esquerda: 1.80, base: 0.875}  # D e E — o gerador converge p/ o centro

grupos_pads:
  - nome: lateral_inferior
    numero_inicial: 1
    n: 10
    inicio: {x: 0, y: 0}                   # relativo ao pino 1
    passo:  {x: 1.00, y: 0}                # H
    tamanho: {largura: 0.70, altura: 1.15} # I x J  (ver passo 3!)
    nomes: ["GPIO_1", "XL1/GPIO_2", ...]

  - nome: base                             # pitch IRREGULAR
    n: 7
    inicio: {x: -8.128, y: 13.589}
    passos: [2.54, 2.54, 2.54, 3.048, 3.048, 2.54]
    eixo: x
    tamanho: {largura: 1.93, altura: 2.032}
```

- `grupos_pads` (regular) + `pads` (irregular) **somam** e cobrem qualquer peça.
- **Não escreva N pads explícitos.** Referência: NINA-B406 = 71 pads em **14
  blocos**; STX3 = 32 em **4**. Se você está prestes a emitir dezenas de
  coordenadas absolutas, pare: o YAML vira artefato de build, ninguém o revisa
  contra o datasheet, e é exatamente onde o erro se esconde.
- **Não escreva um script que escreve o YAML.** Se parecer necessário, a peça
  provavelmente cabe em `grupos_pads` e você ainda não viu a corrida.
- `Y` segue o KiCad (cresce para **baixo**). Datasheet costuma cotar para cima →
  os `dy` entram negados.

## 6. Verificar — este passo não é opcional

```bash
python cli.py --json validar <yaml>
python cli.py gerar <yaml> -o saida/        # footprint + símbolo + 3D

# SEMPRE (acha o .kicad_sym irmão e confere símbolo×footprint junto):
python cli.py conferir saida/<Nome>.kicad_mod

# se existir footprint oficial do fabricante (use como oráculo!):
python cli.py conferir saida/<Nome>.kicad_mod --gabarito <oficial.kicad_mod>
```

`conferir` compara **geometria** (com a rotação aplicada), não texto, e acusa
sobreposição. Um deslocamento **igual em todos os pads** ele reporta como
**offset de origem**, não como N erros — as posições relativas batem.

Gere **os dois artefatos** (não só o footprint): o `conferir` também casa os
**números de pino do símbolo com os pads** — o KiCad liga pino↔pad pelo número,
e um símbolo que não casa passa despercebido até o netlist. **Pino sem pad** é
erro (net sem cobre); **pad sem pino** é aviso (cobre sem net, ex.: `EP`/aba).

**Procure um gabarito antes de gerar**: biblioteca do fabricante (Altium/KiCad),
EasyEDA/LCSC, ou o Reference Design. Com gabarito o sucesso é **medível**. Sem
ele, a checagem de colisão e o fechamento do passo 4 são a sua rede.

Derive **sempre das cotas** e use o gabarito só para **conferir** — nunca copie
coordenadas dele. Foi assim que o NINA fechou 71/71: a derivação bateu com o
oficial *antes* de existir YAML.

## 7. Documentação junto (`.agents/AGENTS.md`)

Se mexer em padrões, campos do YAML ou presets, atualize na **mesma alteração**:
`SKILL.md`, `docs/MANUAL_YAML_REFERENCIA.yaml`, `schemas/component.schema.json`
e `CHANGELOG.md`.

---

## Checklist

- [ ] Cotas extraídas do PDF (nenhuma medida em figura, nenhuma estimada)
- [ ] Faltou dado? → **disse que faltou**, não estimou
- [ ] Orientação do pad conferida (comprimento ⊥ à borda) — passo 3
- [ ] Datum fechado nos **dois** eixos, com a mesma sobra — passo 4
- [ ] YAML em `grupos_pads` (não N pads explícitos, não script externo)
- [ ] `conferir` rodado: **0 sobreposições**
- [ ] Símbolo gerado e conferido: **todo pino tem pad** (sem "pino sem pad")
- [ ] Gabarito procurado; se existe, **100% dos pads idênticos**
- [ ] Docs atualizadas junto
