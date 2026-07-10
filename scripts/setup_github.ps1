# =============================================================================
# scripts/setup_github.ps1
# Configura o lado do GitHub do repositório: descrição, topics, labels e
# abre as "good first issues" iniciais.
#
# Requer o GitHub CLI: https://cli.github.com/  (winget install GitHub.cli)
# Depois: gh auth login
#
# Uso:
#   .\scripts\setup_github.ps1
# =============================================================================

$ErrorActionPreference = 'Stop'
$REPO = 'PedroWall-e/EDA-Footprint-Generator-Data-Frontier'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) nao encontrado. Instale com: winget install GitHub.cli ; depois: gh auth login"
    exit 1
}

Write-Host "==> Definindo descricao e topics do repositorio..." -ForegroundColor Cyan
gh repo edit $REPO `
  --description "Parametric EDA component generator: YAML -> KiCad footprint + symbol + 3D STEP, IPC-7351B validated. Exports to KiCad, Eagle, Altium." `
  --homepage "https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier" `
  --add-topic kicad `
  --add-topic pcb `
  --add-topic footprint `
  --add-topic eda `
  --add-topic altium `
  --add-topic eagle `
  --add-topic cadquery `
  --add-topic step `
  --add-topic ipc-7351 `
  --add-topic electronics

Write-Host "==> Criando labels..." -ForegroundColor Cyan
$labels = @(
    @{ name = 'good first issue'; color = '7057ff'; desc = 'Bom ponto de entrada para novos contribuidores' },
    @{ name = 'help wanted';      color = '008672'; desc = 'Precisa de ajuda da comunidade' },
    @{ name = 'new-package';      color = '0e8a16'; desc = 'Pedido de novo package/footprint' }
)
foreach ($l in $labels) {
    gh label create $l.name --repo $REPO --color $l.color --description $l.desc --force
}

Write-Host "==> Abrindo good first issues..." -ForegroundColor Cyan
$issues = @(
    @{ title = 'Add preset: QFN-20 (0.5mm pitch)';
       body  = "Add `modulos_config/_preset_QFN20.yaml` by copying `_preset_QFN16_4x4.yaml` and adjusting pin count/body. Validate with `python cli.py validar` and add to the SKILL.md preset table (see documentation-discipline rule in CONTRIBUTING.md)." },
    @{ title = 'Record a 10-second demo GIF for the README';
       body  = "Capture the GUI generating a footprint from YAML (YAML left, footprint + 3D right). Save as `assets/demo.gif` and reference it in `README.md` + `README.pt-BR.md`. Replaces the TODO placeholder in the README." },
    @{ title = 'CLI: add a --dry-run flag to `gerar`';
       body  = "Add `--dry-run` to `cli.py gerar` that validates and prints what would be generated without writing files. Update the SKILL.md and README CLI sections per the documentation-discipline rule." },
    @{ title = 'Improve IPC validation error messages (expected vs actual)';
       body  = "In `core/validador_ipc.py`, include the expected vs measured value in each error (e.g. 'annular ring 0.12mm < min 0.15mm'). Add a test in `tests/teste_v2.py`." },
    @{ title = 'Translate the YAML reference to English';
       body  = "Translate `docs/MANUAL_YAML_REFERENCIA.yaml` into `docs/YAML_REFERENCE.en.yaml`. Good first task to learn the schema." },
    @{ title = 'Add a 64x64 PNG icon for the KiCad PCM package';
       body  = "The PCM requires `kicad_plugin/icon.png` (64x64). Generate one from `assets/app_icon.ico` / `assets/icon_generator.py`. See `kicad_plugin/README_PCM.md`." }
)
foreach ($i in $issues) {
    gh issue create --repo $REPO --title $i.title --body $i.body --label 'good first issue'
}

Write-Host "`nPronto! Repositorio configurado." -ForegroundColor Green
