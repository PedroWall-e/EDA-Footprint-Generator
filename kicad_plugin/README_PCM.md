# Publishing to the KiCad Plugin & Content Manager (PCM)

The PCM is the highest-leverage distribution channel: it puts this plugin **inside the KiCad the user already has open**. This guide covers packaging and publishing.

## 1. Prerequisites

- A **64×64 PNG** icon at `kicad_plugin/icon.png` (PCM requires it). You can generate one from `assets/app_icon.ico` / `assets/icon_generator.py`.
- The plugin version in [`metadata.json`](metadata.json) matches the release you're cutting (`versions[0].version`).

## 2. Build the package

```bash
python scripts/build_pcm_package.py \
  --download-url https://github.com/PedroWall-e/EDA-Footprint-Generator-Data-Frontier/releases/download/v2.0.0/DataFrontier-PCM-2.0.0.zip
```

This produces `build/pcm/DataFrontier-PCM-<version>.zip` with the PCM layout:

```
metadata.json
plugins/          # the pcbnew ActionPlugin code
resources/icon.png
```

…and prints the `sha256`, sizes, and a ready-to-paste `versions[]` block.

## 3. Publish

**Option A — Official PCM repository (max reach):**
Submit a merge request to the [KiCad PCM metadata repo](https://gitlab.com/kicad/addons/metadata) following their contribution guide. Once merged, the plugin appears in every user's PCM by default.

**Option B — Self-hosted repository (full control):**
1. Attach the built `.zip` to a GitHub Release.
2. Publish a `packages.json` (containing the printed `versions[]` block with `download_url` + `download_sha256`) and a `repository.json` pointing to it.
3. Users add your `repository.json` URL in **KiCad → Plugin and Content Manager → Manage… → +**.

## 4. On every new release

Per the [documentation-discipline rule](../.agents/AGENTS.md), bump the version in **both** `kicad_plugin/metadata.json` and `core/version.py`, add a `CHANGELOG.md` entry, then re-run the build script and update the repository index.

> The GitHub Actions workflow [`.github/workflows/release-pcm.yml`](../.github/workflows/release-pcm.yml) builds the package automatically when you push a `v*` tag and attaches it to the release.
