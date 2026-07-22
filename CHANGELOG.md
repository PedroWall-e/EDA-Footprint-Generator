# Changelog

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Corrigido
- **Pinos de símbolo caíam fora da grade do esquemático — 15 dos 41.** A largura (e, no castellated, a altura) do corpo saía de um cálculo livre a partir do comprimento dos nomes dos pinos, e o pino, em ±corpo/2 ∓ `PIN_LEN`, herdava o resto: o `NE555_DIP8` saía com os pinos em `x = -8.5725` (−6,75 × 1,27). No editor de esquemático **o fio não engata num pino fora da grade** — o usuário desenha uma ligação que parece feita e não está, e isso só aparece no netlist. Agora as dimensões do corpo são arredondadas para a grade (`_largura_na_grade`), e **os 41 símbolos têm todos os pinos na grade de 50 mil**. Nota: a convenção KLC pede 100 mil, o que exigiria reposicionar as fileiras de pinos — mudança visual maior, não feita aqui.
- **O símbolo do `quad_smd` ignorava `pinos.numeracao`.** Um QFN/QFP com o lado direito começando em 17 (numeração de datasheet) gerava footprint com pads `1-4,17-20` mas símbolo numerado `1..8` — e o guard interno recompunha `1..total`, não via a diferença, e gravava o símbolo torto com "ok". Agora a numeração vem de uma **fonte única** (`numeros_quad_smd` em `gerador_footprint_v2`), usada pelo footprint e pelo símbolo, então os dois não podem divergir. `_lados_quad_smd` unifica também a distribuição por lado (o símbolo caía num fallback de 2 lados enquanto o footprint fazia 4).
- **Salvaguardas de silk que eram promessa vazia.** O recorte de silk apagava o marcador do pino 1 em 5 presets pequenos (SOT23_3/5, SSOP20, MP2359DJ, NINA) sem que nada notasse — o atributo nunca era marcado em `draw_pin1_marker`. Agora, quando o marcador cai sobre cobre, ele é **reposicionado para fora do pad**, junto ao pino 1 (como a lib oficial do KiCad); só quando não há espaço livre é que vira aviso. Também passaram a avisar de verdade: silk aninhado (antes pulado calado) e círculo/arco de silk sobre pad (o docstring prometia um aviso inexistente). E folga de pad de exatamente 0,2 mm deixou de gerar o aviso contraditório "0.200mm (< 0.20mm)" (ruído de ponto flutuante).
- **O símbolo não casava com o footprint gerado ao lado dele — 9 dos 41 presets.** O KiCad casa pino↔pad pelo **número**; símbolo e footprint saem do mesmo YAML por caminhos de código independentes, e **nada nunca os comparava**. A falha só apareceria no *netlist*, dentro do KiCad, longe do gerador — mais um caso do padrão desta base: "aceita, produz, e nunca diz que está errado". A causa era tripla e as três se escondiam uma na outra: (1) `gerar_symbol` terminava em `except Exception: print(...)` **sem relançar**, então nenhuma falha do símbolo chegava ao CLI; (2) o símbolo tinha uma **numeração própria**, paralela à do footprint (`total = dados["pinos"]["total"]`), que nem existe em peças `custom`/`grupos_pads`; (3) `_sym_mosfet_n/p` passavam o **nome** do pino (`"G"`) ao campo **número** — o SOT23_3 saía `(name "G") (number "B")` contra os pads `1/2/3`. Bônus achado no conserto: o papel dos pinos era fixo em 1=G,2=D,3=S — no IRFZ44N (1:G, 2:S, 3:D) isso **trocava dreno e source** mesmo com o número certo; agora o papel sai de `pin_names`. Depois do conserto, 0 dos 41 divergem; uma conferência roda **antes** de escrever e recusa gerar símbolo que não casa.
- **Peças derivadas de datasheet não tinham símbolo, e o CLI dizia "ok".** Consequência direta do `except` engolido acima: gerar o NINA-B406 (`custom` + `grupos_pads`, 71 pads) imprimia `[Symbol] ERRO ... KeyError: 'pinos'`, respondia `"ok": true, "erros": []` e **não gravava** o `.kicad_sym`. Agora o símbolo do NINA sai com **71 pinos** tirados dos próprios `grupos_pads` — a mesma fonte de verdade do footprint — e o CLI reflete a verdade sobre o disco.
- **Silkscreen desenhado por cima dos pads — 15 dos 41 presets.** O gerador desenhava o contorno de corpo inteiro (retângulo, chanfro do pino 1) **sem recortá-lo nos pads**: em DIP/QFN/SOT a linha de silk cruzava a largura inteira do cobre. O KiCad acusa "silk over pad" no DRC da placa e é defeito real de fabricação (tinta sobre área de solda). O recorte agora acontece no `save_footprint` — ponto único de saída dos 8 padrões — via `recortar_silk_sobre_pads`, que subtrai de cada segmento de F.SilkS a área dos pads expostos com folga de 0,2 mm (padrão da biblioteca oficial do KiCad), preservando o contorno e o marcador do pino 1. O F.Fab (documentação) fica intacto de propósito. Resultado: 15 → 0, com os pads inalterados (NINA segue 71/71 idêntico ao oficial).
- **O DRC julgava o YAML, não o footprint gerado.** A Regra 4 (`pad_silk_clearance`) reconstruía de cabeça uma geometria que o gerador não necessariamente desenha — lia `margens.silkscreen` como recuo do corpo quando é **espessura de linha**, e assumia que todo padrão fecha o retângulo de silk (o `dual_smd` não desenha as verticais que ela checava). Errava nos dois sentidos: **4 falsos positivos** e **8 falsos negativos** entre os 41 presets. Corrigida a regra, e o veredito de silk-sobre-pad passou a ser medido no arquivo real por `verificar_drc_arquivo` (ver Adicionado).
- **Texto ilegível no preview de peças pequenas.** As cotas do preview têm texto de tamanho fixo (pontos) e offsets em mm; num 0402 o `autoscale` ampliava a peça até encher a folha e as cotas "corpo" e "pitch" se sobrepunham. Agora há um piso de viewport (peça pequena aparece pequena e centralizada, como num CAD), margem proporcional, aspecto igual (não distorce um pad 1×0,5) e as cotas de topo são empilhadas com passo proporcional — legível tanto num 0402 quanto num DIP.
- **Modelo 3D órfão quando `kicad.modelo_3d` era omitido.** O `cli.py` sempre gera `<nome>.step`, mas o motor universal (`gerador_footprint_v2.py`) só escrevia a referência `(model ...)` se o campo existisse no YAML — e o campo é opcional. Resultado: o `.step` ficava no disco sem ninguém apontar para ele e o KiCad não mostrava 3D nenhum. **Falha silenciosa**: sem erro, sem aviso. Afetava os **7 padrões** (`axial_pth`, `radial_pth`, `dual_pth`, `dual_smd`, `quad_smd`, `custom`, `bga`). Agora, omitir o campo faz referenciar `<nome>.step` automaticamente; `modelo_3d: ""` segue sendo a forma explícita de não referenciar 3D.
- **`kicad.modelo_3d_path` era ignorado no motor universal.** O v2 chamava `add_3d_model(footprint, modelo_3d)` sem repassar `dados`, então o prefixo configurado no YAML nunca era lido.

### Adicionado
- **Conferência símbolo×footprint no `conferir`** (`--simbolo <arquivo.kicad_sym>`, ou o `.kicad_sym` irmão automaticamente). Distingue as duas direções porque não são o mesmo erro: **pino sem pad** é ERRO (o netlist dá net a um pino e não há cobre para levá-lo — a ligação some calada, o pior modo de falha desta base) e **pad sem pino** é aviso (o cobre existe e nenhum net o alcança — a placa ainda fabrica). O pad térmico `EP` dos QFN e a aba do SOT223 caem naturalmente em "pad sem pino" (aviso) por direção, sem uma lista de nomes que engoliria calado um pad esquecido.
- **`verificar_drc_arquivo(<kicad_mod>)`** — DRC sobre a **geometria real** do arquivo gerado, não sobre a intenção do YAML. É quem dá o veredito de silk-sobre-pad. Ligado no `cli.py validar` como **opt-in** (`--footprint`): reprovar o repositório inteiro no dia em que se liga um verificador exige decisão consciente, não um squelch.
- **`core/verificador_modelo_3d.py`** — confere que o `.step` referenciado existe de fato. Trata as variáveis do KiCad em três estados: `${KIPRJMOD}` resolve para a pasta do footprint; `${VAR}` definida no ambiente é checada; `${VAR}` **não** definida vira "não verificável" (INFO, não reprova) — gritar "arquivo não existe" sobre um caminho que não se conhece seria o falso positivo clássico, e no CI a variável tipicamente não existe.
- **`python cli.py conferir <kicad_mod> [--gabarito <oficial>]`** — a verificação virou comando de primeira classe, em vez de script copiado por missão. Compara **geometria, não texto**: aplica a rotação do pad antes de comparar, porque um pad 1,15×0,70 girado 90° tem o *mesmo* `sizeX/sizeY` de um não girado e ocupa cobre **transposto** — foi por ignorar isso que o script da missão NINA deu *"71/71 idênticos"* para um footprint com os pads laterais **em curto**. Acusa sobreposição (pads de mesmo número são o mesmo net e são ignorados) e, quando **todos** os pads divergem pelo **mesmo** deslocamento, reporta como **offset de origem** — não como N erros: as posições relativas batem e só falta reancorar. Não depende do `pcbnew`: lê o `.kicad_mod` pelo `sexpr_parser`, então roda no venv do próprio gerador.
- **Skill `footprint_de_datasheet`** (`.agents/skills/`) — o procedimento para gerar footprint a partir de um PDF, destilado dos erros reais desta base: como ler o datasheet sem torrar contexto (vetorial vs raster), nunca inventar cota, a armadilha da **orientação do pad** (comprimento ⊥ à borda — o bug que entregou pads em curto), como fechar o **datum nos dois eixos** (o erro que me fez declarar o STX3 bloqueado quando o dado estava lá), escrever em `grupos_pads` em vez de N coordenadas, e terminar **sempre** no `conferir`. `AGENTS.md` ganhou as regras 9 e 10 apontando para ela.
- **`grupos_pads` — o YAML ganhou a palavra que faltava.** Um módulo LGA/castelado é quase todo feito de **corridas**: n pads a partir de um ponto, somando um passo — que é exatamente como o datasheet cota (*"10 pads, pitch H, a partir do pino 1"*). Antes, o `custom` exigia as n coordenadas **absolutas calculadas à mão**: o NINA-B406 virava 71 números soltos, e o YAML deixava de ser fonte (era emitido por um script fora do repositório), ninguém o revisava contra o datasheet, e foi exatamente ali que nasceu o bug de rotação que entregou pads em curto. Agora se declara a **regra**, não o resultado. `passos: [...]` + `eixo` cobrem pitch **irregular** (a fileira inferior do STX3, com folga extra em volta do RFOUT — sem isso a peça não seria expressável). `grupos_pads` e `pads` **somam**: as corridas regulares num, o resto irregular no outro — juntos cobrem qualquer peça sem executar código.
  - **NINA-B406: 71 pads → 14 blocos.** Provado, não opinado: o YAML em blocos gera **71/71 pads idênticos** ao footprint oficial da u-blox, 0 sobreposições — o mesmo resultado dos 71 explícitos.
  - **Globalstar STX3: 32 pads → 4 blocos**, 32/32 idênticos à versão explícita.
- **`origem: pino_1`** — as cotas de datasheet são relativas ao **pino 1** (no NINA, as 27 da Table 22 são todas). Obrigar o autor a converter para o centro do corpo é conta mecânica e é onde o erro entra; agora é do gerador. `da_borda: {esquerda: D, base: E}` diz de quais bordas o pino 1 dista — exige uma horizontal e uma vertical, porque o datasheet cota distância e o lado vem do desenho (adivinhar seria inventar).
- **Detecção de colisão estendida aos padrões paramétricos** (`quad_smd`, `dual_smd`) — eu havia ligado a checagem só no `custom` e no `single_row_pth`, raciocinando que *"nos paramétricos as posições são calculadas, colidir é difícil"*. **Errado.** A regra IPC de clearance compara `pitch` × `tamanho_pad` e olha só vizinhos adjacentes: não enxerga `overrides` nem `pinos_absolutos`. Um override maior que o pitch gerava com `ok: true` e saía **em curto** (`quad_smd` com `overrides: {"2": {altura: 3.0}}` e pitch 1,0 → 2 pares sobrepostos, aprovado). Agora a checagem é sobre a geometria real de **todos** os pares. Ligá-la revelou **4 fixtures da própria suíte de testes** com `largura`/`altura` trocados — SOIC-8 e QFP-32/128 fisicamente impossíveis, gerados e validados há tempo porque nada checava; e dois corpos pequenos demais, pondo os pads de **canto** em curto (coluna × fileira). A mesma confusão semântica do bug de rotação do NINA, dentro dos testes.
- `cli.py conferir`: arquivo inexistente agora dá erro claro em vez de traceback.
- **Detecção de colisão entre pads** (`footprint_helpers.check_pad_collisions`) — `validate_pad_clearance` existia desde sempre e **nenhum código a chamava**: dois pads de 1×1 mm com centros a 0,1 mm geravam `ok: true`. Agora sobreposição é **erro** (o cobre se toca, os pinos sairiam em curto) e folga curta é aviso; pads com o mesmo número são o mesmo net e são ignorados. Ligada no `custom` e no `single_row_pth` — o `custom` é o único padrão onde as posições são escritas à mão, ou seja, o único onde dá para colidir. Achado ao gerar o NINA-B406 (ver `missoes/nina-b406/ACHADOS.md`).
- **Padrão `single_row_pth`** — pin header 1×N (fileira única PTH), com o corpo derivado dos pads quando ausente.

### Corrigido
- **`conector_pth` gerava footprints inutilizáveis** — o shim mapeava para `dual_pth`, que é de **duas** fileiras: `total // 2` descartava o pino ímpar e `afastamento_colunas` (ausente nos YAMLs de header) colapsava as colunas em x=0. Resultado: `Conn_01x03` declarava `total: 3` e saía com **2 pads empilhados em (0,0)**; `Conn_01x06_PinHeader` saía com os pares 1&6, 2&5, 3&4 coincidentes. Ambos validavam `ok: true`. `conector_pth` agora mapeia para `single_row_pth`.
- **A validação de JSON Schema nunca rodou no CI** — `validador_schema` faz `except ImportError: return (True, [])`, ou seja, sem a lib `jsonschema` ele devolve **"válido" para qualquer coisa** (um YAML sem `nome` passa). E o CI instalava só `PyQt5 PyYAML matplotlib numpy`. Resultado: a regra nº4 do `AGENTS.md` ("JSON Schema é a verdade") não era verificada — todo YAML passava. `jsonschema` agora é instalada no CI e declarada em `requirements.txt`/`pyproject.toml`, e um teste falha se a validação estiver degradada. Descoberto porque o teste do typo de pad passava local e falhava no CI.
- **Typo em campo opcional de pad passava calado** — `custom_pad` não declarava `additionalProperties`, então `formto: circulo` / `montgem: pth` eram ignorados e o pad saía retangular SMD sem furo, com `ok: true`. Agora é erro. (Typo em campo *obrigatório* já era pego, via `required`.)

### Removido
- **Motor v1 (`core/gerador_footprint.py`, 1229 linhas)** — estava marcado como deprecated desde a v2.0.0, mas a migração nunca foi concluída: o `api_server.py` ainda o usava para YAMLs com `tipo:`, enquanto a CLI forçava o v2. Isso fazia **o mesmo YAML gerar saídas diferentes** conforme a interface — e a API não recebia nenhuma correção feita no v2 (ex.: um YAML sem `kicad.modelo_3d`, campo opcional pelo schema, quebrava a API com `KeyError` e funcionava na CLI). A API agora usa o mesmo dispatch da CLI (sempre v2 + shim `tipo→padrao`), o comportamento ficou idêntico entre as interfaces e o v1 pôde ser removido. `core/geometria_pads.py` foi **mantido**: apesar de ser dependência do v1, também é usado por `gerador_3d.py` e `gui/painel_pin_editor.py`.

### Alterado
- **`pinos.overrides` agora é honrado por todos os padrões que fazem sentido** — antes só o `quad_smd` o lia; `axial_pth`, `radial_pth`, `dual_pth` e `dual_smd` **ignoravam em silêncio** (o YAML era aceito, o footprint gerava, e o pad saía no tamanho padrão). Nos padrões PTH, `largura`/`altura` diferentes produzem um pad **oval** (o KiCad não aceita círculo com lados diferentes) e o anel passa a ser validado contra o menor lado. O `bga` endereça a bola pelo **nome** (`{"A1": {...}}`) — por isso o mapa de overrides passou a ser chaveado por string, que é como o KiCad trata número de pad. O `custom` não usa overrides: cada pad já declara `largura`/`altura` na lista `pads:`.
- **Renomeado o produto de "Data Frontier" para "EDA Footprint Generator"** em toda a interface, documentação e nome do plugin. Identificadores técnicos (`com.datafrontier.footprint-generator`, `DataFrontier.kicad_sym`, chaves de config) e autor/copyright foram mantidos para não quebrar compatibilidade.
- Ícone do app/plugin passa a exibir "EDA" no lugar de "CAD"
- Plugin PCM re-lançado como v3.0.1 com o novo nome

### Adicionado
- Flag `--dry-run` nos comandos `gerar` e `batch` da CLI: valida (IPC) e lista os arquivos que seriam gerados, sem escrever nada (`gerar` por @tapheret2 no #7; estendido ao `batch`)
- README em inglês (`README.md`) como página de produto; versão PT-BR movida para `README.pt-BR.md`
- Templates de issue (bug/feature) e de Pull Request em `.github/`
- Regra de **Disciplina de Documentação** em `.agents/AGENTS.md`, `SKILL.md` e `CONTRIBUTING.md`
- Empacotamento para o KiCad PCM: `metadata.json` no schema oficial, `scripts/build_pcm_package.py`, guia `kicad_plugin/README_PCM.md` e workflow `release-pcm.yml`
- Ícone 64×64 do plugin para o PCM (`kicad_plugin/icon.png`) e gerador `scripts/gen_pcm_icon.py`
- Primeiro release do plugin no PCM (v3.0.0) publicado como asset do GitHub Release
- Repositório PCM próprio (self-hosted) servido via GitHub Pages: `docs/pcm/packages.json` + `docs/pcm/repository.json`, gerados por `scripts/build_pcm_repo.py`
- Landing page do projeto (`docs/index.html`) servida via GitHub Pages, com botão de instalação via PCM e quick start
- Seção de "good first issues" no `CONTRIBUTING.md`

### Corrigido
- **Os 5 campos "inertes" agora fazem o que o schema promete** — estavam no schema e no `_template.yaml` (que ensinava a usá-los), eram aceitos pela validação, e nenhum código os lia. Escrevê-los não produzia efeito nem aviso:
  - `solder_paste_margin` (e `solder_mask_margin`) → viram propriedade do footprint no `.kicad_mod`. No KiCad são propriedades do *footprint*, não do pad — que é exatamente onde o schema as declara (topo). Aplicadas em `save_footprint`, ponto de saída comum aos 7 padrões.
  - `pinos.numeracao.inicio_esquerdo` / `inicio_direito` → definem onde a numeração de cada lado começa no `quad_smd`. **Colisão entre lados agora é erro**: um início que caia sobre outro lado gerava pads duplicados, e pad duplicado é netlist errada.
  - `eletrico.polaridade` → aparece no relatório técnico (o bloco `eletrico` já era consumido lá). O relatório iterava uma lista fixa que a omitia; e `if valor:` descartaria `polaridade: false`, então booleano é tratado à parte ("Polarizado" / "Nao polarizado").
  - `pcb.material` / `shield_metalico.material` → aparecem no relatório técnico. São metadados do módulo físico; não afetam o footprint.
- `eletrico.corrente_maxima` declarado no schema — o relatório já o lia, mas ele não existia no schema (descasamento no sentido inverso).
- `simbolo: custom` adicionado ao enum do schema — `gerador_symbol` já o suportava (mapeia para CI genérico), mas o schema o rejeitava: o preset `PESD2CAN_SOT23` falhava na validação.
- `Stx3.yaml`: bloco `numeracao` removido — descrevia um módulo de 2 lados (`inicio_direito: 17`), mas o módulo é de 4 lados e a base já ocupa 17-32, então duplicaria 16 pads. Como o campo era ignorado, a numeração efetiva sempre foi a sequencial 1..64 — a saída não muda. **Conferir no datasheet** se a numeração real é mesmo sequencial.
- **`thermal_pad.pasta_ratio` deixou de ser ignorado** — o schema declara `pasta_ratio` como *sinônimo* de `paste_ratio` e o `_template.yaml` ensina justamente essa grafia, mas o código só lia `paste_ratio`: quem escrevia `pasta_ratio` tinha o valor descartado em silêncio e a abertura de pasta saía no default (0.5). Afetava `_template.yaml`, `_preset_QFN16_4x4` e `MT6835GT_QFN16` — invisível só porque os três usam 0.5, que por acaso é o default. A leitura das duas grafias agora vive num lugar só (`footprint_helpers.read_paste_ratio`).
- **`pinos.total` contraditório agora é erro, não geração silenciosa** — no `quad_smd`, um `total` que não batesse com `lados`/`por_lado` era descartado sem aviso: o `Stx3.yaml` declarava `total: 32` com `por_lado: 16` e gerava **64 pads**. O mesmo valia para `total` não divisível por 4 (`30 → 30//4 = 7` por lado → 28 pads, sumiam 2). Melhor não gerar do que gerar errado.
- **`Stx3.yaml` reescrito como `padrao: custom`, derivado do datasheet** (STX3 User Manual 8545-0198-01 R-4) — 32 pads, 0 colisões. O arquivo anterior estava errado em quase tudo: `tipo: castellated` (→ `quad_smd`, que aplica **um** pitch e não expressa a fileira inferior não-uniforme `.100 .100 .100 .120 .120 .100`, cuja folga extra cerca o pino 14 = RFOUT); `por_lado: 16` (o módulo é 4 lados mas **9/7/9/7** = 32, Fig.8 + Table 3); e a geometria era **inventada** — pitch 1,778 e pad 2,03×1,27 contra os reais 2,54 e 2,032×1,930 (`.100"`, `.080×.076"`). O próprio comentário entregava: *"1.778 — único pitch padrão que cabe 16 pinos em 28.70mm"*, ou seja, escolhido para caber numa suposição. Os pads são **orientados** (lado longo ⊥ à borda), como no NINA. Derivação em `missoes/stx3/derivar_stx3.py`, com asserções de fechamento. Verificado contra o footprint derivado de forma independente em outro projeto: **tamanhos idênticos e geometria relativa igual** (desvio único e constante = translação rígida). Também corrigido, no caminho, um deslocamento de **+0,457 mm em Y** que aquela derivação tinha: ela centrava as *colunas* em y=0, mas as cotas `.117` ≠ `.153` tornam a coluna assimétrica de propósito — quem centra a coluna desloca o campo inteiro contra o contorno do módulo.
  - **O datum foi resolvido por fechamento**, não estimado: `.075 + 6×.100 + .075 = .750` (topo) e `.055 + (.100+.100+.100+.120+.120+.100) + .055 = .750` (base) concordam; e `.117 + 8×.100 + .153 = 1.070`. Contra o módulo (`.810 × 1.130`, Fig.1, em texto): sobra `.060` nos **dois** eixos → **`.030`/lado**. O mesmo recuo em ambos os eixos é o que prova a leitura: as linhas de referência da Fig.7 são as *centerlines* dos pads. (Eu havia declarado isso bloqueado — errado: calculei `1.070 ≠ 1.130` e não percebi que o horizontal errava pelos mesmos `.060`.)
- `Stx3.yaml`: revertido meu erro anterior de `total: 32` → `64`. O `total` original estava certo; o campo errado era o `por_lado`. E o `numeracao: {inicio_esquerdo: 1, inicio_direito: 17}` que removi **estava correto** — com 9 pinos à esquerda, o direito começa mesmo em 17 (agora implícito na ordem dos pads).
- **Repositório PCM voltou a funcionar após o rename do repo** — o GitHub redireciona URLs de repositório renomeado, mas **o GitHub Pages não**: a URL antiga passou a dar 404. Como o `repository.json` apontava para o Pages antigo, o KiCad não conseguia baixar o `packages.json` e o repositório PCM ficava inutilizável. Índice regerado com as URLs novas e todas as 31 referências ao slug antigo atualizadas (README, landing page, metadata, docs, scripts). Nova URL: `https://pedrowall-e.github.io/EDA-Footprint-Generator/pcm/repository.json`
- **`pinos.overrides` em lista voltou a funcionar** — o motor v2 assumia que `overrides` era sempre um dict e estourava `AttributeError: 'list' object has no attribute 'get'` na forma em lista (`- numeros: [...]`), que o `schemas/component.schema.json` declara como válida (`oneOf`). Regressão da reescrita do v1 → v2: o v1 suportava a forma lista via `geometria_pads._construir_override_map`. Afetava `quad_smd`/castellated — os presets `RM200-v2` e `ModuloLTE_4Lados` não geravam. A normalização das duas formas agora vive num lugar só (`footprint_helpers.build_override_map`). Batch dos 40 presets: 40/40.
- `add_3d_model`: não estoura mais quando o YAML tem `kicad:` presente porém vazio (vira `None`, não `{}`)
- Documentadas as duas formas de `pinos.overrides` no `MANUAL_YAML_REFERENCIA.yaml` (a forma lista não estava documentada)
- CI: testes falhavam no Windows (`UnicodeEncodeError` ao imprimir emojis) — `tests/teste_v2.py` agora força UTF-8 no stdout/stderr; workflow define `PYTHONUTF8`/`PYTHONIOENCODING`
- CI: testes falhavam no Python 3.9 (sintaxe `X | None` exige 3.10+) — matriz do CI passa a 3.10/3.11/3.12; `requires-python` ajustado para `>=3.10` (alinhado ao README)
- `LICENSE` agora contém o texto completo e verbatim da GPL-3.0 (antes só o cabeçalho), permitindo a detecção correta da licença pelo GitHub e cumprindo a exigência da GPL de distribuir o texto integral
- Nota explicativa "por que GPL" movida do `LICENSE` para o `NOTICE`
- URL de Homepage corrigida no `pyproject.toml` (apontava para repositório inexistente); adicionadas URLs de Repository e Issues

## [3.0.0] - 2026-06-16

### Adicionado
- Módulo de Relatório Técnico com réguas CAD (PDF + HTML)
- Verificador DRC com 8 regras configuráveis
- Export Eagle (.lbr) e Altium (CSV)
- Plugin KiCad nativo (pcbnew ActionPlugin)
- Wizard de criação de componente (4 páginas)
- Preferências persistêntes (QSettings)
- Splash screen animado
- Help integrado (F1) com referência YAML completa
- Suporte a BGA (7° padrão no motor universal)
- Geração de BOM (CSV)
- Launcher cross-platform (Linux/Mac)
- Build script PyInstaller

### Corrigido
- Motor v1 agora gera formato KiCad v6+ corretamente
- Batch export roteia para motor v2 quando `padrao:` presente
- Auto-save silencioso antes de gerar footprint

## [2.0.0] - 2026-06-15

### Adicionado
- Motor Universal v2 com 6 padrões (axial, radial, dual PTH/SMD, quad, custom)
- Validador IPC-7351B com 10 regras
- Viewer 2D com toggle de camadas e ferramentas de medição
- Export PNG/SVG/PDF do footprint
- Status bar (Ln/Col, arquivo, validação)
- Error markers no editor YAML
- Drag & Drop de arquivos .yaml
- Diálogo "Sobre"
- 91 testes automatizados

### Melhorado
- 24 presets de componentes padrão (SMD, PTH, QFP, BGA)
- Modelos 3D detalhados (CadQuery) para todos os tipos
- Interface dark theme Catppuccin Mocha

## [1.0.0] - 2026-06-01

### Adicionado
- Motor de geração v1 com 10 tipos de componente
- Editor YAML com syntax highlighting
- Viewer 3D integrado (CQ-Editor)
- Geração de símbolos esquemáticos
- Exportação de biblioteca KiCad
- 10 componentes de exemplo
