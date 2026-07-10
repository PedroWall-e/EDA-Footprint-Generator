#!/usr/bin/env python3
# =============================================================================
# build/build_installer.py
# Script de build para gerar o instalador da EDA Footprint Generator
# usando PyInstaller.
#
# Uso:  python build/build_installer.py
# =============================================================================

import PyInstaller.__main__
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build():
    """Executa o PyInstaller para empacotar a aplicação."""
    args = [
        os.path.join(PROJ, 'gui', 'interface_dual.py'),
        '--name=CAM-CAD-DataFrontier',
        '--onedir',
        '--windowed',
        f'--add-data={os.path.join(PROJ, "core")}{os.pathsep}core',
        f'--add-data={os.path.join(PROJ, "gui")}{os.pathsep}gui',
        f'--add-data={os.path.join(PROJ, "modulos_config")}{os.pathsep}modulos_config',
        f'--add-data={os.path.join(PROJ, "docs", "MANUAL_YAML_REFERENCIA.yaml")}{os.pathsep}docs',
        '--hidden-import=cadquery',
        '--hidden-import=OCP',
        '--collect-all=cadquery',
        f'--distpath={os.path.join(PROJ, "build", "dist")}',
        f'--workpath={os.path.join(PROJ, "build", "work")}',
        f'--specpath={os.path.join(PROJ, "build")}',
        f'--icon={os.path.join(PROJ, "assets", "app_icon.ico")}',
    ]

    print('╔══════════════════════════════════════════════════════════╗')
    print('║  Build — EDA Footprint Generator               ║')
    print('╠══════════════════════════════════════════════════════════╣')
    print(f'║  Projeto : {PROJ}')
    print(f'║  Saída   : {os.path.join(PROJ, "build", "dist")}')
    print('╚══════════════════════════════════════════════════════════╝')
    print()

    PyInstaller.__main__.run(args)

    print()
    print('✅  Build concluído com sucesso!')
    print(f'    Executável em: {os.path.join(PROJ, "build", "dist", "CAM-CAD-DataFrontier")}')


if __name__ == '__main__':
    build()
