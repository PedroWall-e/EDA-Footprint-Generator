"""
Validador de Schema JSON para dados YAML de componentes.

Valida dicionários de componentes contra o JSON Schema definido em
schemas/component.schema.json usando a biblioteca jsonschema.

Inclui fallback gracioso caso jsonschema não esteja instalado.
"""

import json
import os
import logging

log = logging.getLogger(__name__)

# Caminho do schema relativo a este arquivo
_SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'schemas')
_SCHEMA_PATH = os.path.join(_SCHEMA_DIR, 'component.schema.json')


def _carregar_schema() -> dict:
    """Carrega o JSON Schema do disco.

    Returns:
        dict com o schema JSON parseado.

    Raises:
        FileNotFoundError: se o arquivo do schema não existir.
    """
    schema_path = os.path.normpath(_SCHEMA_PATH)
    if not os.path.isfile(schema_path):
        raise FileNotFoundError(
            f'Schema não encontrado: {schema_path}. '
            f'Verifique se schemas/component.schema.json existe.'
        )
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validar_schema(dados: dict) -> tuple:
    """Valida um dicionário de componente contra o JSON Schema.

    Usa a biblioteca jsonschema para validação completa. Se jsonschema não
    estiver instalado, retorna (True, []) com um aviso no log.

    Args:
        dados: dicionário com os dados do componente (carregado do YAML).

    Returns:
        Tupla (ok, erros):
            ok (bool): True se o componente é válido, False se há erros.
            erros (list[str]): Lista de mensagens de erro legíveis.
                               Vazia se ok=True.

    Exemplos:
        >>> ok, erros = validar_schema({"nome": "R1", "tipo": "resistor_pth"})
        >>> print(ok)
        True

        >>> ok, erros = validar_schema({"tipo": "ci_dip"})
        >>> print(ok)
        False
        >>> print(erros[0])
        "'nome' é obrigatório"
    """
    try:
        import jsonschema
        from jsonschema import Draft202012Validator, ValidationError
    except ImportError:
        log.warning(
            'Biblioteca jsonschema não instalada. '
            'Instale com: pip install jsonschema. '
            'Validação de schema ignorada.'
        )
        return (True, [])

    # Carregar schema
    try:
        schema = _carregar_schema()
    except FileNotFoundError as e:
        log.error(str(e))
        return (False, [str(e)])
    except json.JSONDecodeError as e:
        msg = f'Erro ao parsear schema JSON: {e}'
        log.error(msg)
        return (False, [msg])

    # Validar dados
    if not isinstance(dados, dict):
        return (False, ['Dados de entrada não são um dicionário válido.'])

    validator = Draft202012Validator(schema)
    erros = []

    for error in sorted(validator.iter_errors(dados), key=lambda e: list(e.path)):
        # Construir caminho legível
        caminho = '.'.join(str(p) for p in error.absolute_path)
        if caminho:
            msg = f'{caminho}: {error.message}'
        else:
            msg = error.message

        erros.append(msg)

    ok = len(erros) == 0

    # Log
    nome = dados.get('nome', '<sem nome>')
    if ok:
        log.info(f'Schema validação OK para "{nome}"')
    else:
        log.error(
            f'Schema validação FALHOU para "{nome}": '
            f'{len(erros)} erro(s)'
        )
        for e in erros:
            log.error(f'  → {e}')

    return (ok, erros)


def validar_arquivo_yaml(caminho: str) -> tuple:
    """Conveniência: carrega um YAML e valida contra o schema.

    Args:
        caminho: caminho do arquivo .yaml a validar.

    Returns:
        Tupla (ok, erros) — mesma assinatura de validar_schema().
    """
    try:
        import yaml
    except ImportError:
        msg = (
            'Biblioteca PyYAML não instalada. '
            'Instale com: pip install pyyaml'
        )
        log.error(msg)
        return (False, [msg])

    if not os.path.isfile(caminho):
        return (False, [f'Arquivo não encontrado: {caminho}'])

    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return (False, [f'Erro ao parsear YAML: {e}'])

    if dados is None:
        return (False, ['Arquivo YAML vazio.'])

    return validar_schema(dados)


# ---------------------------------------------------------------------------
# Execução direta — valida todos os YAMLs em modulos_config/
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    import glob

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    # Encontrar diretório modulos_config
    base_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'modulos_config'
    )
    base_dir = os.path.normpath(base_dir)

    if not os.path.isdir(base_dir):
        print(f'Diretório não encontrado: {base_dir}')
        sys.exit(1)

    yamls = sorted(glob.glob(os.path.join(base_dir, '*.yaml')))
    if not yamls:
        print(f'Nenhum arquivo .yaml encontrado em {base_dir}')
        sys.exit(1)

    total = 0
    falhas = 0
    resultados = []

    print(f'\n{"="*70}')
    print(f'Validando {len(yamls)} arquivos YAML contra o schema...')
    print(f'{"="*70}\n')

    for yaml_path in yamls:
        nome_arq = os.path.basename(yaml_path)
        ok, erros = validar_arquivo_yaml(yaml_path)
        total += 1

        if ok:
            print(f'  [OK] {nome_arq}')
        else:
            falhas += 1
            print(f'  [ERRO] {nome_arq}')
            for e in erros:
                print(f'      > {e}')
            resultados.append((nome_arq, erros))

    print(f'\n{"="*70}')
    print(f'Resultado: {total - falhas}/{total} válidos, {falhas} com erros')
    print(f'{"="*70}\n')

    if falhas > 0:
        sys.exit(1)
