# Achados — missão NINA-B406 (LGA-71)

> Metade da missão era gerar o footprint; a outra metade, anotar o que o gerador
> não deu conta. Este é o segundo. Cada afirmação aqui foi **testada**, não
> suposta — os comandos estão junto.

## Resultado: 71/71

```
pads: oficial=71  gerado=71
=== VEREDITO: 71/71 pads identicos ao oficial | divergentes: 0 ===
```

Comparado com `referencia/NINA_LGA71R_1500X1000X223_PCB.kicad_mod` (footprint
oficial da u-blox), reabrindo pelo Python do KiCad 10.0.3 — não pelo "ok" do CLI.
Estrutura idêntica: 71 pads SMD, 0 de área nula, 30 pads `J×I` (1,15×0,70) + 41
pads `O` (0,70×0,70), extensão 13,70 × 8,70 mm.

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

---

## Prioridade sugerida

| # | Gap | Impacto | Custo |
|---|---|---|---|
| 4 | Ligar a detecção de colisão | **alto** — hoje gera placa errada calado | baixo (o validador já existe) |
| 2 | `origem: pino_1` | alto — remove a conversão manual | baixo |
| 1 | `grupos_pads` | alto — o YAML deixa de ser artefato de build | médio |
| 3 | Keepout | ? | **bloqueado**: falta o UBX-19052230 |

O gap 4 é o de melhor relação impacto/custo e resolve uma classe inteira, não só
esta peça.

## Reproduzir

```bash
python cli.py --json validar modulos_config/NINA_B406.yaml
python cli.py gerar modulos_config/NINA_B406.yaml -o saida --apenas footprint

# comparar com o oficial (Python do KiCad, não o do venv)
cd missoes/nina-b406
"C:\Program Files\KiCad\10.0\bin\python.exe" -c "..."   # script no README
```
