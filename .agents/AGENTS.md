# EDA Footprint Generator — Regras para Agentes

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
8. **Idioma**: Interface e documentação de usuário em Português (BR). `README.md` (inglês) e `README.pt-BR.md` devem ser mantidos em sincronia; templates de issue/PR em inglês.
9. **Footprint a partir de datasheet** — Não improvise: siga
   `.agents/skills/footprint_de_datasheet/SKILL.md`. Ela traz as armadilhas que
   já custaram caro (orientação do pad, datum, cota inventada) e o passo de
   verificação obrigatório.
10. **Verificar, não confiar no "ok"** — `python cli.py conferir <kicad_mod>`
    depois de gerar. "Gerou sem erro" não quer dizer "está certo": já houve
    footprint com pads em curto aprovado por três verificadores.
11. **📌 DISCIPLINA DE DOCUMENTAÇÃO (obrigatória)** — A cada mudança, pequena ou grande, atualize a documentação afetada **na mesma alteração**. Ver tabela abaixo. Documentação desatualizada é tratada como bug.

## Disciplina de Documentação

Antes de considerar uma tarefa concluída, verifique se algum destes artefatos precisa acompanhar a mudança e **atualize-o junto**:

| Se você mudou… | Atualize também |
|---|---|
| Qualquer comportamento visível (feature, fix, remoção) | `CHANGELOG.md` (sempre) |
| Campos/estrutura do YAML | `schemas/component.schema.json`, `docs/MANUAL_YAML_REFERENCIA.yaml`, `.agents/skills/component_generator/SKILL.md`, `README.md` + `README.pt-BR.md` |
| Padrões (`_PADROES`) ou tipos 3D (`TEMPLATES_3D`) | `SKILL.md` (tabelas de padrões/tipos), `README*` (tabela de features) |
| Presets em `modulos_config/_preset_*.yaml` | Tabela de presets na `SKILL.md` |
| Comandos da CLI / endpoints da API | `SKILL.md`, `README*`, docstring do próprio comando |
| Exportadores (Eagle/Altium/BOM) ou validadores (IPC/DRC) | `README*` (features + seção "trust"), `CHANGELOG.md` |
| Regras de contribuição / setup | `CONTRIBUTING.md`, `README*` (quick start) |
| Versão do plugin ou release | `kicad_plugin/metadata.json`, `core/version.py`, `CHANGELOG.md` |

**Regra de ouro:** `README.md` e `README.pt-BR.md` são espelhos — nunca atualize um sem o outro. Se não tiver certeza de qual doc atualizar, atualize o `CHANGELOG.md` no mínimo.

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
