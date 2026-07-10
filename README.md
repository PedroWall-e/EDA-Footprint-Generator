<p align="right"><a href="README.pt-BR.md">🇧🇷 Português</a></p>

# 🏭 EDA Footprint Generator — Parametric footprints, symbols & 3D from YAML

> Stop hand-drawing footprints. Describe a component once in **YAML** and generate the **KiCad footprint** (`.kicad_mod`), **schematic symbol** (`.kicad_sym`) and **3D model** (`.step`) in one shot — validated against **IPC-7351B** before anything is written.

[![CI](https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier/actions/workflows/ci.yml/badge.svg)](https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![KiCad 6+](https://img.shields.io/badge/KiCad-6%20%7C%207%20%7C%208-brightgreen.svg)](https://www.kicad.org/)

---

## The problem

Drawing a footprint by hand is slow and, worse, **error-prone** — a pad 0.2 mm off, a courtyard that overlaps, an annular ring below spec, and you find out when the board comes back from fab. Existing part libraries help only if *your* exact part is already in them.

**EDA Footprint Generator** takes a different route: you describe the component's physical parameters (body size, pin pitch, package type) in a small YAML file, and it generates a **complete, standards-checked** footprint + symbol + 3D model. The same source produces exports for **KiCad, Eagle and Altium**, and the STEP model drops straight into **Fusion 360**.

```yaml
# resistor_470R.yaml — the whole component in 20 lines
nome: R_Axial_470R
padrao: axial_pth
pinos:  { espacamento: 10.16, diametro_pad: 1.8, diametro_furo: 0.8 }
corpo:  { comprimento: 6.0, diametro: 2.5, formato: cilindro }
margens:{ courtyard: 0.5, silkscreen: 0.12, fab_line: 0.10 }
kicad:  { referencia: "R?", valor: "470R", modelo_3d: "R_Axial_470R.step" }
```

```bash
python cli.py gerar resistor_470R.yaml -o saida/
# ✅ R_Axial_470R.kicad_mod   ✅ R_Axial_470R.kicad_sym   ✅ R_Axial_470R.step
```

<!-- TODO: add a 10-second demo GIF here -> assets/demo.gif (YAML on the left, footprint + 3D preview on the right) -->

---

## Why trust the output?

Footprint mistakes become **manufacturing mistakes**. So every generation is checked before a file is written:

- **IPC-7351B validation** — pad-to-pad clearance, courtyard excess, annular ring, silkscreen-to-pad. Errors **abort** generation; warnings are surfaced. ([`core/validador_ipc.py`](core/validador_ipc.py))
- **JSON Schema** — the component structure is validated against a formal schema. ([`schemas/component.schema.json`](schemas/component.schema.json))
- **DRC** — 8 configurable design-rule checks on the generated footprint. ([`core/verificador_drc.py`](core/verificador_drc.py))
- **CI** — 127 automated tests run on **Windows + Linux** across **Python 3.10 / 3.11 / 3.12** on every push.

---

## Features

| | |
|---|---|
| 🦶 **Footprints** | `.kicad_mod` — pads, silkscreen, courtyard, fab layers (KiCad 6/7/8) |
| 🔣 **Symbols** | `.kicad_sym` — schematic symbol with named, typed pins |
| 🧊 **3D models** | `.step` — parametric solid via CadQuery / OpenCASCADE (imports into Fusion 360) |
| 🔄 **Multi-EDA export** | KiCad `.pretty` libraries, Eagle `.lbr`, Altium CSV, BOM CSV |
| 📐 **7 pad patterns** | `axial_pth`, `radial_pth`, `dual_pth`, `dual_smd`, `quad_smd`, `custom`, `bga` |
| 🖥️ **4 ways to drive it** | Desktop GUI (PyQt5), CLI, REST API (FastAPI), native KiCad plugin |
| ✅ **Validation built-in** | IPC-7351B + JSON Schema + DRC |

### Supported packages (out of the box)

Chip (0402/0603/0805/1206), SOT-23/223, SSOP, SOIC, DIP, QFN, QFP, BGA, TO-92/220/247, DPAK, DO-214/SOD-123, axial/radial PTH (resistor, diode, LED, capacitor, crystal), pin headers, castellated RF modules, coin-cell batteries and patch antennas. Start from any of the 30+ presets in [`modulos_config/_preset_*.yaml`](modulos_config/).

---

## Quick start

> **Requires:** Python 3.10+, and KiCad 6+ to open the generated files.

```bash
git clone https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier.git
cd EDA-Footprint-Generator-Data-Frontier

# Windows (recommended) — sets up the venv + local CadQuery/CQ-Editor deps
.\scripts\setup_ambiente.ps1

# Generate a component
python cli.py gerar modulos_config/NE555_DIP8.yaml -o saida/

# Validate without generating
python cli.py validar modulos_config/NE555_DIP8.yaml

# Generate an entire folder
python cli.py batch modulos_config/ -o saida/

# JSON output (for scripts / AI agents)
python cli.py --json gerar modulos_config/NE555_DIP8.yaml -o saida/
```

> [!WARNING]
> Don't run `pip install -r requirements.txt` directly — `cadquery` and `CQ-Editor` are installed from the local sources in `libs/` (the setup script handles this). The 3D/STEP output needs CadQuery; footprint + symbol generation work without it.

### Desktop GUI

```bash
abrir_dual.bat        # Windows
./abrir_dual.sh       # Linux / macOS
```

Edit the YAML on the left, press `Ctrl+Enter`, and see the 2D footprint, schematic symbol and live 3D model side by side.

---

## How does it compare?

Because you'll compare anyway — here's an honest take:

| Tool | Approach | Where EDA Footprint Generator differs |
|---|---|---|
| **[kicad-footprint-generator](https://gitlab.com/kicad/libraries/kicad-footprint-generator)** (official) | Python scripts, no GUI | EDA Footprint Generator adds a GUI, a declarative YAML layer, symbol + 3D in one run, and multi-EDA export |
| **SnapEDA / Ultra Librarian** | Download pre-made parts | EDA Footprint Generator *generates* parametrically — works for parts not in any library, and you own the source |
| **Component Search Engine** | Vendor part catalog | No account, no per-part download; describe the package and generate offline |

If your exact part already exists in a library, grabbing it there is faster. EDA Footprint Generator wins when you need a **custom or uncommon package**, want **KiCad + Eagle + Altium + 3D from one definition**, or want the generation **IPC-checked and reproducible** in CI.

---

## Interfaces

| Interface | Entry point | Use for |
|---|---|---|
| **GUI** | `abrir_dual.bat` → [`gui/interface_dual.py`](gui/interface_dual.py) | Interactive design with 2D + 3D preview |
| **CLI** | [`cli.py`](cli.py) | Automation, batch, CI, AI agents (`--json`, `--stdin`) |
| **REST API** | [`api_server.py`](api_server.py) → `http://localhost:8042/docs` | Integrating from other apps |
| **KiCad plugin** | [`kicad_plugin/`](kicad_plugin/) | Generating from inside pcbnew |

---

## Documentation

- **YAML reference** — [`docs/MANUAL_YAML_REFERENCIA.yaml`](docs/MANUAL_YAML_REFERENCIA.yaml)
- **JSON Schema** — [`schemas/component.schema.json`](schemas/component.schema.json) (`python cli.py schema`)
- **Presets** — [`modulos_config/_preset_*.yaml`](modulos_config/)
- **Contributing** — [`CONTRIBUTING.md`](CONTRIBUTING.md) · **Changelog** — [`CHANGELOG.md`](CHANGELOG.md)

---

## Contributing

Issues and PRs are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [good first issues](https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier/labels/good%20first%20issue). Run the tests before opening a PR:

```bash
python tests/teste_v2.py    # expected: 107/107 OK
```

---

## License & trademarks

Distributed under the **GNU General Public License v3.0** (GPL-3.0-or-later). See [LICENSE](LICENSE) and [NOTICE](NOTICE).

> KiCad, Eagle, Altium and Fusion 360 are trademarks of their respective owners. This project is **not affiliated with or endorsed by** any of them; it only reads/writes their documented file formats for interoperability.

---

<p align="center"><sub>Built with 💜 using PyQt5 · CadQuery · KicadModTree</sub></p>
