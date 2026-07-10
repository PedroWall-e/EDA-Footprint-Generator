# Changelog

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Adicionado
- README em inglês (`README.md`) como página de produto; versão PT-BR movida para `README.pt-BR.md`
- Templates de issue (bug/feature) e de Pull Request em `.github/`
- Regra de **Disciplina de Documentação** em `.agents/AGENTS.md`, `SKILL.md` e `CONTRIBUTING.md`
- Empacotamento para o KiCad PCM: `metadata.json` no schema oficial, `scripts/build_pcm_package.py`, guia `kicad_plugin/README_PCM.md` e workflow `release-pcm.yml`
- Seção de "good first issues" no `CONTRIBUTING.md`

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
