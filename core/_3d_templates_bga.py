# =============================================================================
# _3d_templates_bga.py
# CadQuery 3D model template for BGA (Ball Grid Array) components.
#
# Template:
#   _tmpl_bga – Generic BGA package: thin black body, solder balls, A1 marker
#
# Signature: def _tmpl_bga(dados, nome, show_fn, cq, _log)
#   dados   – dict loaded from YAML with component dimensions
#   nome    – component reference name (str)
#   show_fn – callback  show_fn(shape, name=..., options={...})
#   cq      – cadquery module (pre-imported)
#   _log    – logging helper
#
# Author : Auto-generated BGA 3-D template library
# =============================================================================

import math as _math


def _row_label(row_idx):
    """Convert row index (0-based) to letter label: 0→A, 1→B, ..., 25→Z, 26→AA, etc."""
    label = ''
    n = row_idx
    while True:
        label = chr(ord('A') + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label


def _tmpl_bga(dados, nome, show_fn, cq, _log):
    """3-D model for BGA (Ball Grid Array) packages.

    Body: thin black square sitting on PCB surface (z=0).
    Solder balls: small spheres underneath the body in a grid pattern.
    Pin A1 marker: small dot on the top surface near corner A1.
    """
    _log("[3D] bga – start")

    # ── dimensions ──────────────────────────────────────────────────────────
    pinos = dados.get('pinos', {})
    corpo = dados.get('corpo', {})

    linhas = int(pinos.get('linhas', 10))
    colunas = int(pinos.get('colunas', 10))
    pitch = float(pinos.get('pitch', 0.8))
    ball_diam = float(pinos.get('diametro_pad', 0.4))
    excluir = set(pinos.get('excluir', []))

    # Body dimensions: derived from grid or explicitly set
    body_w = float(corpo.get('largura', (colunas - 1) * pitch + pitch * 2))
    body_h_xy = float(corpo.get('comprimento', corpo.get('altura',
                       (linhas - 1) * pitch + pitch * 2)))
    body_z = float(corpo.get('altura_3d', 1.2))   # package height

    ball_r = ball_diam / 2
    standoff = ball_r * 0.8  # body sits above PCB by ball radius amount

    # ── Body ────────────────────────────────────────────────────────────────
    body = (cq.Workplane("XY")
            .box(body_w, body_h_xy, body_z, centered=(True, True, False))
            .translate((0, 0, standoff)))

    try:
        body = body.edges("|Z").fillet(min(0.3, body_w * 0.02))
    except Exception:
        pass

    show_fn(body, name=f"Body - {nome}",
            options={"color": (25, 25, 30), "alpha": 0.95})

    # ── Pin A1 marker (dot on top surface) ──────────────────────────────────
    marker_r = min(pitch * 0.25, 0.5)
    # A1 is at top-left corner of grid
    grid_x0 = -(colunas - 1) * pitch / 2
    grid_y0 = -(linhas - 1) * pitch / 2

    marker_x = grid_x0 - pitch * 0.3
    marker_y = grid_y0 - pitch * 0.3
    marker_z = standoff + body_z

    try:
        marker = (cq.Workplane("XY")
                  .workplane(offset=marker_z - 0.05)
                  .cylinder(0.1, marker_r))
        show_fn(marker, name=f"A1_marker - {nome}",
                options={"color": (220, 220, 220), "alpha": 0.95})
    except Exception:
        pass

    # ── Solder balls ────────────────────────────────────────────────────────
    ball_color = (180, 175, 160)   # solder tin color
    n_balls = 0
    is_large = (linhas * colunas > 100)

    # Assembly para exportar STEP (contém tudo)
    assy = cq.Assembly()
    assy.add(body, name="body", color=cq.Color(*[c/255 for c in (25, 25, 30)]))

    if marker_r > 0:
        try:
            assy.add(marker, name="a1_marker",
                     color=cq.Color(*[c/255 for c in (220, 220, 220)]))
        except Exception:
            pass

    ball_solids = []  # acumula .val() para Compound (BGAs grandes)

    for row in range(linhas):
        row_lbl = _row_label(row)
        for col in range(colunas):
            pin_name = f"{row_lbl}{col + 1}"
            if pin_name in excluir:
                continue

            bx = grid_x0 + col * pitch
            by = grid_y0 + row * pitch
            bz = ball_r * 0.6   # slightly squished against PCB

            try:
                ball = cq.Workplane("XY").sphere(ball_r).translate((bx, by, bz))

                if not is_large:
                    # BGAs pequenos: mostrar cada ball no viewer
                    show_fn(ball, name=f"Ball_{pin_name} - {nome}",
                            options={"color": ball_color, "alpha": 0.90})
                else:
                    ball_solids.append(ball.val())

                assy.add(ball, name=f"ball_{pin_name}",
                         color=cq.Color(*[c/255 for c in ball_color]))
                n_balls += 1
            except Exception:
                pass

    # Viewer: corpo + balls como Compound ÚNICO (3 objetos no viewer, não 258)
    if is_large:
        show_fn(body, name=f"Body - {nome}",
                options={"color": (25, 25, 30), "alpha": 0.95})
        try:
            show_fn(marker, name=f"A1_marker - {nome}",
                    options={"color": (220, 220, 220), "alpha": 0.95})
        except Exception:
            pass
        if ball_solids:
            try:
                balls_compound = cq.Compound.makeCompound(ball_solids)
                show_fn(balls_compound, name=f"Balls_{n_balls} - {nome}",
                        options={"color": ball_color, "alpha": 0.90})
                _log(f"[3D] bga – viewer: corpo + {n_balls} balls (1 Compound)")
            except Exception as e:
                _log(f"[3D] bga – Compound falhou: {e}, mostrando sem balls")

    _log(f"[3D] bga – {n_balls} balls, body {body_w}x{body_h_xy}x{body_z}mm")

    return assy

