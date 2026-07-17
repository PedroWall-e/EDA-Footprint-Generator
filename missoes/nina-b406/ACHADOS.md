# Achados — missão NINA-B406 (LGA-71)

> Metade da missão era gerar o footprint; a outra metade, anotar o que o gerador
> não deu conta. Este é o segundo. Cada afirmação aqui foi **testada**, não
> suposta — os comandos estão junto.

## Resultado: 71/71 — mas só na segunda tentativa

```
=== geometria: 71/71 pads identicos | divergentes: 0 ===
  OFICIAL: 0 sobreposicoes (ok)
  GERADO:  0 sobreposicoes (ok)
```

Comparado com `referencia/NINA_LGA71R_1500X1000X223_PCB.kicad_mod` (footprint
oficial da u-blox), reabrindo pelo Python do KiCad 10.0.3 — não pelo "ok" do CLI.
Estrutura idêntica: 71 pads SMD, 0 de área nula, extensão 13,70 × 8,70 mm.

> ⚠️ **A primeira versão passou no teste do README e estava fisicamente
> quebrada.** Ler a seção seguinte antes de confiar no número acima.

## O erro mais instrutivo da missão: o gabarito não é o oráculo — a geometria é

A primeira versão deu **"71/71 idênticos"** pelo script do README. Estava errada:
os pads laterais ficavam **em curto**.

O script do README compara `(x, y, GetSizeX, GetSizeY)` e **ignora
`GetOrientationDegrees()`**. O footprint oficial tem **32 pads girados 90°**; o
meu, nenhum. Um pad 1,15×0,70 girado 90° tem *o mesmo* sizeX/sizeY de um não
girado — e ocupa cobre **transposto**. O script não vê diferença; a placa vê.

```
OFICIAL  rotacoes: {90.0: 32, 0.0: 39}
MEU (v1) rotacoes: {0.0: 71}
```

Consequência concreta: os pads 1..10 mediam 1,15 mm em X com pitch `H`=1,00 →
**sobreposição de 0,15 mm entre pads vizinhos**.

**A causa foi de leitura de cota, não de código.** A Table 22 diz:

- `J` = "Lateral and antenna row pin **length**" = 1,15
- `I` = "Lateral, antenna row and outer pin **width**" = 0,70

São medidas **semânticas**, não presas a X/Y: o *comprimento* entra
**perpendicular à borda** que o pad ocupa; a *largura* corre **ao longo** dela.
Mapeei `J → largura` em todos os grupos. O correto:

| Fileira | Corre em | (largura, altura) |
|---|---|---|
| Laterais (1–10, 16–25) | X | `(I, J)` = (0,70, 1,15) |
| Antena (11–15) e coluna esq. (26–30) | Y | `(J, I)` = (1,15, 0,70) |

Os outros 12 pads girados no oficial (56–67) são **quadrados** 0,70×0,70 — girar
não muda nada. Só 20 pads importavam.

### O que isso ensina sobre verificação

Três verificadores disseram "ok" para um footprint com pads em curto:

| Verificador | Veredito | Por quê falhou |
|---|---|---|
| `cli.py validar` (IPC + schema) | `ok: true` | não checa sobreposição |
| Script de comparação do README | `71/71 idênticos` | ignora rotação |
| `cli.py gerar` | `✅` | idem |

Quem pegou foi a **checagem de colisão** — justamente o gap 4 deste documento.
Escrevi o teste para saber se ligar a colisão quebraria presets; ele quebrou o
**meu próprio footprint**. Sem ele, isto teria ido para a placa.

`comparar.py` (nesta pasta) substitui o script do README: compara a **extensão
real do cobre** (bounding box com rotação aplicada) e checa sobreposição nos dois
footprints.

```bash
"C:\Program Files\KiCad\10.0\bin\python.exe" missoes/nina-b406/comparar.py
```

> **Sugestão para o README da missão**: o script de comparação que ele oferece
> dá falso positivo. Vale trocá-lo por `comparar.py`.

**Nenhuma coordenada foi copiada do gabarito.** As 71 posições foram derivadas
só da Table 22 e *depois* conferidas contra o oficial (script:
`derivar_nina.py` → 71/71 antes de existir YAML). O gabarito foi oráculo, não
fonte.

### Sobre o offset de origem que o README previa

Não houve. O README avisava que a origem provavelmente difere (gabarito no
centro, meu no pino 1). O aviso era razoável, mas a conversão saiu das próprias
cotas e caiu exata:

```
x = -A/2 + D + dx = -7,5 + 1,80 + dx     ->  pino 1 em x = -5,700  ✓ oficial
y = +B/2 - E - dy = +5,0 - 0,875 - dy    ->  pino 1 em y = +4,125  ✓ oficial
```

Isso também **valida a Table 22 de forma cruzada**: `D` e `E` preveem o pino 1
do footprint do fabricante na casa dos micrometros.

## O arranjo (derivado das cotas, confirmado pelo gabarito)

| Grupo | Pinos | n | Regra | Cotas |
|---|---|---|---|---|
| Lateral inferior | 1–10 | 10 | pino 1 na origem, `+k·H` | `H`, `J×I` |
| Fileira da antena | 11–15 | 5 | `dx=R`, `dy=F+k·H` | `R`, `F`, `H` |
| Lateral superior | 16–25 | 10 | `dy=B−2E`, dx decrescente | `B`, `E`, `H` |
| Coluna lateral esq. | 26–30 | 5 | `dx=Y`, dy decrescente | `Y`, `F`, `H` |
| Interna inferior | 31–36 | 6 | `dy=N`, `dx=M+k·Q` | `M`, `N`, `Q`, `O` |
| Interna superior | 37–42 | 6 | `dy=(B−2E)−N` | idem |
| Interna coluna esq. | 43–46 | 4 | `dx=M`, `dy=N+k·Q` | idem |
| Externa | 47–55 | 9 | `dx=−U`, `dy=T+k·S` | `U`, `T`, `S`, `O` |
| Central | 56–67 | 12 | grade 4×4 (`K−3P…K` × `L…L+3P`) menos 4 | `K`, `L`, `P`, `O` |
| GND da antena | 68–71 | 4 | `dx=ZA1/ZA2`, `dy=−ZB` e `(B−2E)+ZB` | `ZA1`, `ZA2`, `ZB`, `ZL` |

`B−2E = 8,25` (vão entre as fileiras laterais) é **derivado**, não cotado: cada
lateral está a `E` da sua borda num módulo de largura `B`.

O bloco central é uma grade 4×4 onde as colunas `K−3P` e `K−P` têm só as duas
linhas do meio. **Isso não é cota** — é *quais pads existem*, e saiu do
gabarito/figura. É o único ponto onde a figura seria indispensável.

### Pinagem (Table 6, extraída do PDF)

- **1–55**: nomes próprios (`GPIO_1`, `XL1/GPIO_2`, `USB_DP`…). GND em 6, 12,
  14, 26, 30, 53.
- **56–67**: o datasheet chama de **EGP** — *"The exposed pins in the center of
  the module should be connected to GND"*.
- **68–71**: **EAGP** — *"The exposed pins underneath the antenna area should be
  connected to GND"*.

⚠️ **O datasheet não numera os EGP/EAGP.** A numeração 56–71 vem do footprint
oficial da u-blox, não do PDF. Quem gerar sem o gabarito não tem como saber.

---

# O que o gerador NÃO deu conta

## 1. Grupos de pads — CONFIRMADO (é o gap central)

A peça são **14 corridas lineares** (`início + k·passo`). O `padrao: custom`
exige **71 pads com `x`/`y` absolutos**. Resultado: um YAML de 129 linhas com 71
coordenadas calculadas na mão.

O sintoma que denuncia o problema: **eu não escrevi o YAML — escrevi um script
que escreve o YAML** (`emitir_yaml.py`). Ou seja, o YAML virou *artefato de
build*, e a fonte de verdade real ficou fora do repositório. Se uma cota mudar,
o YAML não se atualiza: tem que rodar o script de novo.

Isso também apaga a rastreabilidade: no YAML lê-se `x: -4.7`, não `pino 2 =
pino 1 + H`. Ninguém revisa 71 números soltos contra um datasheet.

**Proposta** — `grupos_pads`, uma lista de corridas:

```yaml
padrao: custom
origem: pino_1                    # ver gap 2
grupos_pads:
  - nome: lateral_inferior
    numero_inicial: 1
    n: 10
    inicio: {x: 0, y: 0}
    passo:  {x: 1.00, y: 0}       # H
    tamanho: {largura: 1.15, altura: 0.70}   # J x I
  - nome: fileira_antena
    numero_inicial: 11
    n: 5
    inicio: {x: 8.925, y: 2.125}  # R, F
    passo:  {x: 0, y: 1.00}       # H
    tamanho: {largura: 1.15, altura: 0.70}
  # ... 12 outras corridas
```

71 pads → 14 blocos, cada um espelhando uma linha da Table 22. `pads:` explícito
continua valendo para o caso irregular (e para o bloco central, que é 4 corridas).

## 2. Posições relativas ao pino 1 — CONFIRMADO

**As 27 cotas da Table 22 são todas relativas ao pino 1** (`D`, `E`, `F`, `K`,
`L`, `M`, `N`, `R`, `T`, `U`, `Y`, `ZA1`, `ZA2`, `ZB`). O gerador só aceita
absoluto. Tive que aplicar a conversão à mão:

```
x = -A/2 + D + dx
y = +B/2 - E - dy      (Y do KiCad cresce para baixo; o datasheet, para cima)
```

Três armadilhas aí, todas silenciosas se erradas: o sinal do Y, o `-A/2 + D`, e
o fato de `dy` do datasheet ser oposto ao do KiCad. **É exatamente onde o erro
entra** — e é mecânico, então deveria ser do gerador, não do humano.

**Proposta**: `origem: pino_1` (default `centro`), com o gerador aplicando a
conversão a partir de `A`, `B`, `D`, `E`.

## 3. Keepout da antena — **REFUTADO** (o dado não existe aqui)

O README supõe: *"o datasheet exige área livre de cobre embaixo/ao redor"*.
**Não exige — não neste documento.** Procurei no PDF inteiro:

```
'keep-out' / 'keepout' / 'keep out' / 'clearance' / 'restricted'  -> 0 ocorrências
'antenna area'                                                     -> só a pág. 19
```

O que a pág. 19 diz é sobre **conectar ao GND**, não sobre manter livre:
> "The exposed pins underneath the antenna area should be connected to GND"

E a pág. 10 remete a outro documento:
> "See the NINA-B4 **system integration manual [3]** for Antenna reference
> designs and integration"

Esse manual (**UBX-19052230**) **não está na pasta da missão**. Pela regra "se
faltar dado, diga que falta — não estime": **falta o dado**. Não dá para
implementar keepout do B406 sem ele, e qualquer número seria inventado.

> A pergunta "o gerador tem como expressar keepout?" segue **em aberto e válida**
> (a resposta hoje é não: não há campo nem camada de keepout). Mas o NINA-B406
> não é o caso de teste para isso — não há cota para conferir. Para atacar
> keepout, buscar o UBX-19052230 primeiro.

## 4. Detecção de colisão — CONFIRMADO, e pior que a hipótese

Não é que falte: **existe e nunca é chamado.**

```
$ git grep -n "validate_pad_clearance" -- core/ | grep -v "def "
  (vazio — ninguém chama)
```

`footprint_helpers.validate_pad_clearance` é **código morto**. Teste com dois
pads de 1×1 mm com centros a 0,1 mm (sobreposição de 0,9 mm):

```
$ python cli.py --json validar /tmp/colisao.yaml
{ "ok": true, "erros": [], "avisos": [] }
```

Gera limpo. Nem IPC, nem schema, nem o validador que existe.

É grave justamente no `custom`: nos padrões paramétricos as posições são
calculadas (colidir é difícil); no `custom` você as escreve à mão — é o único
lugar onde dá para colidir, e é o único sem rede. Um LGA-71 com 4 pitches é
precisamente onde um dedo trocado passa despercebido.

**Proposta**: chamar `validate_pad_clearance` no `custom` (no mínimo), com a
folga IPC como limite; sobreposição = erro, folga curta = aviso.

### O que a colisão pegaria hoje: 2 presets da biblioteca estão quebrados

Rodei a checagem de colisão nos 41 presets. Além do meu bug, ela achou **defeitos
reais e pré-existentes**:

```
Conn_01x03          : 1 sobreposicao  -> pads 1 e 2 AMBOS em (0,0)
Conn_01x06_PinHeader: 3 sobreposicoes -> pads 1&6, 2&5, 3&4 coincidentes
```

`header_3pin.yaml` declara `total: 3` e o footprint sai com **2 pads empilhados
na origem**:

```
YAML pede total: 3  ->  gerou 2 pads
    pad 1 em (0.0, 0.0)
    pad 2 em (0.0, 0.0)
```

**Causa raiz** — `tipo: conector_pth` cai no shim para **`dual_pth`**, que é para
componentes de **duas fileiras** (DIP):

```python
'conector_pth': 'dual_pth',                       # _TIPO_PARA_PADRAO
meio        = total // 2                          # 3 // 2 = 1  -> perde 1 pino
afastamento = _float(dados, 'corpo', 'afastamento_colunas')   # ausente -> 0.0
x_esq, x_dir = -afastamento/2, +afastamento/2     # ambos 0 -> colunas colapsam
```

Um pin header 1×N é de **uma fileira**, não duas. Dois erros se somam: `total//2`
descarta o pino ímpar e `afastamento_colunas` sem default junta as colunas em
x=0. Os dois presets validam `ok: true`.

> Fora do escopo do NINA-B406, mas achado por ele. `Conn_01x03` e
> `Conn_01x06_PinHeader` produzem footprints inutilizáveis hoje — vale um issue
> próprio. O `dual_pth` precisa de um caminho de fileira única (ou um padrão
> `single_row`), e `afastamento_colunas` não deveria ter default silencioso 0.

## 5. Rotação de pad — CONFIRMADO (gap novo, não previsto no README)

O `custom` **não tem campo de rotação**:

```
$ sed -n '/^def _gerar_custom/,/save_footprint/p' core/gerador_footprint_v2.py | grep -i rota
  (nada)
```

Para este LGA deu para contornar trocando `largura`/`altura` (num retângulo,
girar 90° ≡ transpor w/h) — foi o que fiz. Mas:

- o contorno é **outra conversão mental** que o humano faz e erra, exatamente
  como a do gap 2;
- para ângulos que não sejam múltiplos de 90° (conectores circulares, pads
  radiais) **não há contorno**: é impossível expressar hoje.

## 6. Typo em campo opcional de pad — CONFIRMADO (menor do que eu afirmei)

> **Correção**: minha primeira versão deste achado dizia que *"o schema não
> valida os campos de pad"*. **Estava errado.** Eu li
> `pads.items.properties` e vi `[]` — mas `items` é um **`$ref` para
> `$defs/custom_pad`**, e minha checagem não seguiu a referência. O
> `custom_pad` define os 11 campos e exige `x`, `y`, `largura`, `altura`.
> Um typo em campo **obrigatório** já era pego:
> `largara: 1.15` → *"'largura' is a required property"* ✓

O gap real é bem menor: `custom_pad` não declarava `additionalProperties`, então
um typo em campo **opcional** passava calado. Testado:

```yaml
- {numero: 1, x: 0, y: 0, largura: 1.15, altura: 0.7,
   formto: circulo, montgem: pth, buraco: 0.8}     # 3 typos
```
```
validar -> ok: true
pad 1   -> shape=rect  attr=SMD  drill=0.0
        (o autor pediu circulo PTH com furo 0,8)
```

Validava, gerava, e entregava um pad **retangular SMD sem furo** — sem um aviso.

**Corrigido**: `custom_pad.additionalProperties: false`. Agora:
`"Additional properties are not allowed ('buraco', 'formto', 'montgem' were unexpected)"`.
Os 41 presets seguem validando.

---

## Prioridade sugerida

| # | Gap | Impacto | Custo |
|---|---|---|---|
| 4 | **Ligar a detecção de colisão** | **crítico** — pegaria meu bug e 2 presets quebrados | **baixo** (o validador já existe) |
| — | Corrigir `conector_pth` de fileira única | **alto** — 2 presets inutilizáveis hoje | baixo |
| 6 | Declarar os campos de pad no schema | alto — typo hoje passa calado | baixo |
| 2 | `origem: pino_1` | alto — remove a conversão manual | baixo |
| 5 | `rotacao` de pad | médio — contornável em 90°, impossível fora | baixo |
| 1 | `grupos_pads` | alto — o YAML deixa de ser artefato de build | médio |
| 3 | Keepout | ? | **bloqueado**: falta o UBX-19052230 |

O **gap 4 é disparado o melhor investimento**: o validador já existe, e ligá-lo
teria pego (a) o meu footprint em curto e (b) dois presets quebrados na
biblioteca. Não é hipótese — é o que ele achou nos 41 presets em uma rodada.

## A lição que atravessa tudo

Os quatro achados são o **mesmo padrão**: *o gerador aceita, produz, e não avisa
que está errado.*

| | |
|---|---|
| `.step` órfão (corrigido antes) | gerava sem referência 3D |
| `overrides` em lista | ignorado em silêncio |
| Meu footprint girado | 3 verificadores disseram "ok" |
| `Conn_01x03` | 3 pinos → 2 pads empilhados, `ok: true` |

Um gerador de footprint que erra **em silêncio** produz placa errada. O valor de
"gerar sem erro" é zero se "sem erro" não quer dizer "certo". A lacuna do gerador
não é de features — é de **desconfiança de si mesmo**.

## Reproduzir

```bash
python cli.py --json validar modulos_config/NINA_B406.yaml
python cli.py gerar modulos_config/NINA_B406.yaml -o saida --apenas footprint

# comparar com o oficial (Python do KiCad, não o do venv)
cd missoes/nina-b406
"C:\Program Files\KiCad\10.0\bin\python.exe" -c "..."   # script no README
```
