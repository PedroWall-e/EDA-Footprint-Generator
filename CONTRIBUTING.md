# Contribuindo para a EDA Footprint Generator

Obrigado pelo interesse em contribuir! Este guia ajuda a manter a qualidade do projeto.

## Como Contribuir

### Reportar Bugs
1. Verifique se o bug já foi reportado nas [Issues](../../issues)
2. Use o template de bug report
3. Inclua: versão do Python, sistema operacional, passos para reproduzir

### Sugerir Melhorias
1. Abra uma Issue com o label `enhancement`
2. Descreva o caso de uso e o comportamento esperado

### Enviar Código
1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Faça suas alterações
4. Rode os testes: `python tests/teste_v2.py` (todos devem passar)
5. Commit: `git commit -m 'feat: descrição da feature'`
6. Push: `git push origin feature/minha-feature`
7. Abra um Pull Request

## Padrões de Código

### Python
- Python 3.10+ (o código usa sintaxe de união de tipos `X | None`, que exige 3.10+)
- Docstrings em todas as funções públicas
- Logging via `log = logging.getLogger(__name__)` (nunca `print()`)
- `yaml.safe_load()` (nunca `yaml.load()`)
- Tratamento de erros com `try/except` específico

### Nomes
- Variáveis e funções: `snake_case` em português
- Classes: `PascalCase`
- Constantes: `UPPER_SNAKE_CASE`
- Campos YAML: português (`espacamento`, `comprimento`, `diametro_pad`)

### Commits
Seguimos [Conventional Commits](https://www.conventionalcommits.org/pt-br/):
- `feat:` nova funcionalidade
- `fix:` correção de bug
- `docs:` documentação
- `test:` testes
- `refactor:` refatoração sem mudança funcional

## Estrutura do Projeto

```
core/           ← Lógica de negócio (geradores, validadores, exportadores)
gui/            ← Interface gráfica (PyQt5 + launcher)
tests/          ← Suite de testes
docs/           ← Manual YAML de referência
modulos_config/ ← Presets e componentes YAML
assets/         ← Ícone e recursos visuais
build/          ← Scripts de build (PyInstaller)
kicad_plugin/   ← Plugin KiCad nativo
scripts/        ← Scripts utilitários
```

## Disciplina de Documentação (obrigatória)

Toda mudança — pequena ou grande — deve atualizar a documentação afetada **no mesmo PR**. Documentação desatualizada é tratada como bug e trava o merge.

| Se você mudou… | Atualize também |
|---|---|
| Qualquer comportamento visível | `CHANGELOG.md` (sempre) |
| Campos/estrutura do YAML | `schemas/component.schema.json`, `docs/MANUAL_YAML_REFERENCIA.yaml`, `README.md` + `README.pt-BR.md` |
| Padrões de pad ou tipos 3D | `.agents/skills/component_generator/SKILL.md`, `README*` |
| Presets (`modulos_config/_preset_*.yaml`) | Tabela de presets na `SKILL.md` |
| Comandos da CLI / endpoints da API | `SKILL.md`, `README*` |
| Exportadores ou validadores | `README*`, `CHANGELOG.md` |
| Versão do plugin / release | `kicad_plugin/metadata.json`, `core/version.py`, `CHANGELOG.md` |

> `README.md` (inglês) e `README.pt-BR.md` são espelhos: nunca atualize um sem o outro.

## Bons primeiros PRs (good first issues)

Quer começar? Estes são pontos de entrada de baixo risco e alto valor:

1. **Adicionar um preset** para um package ainda não coberto (ex.: `_preset_QFN20`, `_preset_uMAX8`) copiando um `_preset_*.yaml` similar.
2. **Traduzir uma seção** do `docs/MANUAL_YAML_REFERENCIA.yaml` para inglês (`docs/YAML_REFERENCE.en.yaml`).
3. **Adicionar um teste** para um padrão pouco coberto em `tests/teste_v2.py`.
4. **Gravar o GIF de demonstração** (`assets/demo.gif`) e referenciá-lo no README.
5. **Melhorar uma mensagem de erro** de validação IPC para incluir o valor esperado vs. obtido.
6. **Adicionar um `--dry-run`** ao `cli.py gerar` que valida e mostra o que seria gerado sem escrever arquivos.

Veja a lista completa e etiquetada em [good first issues](https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier/labels/good%20first%20issue).

## Testes

Antes de enviar um PR, garanta que todos os testes passam:

```bash
python tests/teste_v2.py
# Esperado: 107/107 OK
```

Se adicionar funcionalidade nova, adicione testes no grupo apropriado ou crie um novo grupo.

## Licença

Ao contribuir, você concorda que suas contribuições serão licenciadas sob a [GPL v3](LICENSE).
