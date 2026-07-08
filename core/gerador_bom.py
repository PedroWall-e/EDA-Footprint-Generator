# =============================================================================
# gerador_bom.py
# Gerador de BOM (Bill of Materials) a partir dos YAMLs de componentes.
#
# Lê todos os arquivos .yaml de um diretório de módulos, extrai informações
# relevantes e gera um arquivo CSV com a lista de materiais.
#
# Autor: Gerador Automático de Footprints
# =============================================================================

"""Gerador de BOM (Bill of Materials) a partir dos YAMLs de componentes."""

import os
import csv
import yaml
import logging

log = logging.getLogger(__name__)


def _extrair_componente(yaml_path: str) -> dict | None:
    """Extrai dados de um componente a partir de um arquivo YAML.

    Retorna dict com campos do BOM ou None se o arquivo for inválido.
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            dados = yaml.safe_load(f)
    except Exception as e:
        log.warning("Erro ao ler %s: %s", yaml_path, e)
        return None

    if not isinstance(dados, dict):
        return None

    nome = dados.get('nome', os.path.splitext(os.path.basename(yaml_path))[0])
    padrao = dados.get('padrao', '')
    tipo = dados.get('tipo', '')

    # Referência KiCad
    kicad = dados.get('kicad', {})
    referencia = kicad.get('referencia', '')
    valor = kicad.get('valor', nome)
    descricao = kicad.get('descricao', '')
    tags = kicad.get('tags', '')

    # Footprint name (nome do componente = nome do footprint gerado)
    footprint = nome

    # Total de pinos
    pinos = dados.get('pinos', {})
    total_pinos = pinos.get('total', 0)

    # Para padrão BGA, calcular total de pinos se não definido
    if total_pinos == 0 and padrao == 'bga':
        linhas = pinos.get('linhas', 0)
        colunas = pinos.get('colunas', 0)
        excluir = pinos.get('excluir', [])
        total_pinos = linhas * colunas - len(excluir)

    # Para padrão custom, contar pads
    if total_pinos == 0:
        pads_list = dados.get('pads', [])
        if pads_list:
            total_pinos = len(pads_list)

    # Para axial_pth sem total definido
    if total_pinos == 0 and padrao == 'axial_pth':
        total_pinos = 2

    return {
        'nome': nome,
        'tipo': tipo or padrao,
        'referencia': referencia,
        'valor': valor,
        'descricao': descricao,
        'tags': tags,
        'footprint': footprint,
        'pinos': total_pinos,
    }


def gerar_bom(yaml_dir: str, output_path: str, formato: str = 'csv') -> dict:
    """Gera BOM a partir de todos os YAMLs em um diretório.

    Args:
        yaml_dir: Diretório com arquivos .yaml
        output_path: Caminho do arquivo de saída (.csv)
        formato: 'csv' (default)

    Returns:
        dict com 'total', 'arquivo', 'componentes'
    """
    if not os.path.isdir(yaml_dir):
        raise FileNotFoundError(f"Diretório não encontrado: {yaml_dir}")

    componentes = []

    # Listar todos os YAML no diretório
    for fname in sorted(os.listdir(yaml_dir)):
        if not fname.lower().endswith(('.yaml', '.yml')):
            continue

        # Skip presets e templates
        basename = os.path.basename(fname)
        if basename.startswith('_preset_') or basename.startswith('_template'):
            continue

        yaml_path = os.path.join(yaml_dir, fname)
        comp = _extrair_componente(yaml_path)
        if comp:
            componentes.append(comp)

    # Ordenar por referência (vazio por último)
    componentes.sort(key=lambda c: (c['referencia'] == '', c['referencia'], c['nome']))

    # Garantir que o diretório de saída exista
    dir_saida = os.path.dirname(output_path)
    if dir_saida:
        os.makedirs(dir_saida, exist_ok=True)

    # Gerar CSV
    colunas = ['Item', 'Referencia', 'Valor', 'Footprint', 'Descricao', 'Pinos', 'Tags']

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(colunas)

        for idx, comp in enumerate(componentes, start=1):
            writer.writerow([
                idx,
                comp['referencia'],
                comp['valor'],
                comp['footprint'],
                comp['descricao'],
                comp['pinos'] if comp['pinos'] > 0 else '',
                comp['tags'],
            ])

    log.info("BOM gerado: %s (%d componentes)", output_path, len(componentes))

    return {
        'total': len(componentes),
        'arquivo': output_path,
        'componentes': componentes,
    }
