#!/usr/bin/env python3
# =============================================================================
# scripts/build_pcm_package.py
# Empacota o plugin KiCad no formato do Plugin & Content Manager (PCM).
#
# Monta a estrutura exigida pelo PCM, gera o .zip, calcula sha256 e tamanhos,
# e imprime o bloco `versions[]` pronto para colar no índice do repositório
# (packages.json) que o PCM consome.
#
# Uso:
#   python scripts/build_pcm_package.py --download-url https://github.com/.../releases/download/v2.0.0/DataFrontier-PCM.zip
#
# Estrutura gerada dentro do zip (exigida pelo PCM):
#   metadata.json
#   plugins/            <- código do ActionPlugin
#   resources/icon.png  <- ícone 64x64 (obrigatório pelo PCM)
# =============================================================================

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(PROJ, 'kicad_plugin')
BUILD_DIR = os.path.join(PROJ, 'build', 'pcm')
STAGE_DIR = os.path.join(BUILD_DIR, 'pkg')


def _stage_package():
    """Monta a árvore de arquivos exigida pelo PCM em STAGE_DIR."""
    if os.path.exists(STAGE_DIR):
        shutil.rmtree(STAGE_DIR)
    os.makedirs(os.path.join(STAGE_DIR, 'plugins'), exist_ok=True)
    os.makedirs(os.path.join(STAGE_DIR, 'resources'), exist_ok=True)

    # metadata.json (na raiz do pacote)
    shutil.copy2(os.path.join(PLUGIN_DIR, 'metadata.json'),
                 os.path.join(STAGE_DIR, 'metadata.json'))

    # Código do plugin → plugins/
    for fname in os.listdir(PLUGIN_DIR):
        if fname.endswith('.py'):
            shutil.copy2(os.path.join(PLUGIN_DIR, fname),
                         os.path.join(STAGE_DIR, 'plugins', fname))

    # Ícone → resources/icon.png (PCM exige 64x64 PNG)
    icon_src = os.path.join(PLUGIN_DIR, 'icon.png')
    icon_dst = os.path.join(STAGE_DIR, 'resources', 'icon.png')
    if os.path.isfile(icon_src):
        shutil.copy2(icon_src, icon_dst)
    else:
        print("[AVISO] kicad_plugin/icon.png (64x64 PNG) não encontrado — "
              "o PCM exige um ícone. Adicione-o antes de publicar.",
              file=sys.stderr)


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def _zip_package(zip_path):
    """Zipa STAGE_DIR preservando a estrutura relativa."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(STAGE_DIR):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, STAGE_DIR)
                zf.write(full, arc)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fp:
        for chunk in iter(lambda: fp.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Empacota o plugin para o KiCad PCM")
    ap.add_argument('--download-url', default='REPLACE_WITH_RELEASE_ASSET_URL',
                    help='URL final do .zip no release (vai para o packages.json)')
    args = ap.parse_args()

    os.makedirs(BUILD_DIR, exist_ok=True)
    with open(os.path.join(PLUGIN_DIR, 'metadata.json'), 'r', encoding='utf-8') as f:
        meta = json.load(f)
    version = meta['versions'][0]['version']

    zip_path = os.path.join(BUILD_DIR, f"DataFrontier-PCM-{version}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    _stage_package()
    install_size = _dir_size(STAGE_DIR)
    _zip_package(zip_path)
    download_size = os.path.getsize(zip_path)
    sha = _sha256(zip_path)

    # Bloco versions[] pronto para o índice do repositório PCM (packages.json)
    version_block = dict(meta['versions'][0])
    version_block.update({
        'download_url': args.download_url,
        'download_sha256': sha,
        'download_size': download_size,
        'install_size': install_size,
    })

    print("\n" + "=" * 70)
    print(f"  Pacote PCM: {zip_path}")
    print(f"  sha256    : {sha}")
    print(f"  zip size  : {download_size} bytes")
    print(f"  instalado : {install_size} bytes")
    print("=" * 70)
    print("\nCole este bloco em versions[] do seu packages.json (índice do repositório):\n")
    print(json.dumps(version_block, indent=2, ensure_ascii=False))
    print()


if __name__ == '__main__':
    main()
