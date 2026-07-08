# Nao use $ErrorActionPreference = "Stop" globalmente
# para evitar que tracebacks do Python sejam tratados como erros do PowerShell

$PROJETO_DIR = Split-Path $PSScriptRoot -Parent
Set-Location $PROJETO_DIR

Write-Host ""
Write-Host "============================================================"
Write-Host "  SETUP DO AMBIENTE - GERADOR DE FOOTPRINTS KICAD + STEP"
Write-Host "============================================================"
Write-Host "  Pasta do projeto: $PROJETO_DIR"
Write-Host ""

# -----------------------------------------------------------------------------
# 1. Verificar Python disponivel (qualquer versao >= 3.10)
# -----------------------------------------------------------------------------
Write-Host "[1/7] Verificando Python do sistema..."

$pythonCmd = $null
foreach ($cmd in @("python3.11", "python3.10", "python3", "python")) {
    try {
        $versao = & $cmd --version 2>&1
        $versaoStr = "$versao"
        if ($versaoStr -match "Python 3\.") {
            $pythonCmd = $cmd
            Write-Host "      Encontrado: $versaoStr ($cmd)"
            break
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host "[ERRO] Nenhum Python encontrado no PATH."
    Write-Host "       Baixe em: https://www.python.org/downloads/"
    exit 1
}

# Capturar versao exata para avisos
$versaoCompleta = & $pythonCmd --version 2>&1
$py313 = "$versaoCompleta" -match "Python 3\.1[3-9]"
if ($py313) {
    Write-Host ""
    Write-Host "  AVISO: Python 3.13+ detectado."
    Write-Host "  O OCP (binario do OpenCASCADE) pode nao ter wheel para 3.13."
    Write-Host "  Tentaremos instalar via 'pip install cadquery' que resolve"
    Write-Host "  as dependencias binarias automaticamente."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# 2. Criar o ambiente virtual em .venv/
# -----------------------------------------------------------------------------
Write-Host "[2/7] Criando ambiente virtual em .venv/ ..."

$VENV_DIR = Join-Path $PROJETO_DIR ".venv"
if (Test-Path $VENV_DIR) {
    Write-Host "      .venv ja existe - pulando criacao."
} else {
    & $pythonCmd -m venv $VENV_DIR
    Write-Host "      .venv criado com sucesso."
}

$PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$PIP    = Join-Path $VENV_DIR "Scripts\pip.exe"

Write-Host "      Atualizando pip dentro do venv..."
& $PYTHON -m pip install --upgrade pip setuptools wheel --quiet

# -----------------------------------------------------------------------------
# 3. Pasta libs/ (clones ja feitos na tentativa anterior)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/7] Verificando pasta libs/ ..."

$LIBS_DIR = Join-Path $PROJETO_DIR "libs"
if (-not (Test-Path $LIBS_DIR)) {
    New-Item -ItemType Directory -Path $LIBS_DIR | Out-Null
    Write-Host "      Pasta libs/ criada."
} else {
    Write-Host "      Pasta libs/ ja existe."
}

# -----------------------------------------------------------------------------
# 4. Clonar/atualizar cadquery e CQ-Editor
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/7] Verificando repositorios de codigo-fonte..."

$CQ_DIR = Join-Path $LIBS_DIR "cadquery"
if (Test-Path $CQ_DIR) {
    Write-Host "      cadquery ja clonado - OK."
} else {
    Write-Host "      Clonando cadquery..."
    & git clone https://github.com/CadQuery/cadquery.git $CQ_DIR --depth=1
    Write-Host "      cadquery clonado."
}

$CQEDITOR_DIR = Join-Path $LIBS_DIR "CQ-editor"
if (Test-Path $CQEDITOR_DIR) {
    Write-Host "      CQ-editor ja clonado - OK."
} else {
    Write-Host "      Clonando CQ-editor..."
    & git clone https://github.com/CadQuery/CQ-editor.git $CQEDITOR_DIR --depth=1
    Write-Host "      CQ-editor clonado."
}

# -----------------------------------------------------------------------------
# 5. Instalar cadquery via pip (resolve OCP automaticamente como dependencia)
#    Esta e a estrategia correta: pip resolve a versao de OCP compativel
#    com o Python do venv sem precisar especificar manualmente.
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/7] Instalando OCP + cadquery (binarios via pip) ..."
Write-Host "      Isso pode demorar varios minutos (~300-500MB)..."
Write-Host "      Por favor aguarde..."

# Instala cadquery do PyPI para obter os binarios OCP corretos no venv
# Depois vamos sobrescrever com a versao editavel de libs/cadquery
$pipOutput = & $PIP install cadquery 2>&1
$pipExitCode = $LASTEXITCODE
Write-Host $pipOutput

if ($pipExitCode -ne 0) {
    Write-Host ""
    Write-Host "  FALHA ao instalar cadquery via pip."
    Write-Host "  Provavelmente nao ha wheel de OCP para Python $versaoCompleta."
    Write-Host ""
    Write-Host "  SOLUCOES:"
    Write-Host "  1. Instale Python 3.11 de: https://www.python.org/downloads/release/python-3110/"
    Write-Host "     Depois rode novamente: powershell -File setup_ambiente.ps1"
    Write-Host ""
    Write-Host "  2. Ou use o CQ-Editor standalone (Python embutido):"
    Write-Host "     https://github.com/CadQuery/CQ-editor/releases"
    Write-Host ""
    Write-Host "  O footprint 2D (KiCad) funciona mesmo sem cadquery."
    Write-Host "  Para testar apenas o footprint:"
    Write-Host "    & '$PYTHON' gui\interface_dual.py --somente-footprint"
    Write-Host ""

    # Instalar apenas o necessario para o footprint 2D funcionar
    Write-Host "  Instalando dependencias para footprint 2D (sem cadquery)..."
    & $PIP install PyYAML --quiet
    Write-Host "  PyYAML instalado."

} else {
    Write-Host "      cadquery + OCP instalados com sucesso."

    # -------------------------------------------------------------------------
    # 6. Substituir cadquery por versao editavel (libs/cadquery)
    #    Agora que os binarios OCP estao no venv, instala o codigo Python
    #    de libs/cadquery em modo editavel para permitir modificacoes.
    # -------------------------------------------------------------------------
    Write-Host ""
    Write-Host "[6/7] Configurando instalacoes editaveis..."

    Write-Host "      Substituindo cadquery por versao editavel de libs/cadquery..."
    & $PIP install -e $CQ_DIR --no-deps --quiet
    Write-Host "      cadquery [editavel] configurado."

    Write-Host "      Instalando CQ-editor [editavel]..."
    & $PIP install -e $CQEDITOR_DIR --quiet
    Write-Host "      CQ-editor [editavel] configurado."

    Write-Host "      Instalando PyYAML..."
    & $PIP install PyYAML --quiet
    Write-Host "      PyYAML instalado."
}

# KicadModTree via .pth (funciona independente do cadquery)
$SITE_PACKAGES = & $PYTHON -c "import site; print(site.getsitepackages()[0])" 2>&1
$PTH_FILE = Join-Path "$SITE_PACKAGES" "projeto_local.pth"
"$PROJETO_DIR" | Set-Content $PTH_FILE -Encoding UTF8
Write-Host "      KicadModTree adicionado ao Python path."

# -----------------------------------------------------------------------------
# 7. Criar pasta saida/
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[7/7] Criando pasta saida/ ..."
$SAIDA_DIR = Join-Path $PROJETO_DIR "saida"
if (-not (Test-Path $SAIDA_DIR)) {
    New-Item -ItemType Directory -Path $SAIDA_DIR | Out-Null
}
Write-Host "      Pasta saida/ pronta."

# -----------------------------------------------------------------------------
# Criar scripts de atalho .bat
# -----------------------------------------------------------------------------
$rodatBat = Join-Path $PROJETO_DIR "rodar.bat"
"@echo off`n`"%~dp0.venv\Scripts\python.exe`" `"%~dp0gui\interface_dual.py`" %*" | Set-Content $rodatBat -Encoding ASCII

$editorBat = Join-Path $PROJETO_DIR "abrir_cqeditor.bat"
"@echo off`n`"%~dp0.venv\Scripts\python.exe`" -m cq_editor %*" | Set-Content $editorBat -Encoding ASCII

# Testar se imports basicos funcionam
Write-Host ""
Write-Host "Testando imports..."
$testeYaml = & $PYTHON -c "import yaml; print('yaml OK')" 2>&1
Write-Host "  $testeYaml"
$testeKmt = & $PYTHON -c "import KicadModTree; print('KicadModTree OK')" 2>&1
Write-Host "  $testeKmt"
$testeCq = & $PYTHON -c "import cadquery; print('cadquery OK')" 2>&1
Write-Host "  $testeCq"

# -----------------------------------------------------------------------------
# Resumo final
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "  SETUP CONCLUIDO!"
Write-Host "============================================================"
Write-Host ""
Write-Host "  Estrutura criada:"
Write-Host "    .venv/           - Python isolado com todas as dependencias"
Write-Host "    libs/cadquery/   - Codigo-fonte cadquery (editavel)"
Write-Host "    libs/CQ-editor/  - Codigo-fonte CQ-Editor (editavel)"
Write-Host "    KicadModTree_dev/ - Ja estava aqui (no path)"
Write-Host "    saida/           - Arquivos gerados serao salvos aqui"
Write-Host ""
Write-Host "  Para gerar os arquivos:"
Write-Host "    rodar.bat"
Write-Host "    rodar.bat --somente-footprint"
Write-Host "    rodar.bat --somente-3d"
Write-Host ""
Write-Host "  Para abrir o visualizador 3D:"
Write-Host "    abrir_cqeditor.bat"
Write-Host "============================================================"
