# Changelog

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Corrigido
- **Modelo 3D órfão quando `kicad.modelo_3d` era omitido.** O `cli.py` sempre gera `<nome>.step`, mas o motor universal (`gerador_footprint_v2.py`) só escrevia a referência `(model ...)` se o campo existisse no YAML — e o campo é opcional. Resultado: o `.step` ficava no disco sem ninguém apontar para ele e o KiCad não mostrava 3D nenhum. **Falha silenciosa**: sem erro, sem aviso. Afetava os **7 padrões** (`axial_pth`, `radial_pth`, `dual_pth`, `dual_smd`, `quad_smd`, `custom`, `bga`). Agora, omitir o campo faz referenciar `<nome>.step` automaticamente; `modelo_3d: ""` segue sendo a forma explícita de não referenciar 3D.
- **`kicad.modelo_3d_path` era ignorado no motor universal.** O v2 chamava `add_3d_model(footprint, modelo_3d)` sem repassar `dados`, então o prefixo configurado no YAML nunca era lido.

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
- **`thermal_pad.pasta_ratio` deixou de ser ignorado** — o schema declara `pasta_ratio` como *sinônimo* de `paste_ratio` e o `_template.yaml` ensina justamente essa grafia, mas o código só lia `paste_ratio`: quem escrevia `pasta_ratio` tinha o valor descartado em silêncio e a abertura de pasta saía no default (0.5). Afetava `_template.yaml`, `_preset_QFN16_4x4` e `MT6835GT_QFN16` — invisível só porque os três usam 0.5, que por acaso é o default. A leitura das duas grafias agora vive num lugar só (`footprint_helpers.read_paste_ratio`).
- **`pinos.total` contraditório agora é erro, não geração silenciosa** — no `quad_smd`, um `total` que não batesse com `lados`/`por_lado` era descartado sem aviso: o `Stx3.yaml` declarava `total: 32` com `por_lado: 16` e gerava **64 pads**. O mesmo valia para `total` não divisível por 4 (`30 → 30//4 = 7` por lado → 28 pads, sumiam 2). Melhor não gerar do que gerar errado.
- `Stx3.yaml`: `total` corrigido de 32 para 64 (o módulo é de 4 lados, 16 por lado) — o valor errado só não aparecia porque era ignorado.
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
