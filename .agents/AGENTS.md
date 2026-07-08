# Plataforma CAM/CAD Data Frontier — Regras para Agentes

## Sobre o Projeto

Plataforma de geração automatizada de componentes eletrônicos para KiCad.
Gera 3 saídas por componente: `.kicad_mod` (footprint), `.kicad_sym` (símbolo), `.step` (3D).

## Regras

1. **Sempre validar antes de gerar** — Use `python cli.py --json validar` antes de gerar
2. **Usar presets como base** — Não invente campos; copie de `modulos_config/_preset_*.yaml`
3. **Testar com o teste_v2.py** — Após mudanças em core/, rode `python tests/teste_v2.py`
4. **JSON Schema é a verdade** — `schemas/component.schema.json` define a estrutura válida
5. **Sem auto-geração** — O usuário clica ▶ para gerar; nunca auto-gere
6. **UTF-8 sempre** — Use `-X utf8` ou `reconfigure(encoding='utf-8')` no Windows
7. **Saída em `saida/`** — Arquivos gerados ficam em `saida/`, preview em `saida/_preview/`
8. **Idioma**: Interface e documentação em Português (BR)

## Estrutura do Projeto

```
├── cli.py                          # CLI para automação
├── api_server.py                   # API REST (FastAPI)
├── core/
│   ├── gerador_footprint_v2.py     # Gera .kicad_mod
│   ├── gerador_symbol.py           # Gera .kicad_sym
│   ├── gerador_3d.py               # Gera .step (headless)
│   ├── gerador_universal.py        # Orquestrador CQ-Editor
│   ├── validador_ipc.py            # Validação IPC-7351B
│   └── validador_schema.py         # Validação JSON Schema
├── gui/                            # Interface PyQt5
├── modulos_config/                 # YAMLs de componentes
│   ├── _preset_*.yaml              # Presets base
│   └── _template.yaml              # Template mestre
├── schemas/
│   └── component.schema.json       # JSON Schema formal
├── docs/
│   └── MANUAL_YAML_REFERENCIA.yaml # Manual completo
└── tests/
    └── teste_v2.py                 # 107 testes
```
