# Contribuindo para a Plataforma CAM-CAD Data Frontier

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
- Python 3.9+
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

## Testes

Antes de enviar um PR, garanta que todos os testes passam:

```bash
python tests/teste_v2.py
# Esperado: 107/107 OK
```

Se adicionar funcionalidade nova, adicione testes no grupo apropriado ou crie um novo grupo.

## Licença

Ao contribuir, você concorda que suas contribuições serão licenciadas sob a [GPL v3](LICENSE).
