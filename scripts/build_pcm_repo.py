#!/usr/bin/env python3
# =============================================================================
# scripts/build_pcm_repo.py
# Gera o índice de um repositório PCM próprio (self-hosted): packages.json e
# repository.json, prontos para servir via GitHub Pages.
#
# O sha256/tamanhos são extraídos do PRÓPRIO .zip publicado no release, para
# garantir que o índice bata exatamente com o arquivo que o KiCad vai baixar.
#
# Uso:
#   python scripts/build_pcm_repo.py \
#     --zip <caminho-do-DataFrontier-PCM-X.Y.Z.zip-baixado-do-release> \
#     --download-url https://github.com/.../releases/download/vX.Y.Z/DataFrontier-PCM-X.Y.Z.zip \
#     --pages-base https://pedrowall-e.github.io/EDA-Footprint-Generator-Data-Frontier/pcm
# =============================================================================

import argparse
import hashlib
import json
import os
import time
import zipfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJ, 'docs', 'pcm')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fp:
        for chunk in iter(lambda: fp.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _install_size(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        return sum(zi.file_size for zi in zf.infolist())


def main():
    ap = argparse.ArgumentParser(description="Gera packages.json + repository.json do PCM")
    ap.add_argument('--zip', required=True, help='Caminho do .zip publicado no release')
    ap.add_argument('--download-url', required=True, help='URL do .zip no release')
    ap.add_argument('--pages-base', required=True,
                    help='Base URL onde os JSON serão servidos (sem barra final)')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    with open(os.path.join(PROJ, 'kicad_plugin', 'metadata.json'), 'r', encoding='utf-8') as f:
        meta = json.load(f)

    # --- versions[] com os campos de download derivados do zip real ---
    ver = dict(meta['versions'][0])
    ver.update({
        'download_url': args.download_url,
        'download_sha256': _sha256(args.zip),
        'download_size': os.path.getsize(args.zip),
        'install_size': _install_size(args.zip),
    })

    package = dict(meta)
    package.pop('$schema', None)  # $schema só no topo do documento, não por pacote
    package['versions'] = [ver]

    packages_doc = {
        '$schema': 'https://go.kicad.org/pcm/schemas/v1',
        'packages': [package],
    }
    packages_path = os.path.join(OUT_DIR, 'packages.json')
    with open(packages_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(packages_doc, f, indent=2, ensure_ascii=False)
        f.write('\n')

    # --- repository.json aponta para packages.json com seu sha e timestamp ---
    now = int(time.time())
    repo_doc = {
        '$schema': 'https://go.kicad.org/pcm/schemas/v1',
        'name': 'EDA Footprint Generator PCM Repository',
        'maintainer': meta.get('maintainer', meta.get('author')),
        'packages': {
            'url': f"{args.pages_base}/packages.json",
            'sha256': _sha256(packages_path),
            'update_time_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now)),
            'update_timestamp': now,
        },
    }
    repo_path = os.path.join(OUT_DIR, 'repository.json')
    with open(repo_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(repo_doc, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print("OK — arquivos do repositório PCM gerados:")
    print(f"  {packages_path}")
    print(f"  {repo_path}")
    print(f"\n  download_sha256 : {ver['download_sha256']}")
    print(f"  repo URL (add no KiCad PCM): {args.pages_base}/repository.json")


if __name__ == '__main__':
    main()
