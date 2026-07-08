# Build — Plataforma CAM-CAD Data Frontier

## Pré-requisitos

1. **Python 3.10+** instalado
2. **Ambiente virtual** configurado com todas as dependências.
   Use o script de setup do projeto (a partir da raiz do projeto):
   ```powershell
   .\scripts\setup_ambiente.ps1
   ```
   Esse script cria o `.venv`, instala todas as dependências do `requirements.txt` e o **PyInstaller**.

## Gerar o Executável

### Windows

```bash
# A partir da raiz do projeto:
python build/build_installer.py
```

### Linux / macOS

```bash
python3 build/build_installer.py
```

## Estrutura de Saída

Após o build, a seguinte estrutura será criada:

```
build/
├── dist/
│   └── CAM-CAD-DataFrontier/     ← Diretório do executável
│       ├── CAM-CAD-DataFrontier.exe  (Windows)
│       ├── core/
│       ├── gui/
│       ├── modulos_config/
│       └── ...
├── work/                          ← Arquivos temporários (pode deletar)
├── CAM-CAD-DataFrontier.spec      ← Spec file do PyInstaller
├── build_installer.py             ← Este script
└── README_BUILD.md                ← Este arquivo
```

## Notas

- O build usa `--onedir` para manter as dependências em um diretório (mais fácil para debug).
- Use `--onefile` no script se preferir um único executável (mais lento para iniciar).
- O `--windowed` suprime a janela de console no Windows.
- **CadQuery e OCP** são incluídos via `--hidden-import` e `--collect-all`.
- Se encontrar erros com imports faltando, adicione `--hidden-import=modulo_faltando` ao script.

## Distribuição

Para distribuir, compacte o diretório `build/dist/CAM-CAD-DataFrontier/` em um `.zip` ou use um instalador como **NSIS** ou **Inno Setup** para criar um instalador `.exe`.
