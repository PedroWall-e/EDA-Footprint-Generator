# Changelog

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Corrigido
- **Modelo 3D órfão quando `kicad.modelo_3d` era omitido.** O `cli.py` sempre gera `<nome>.step`, mas o motor universal (`gerador_footprint_v2.py`) só escrevia a referência `(model ...)` se o campo existisse no YAML — e o campo é opcional. Resultado: o `.step` ficava no disco sem ninguém apontar para ele e o KiCad não mostrava 3D nenhum. **Falha silenciosa**: sem erro, sem aviso. Afetava os **7 padrões** (`axial_pth`, `radial_pth`, `dual_pth`, `dual_smd`, `quad_smd`, `custom`, `bga`). Agora, omitir o campo faz referenciar `<nome>.step` automaticamente; `modelo_3d: ""` segue sendo a forma explícita de não referenciar 3D.
- **`kicad.modelo_3d_path` era ignorado no motor universal.** O v2 chamava `add_3d_model(footprint, modelo_3d)` sem repassar `dados`, então o prefixo configurado no YAML nunca era lido.

### Alterado
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
