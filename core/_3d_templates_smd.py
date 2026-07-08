# =============================================================================
# _3d_templates_smd.py
# CadQuery 3D model templates for SMD components.
#
# Templates:
#   _tmpl_smd_chip   – 0402 / 0603 / 0805 / 1206 chip passives
#   _tmpl_smd_diode  – SOD-123, SMA / DO-214AC diodes
#   _tmpl_sot23      – SOT-23-3, SOT-23-5, SOT-223
#   _tmpl_ssop       – SSOP-20 and similar narrow-pitch gull-wing ICs
#
# Signature: def _tmpl_xxx(dados, nome, show_fn, cq, _log)
#   dados   – dict loaded from YAML with component dimensions
#   nome    – component reference name (str)
#   show_fn – callback  show_fn(shape, name=..., options={...})
#   cq      – cadquery module (pre-imported)
#   _log    – logging helper
#
# Author : Auto-generated SMD 3-D template library
# =============================================================================

import math as _math


# ─────────────────────────────────────────────────────────────────────────────
# 1.  SMD CHIP  (0402 / 0603 / 0805 / 1206 passives)
# ─────────────────────────────────────────────────────────────────────────────

def _tmpl_smd_chip(dados, nome, show_fn, cq, _log):
    """
    3-D model for SMD chip passives (resistors, capacitors, inductors).
    Body sits at z=0 (PCB top surface).  Two metal terminals wrap each end.
    """
    _log("[3D] smd_chip – start")

    # ── dimensions ──────────────────────────────────────────────────────────
    corpo  = dados.get("corpo", {})
    pinos  = dados.get("pinos", {})

    body_w = float(corpo.get("largura", 2.0))        # X  (across pads)
    body_l = float(corpo.get("comprimento", 1.25))    # Y  (along pads)
    body_h = float(corpo.get("altura_3d", 0.65))      # Z  height

    # centre-to-centre distance between pads (along X axis)
    afast  = float(corpo.get("afastamento_colunas", body_w))

    # terminal covers ~30 % of body length on each end
    term_len = body_w * 0.30
    term_w   = body_l           # same width as body
    term_h   = body_h           # same height as body

    # ── body colour heuristic ───────────────────────────────────────────────
    nome_lower = nome.lower() if nome else ""
    is_cap = ("cap" in nome_lower or "c_" in nome_lower)
    body_colour = (180, 150, 80) if is_cap else (45, 30, 20)
    term_colour = (200, 200, 210)

    # ── body ────────────────────────────────────────────────────────────────
    body = (
        cq.Workplane("XY")
        .box(body_w, body_l, body_h, centered=(True, True, False))
    )
    try:
        body = body.edges("|Z").fillet(min(0.05, body_l * 0.04))
    except Exception:
        pass

    show_fn(body, name=f"{nome}_body",
            options={"color": body_colour, "alpha": 0.95})
    _log(f"  body  {body_w:.2f} x {body_l:.2f} x {body_h:.2f}")

    # ── terminals (left / right, centred on body ends) ──────────────────────
    for side in (-1, +1):
        tx = side * (body_w / 2.0 - term_len / 2.0)
        term = (
            cq.Workplane("XY")
            .center(tx, 0)
            .box(term_len, term_w, term_h, centered=(True, True, False))
        )
        show_fn(term, name=f"{nome}_term_{'L' if side < 0 else 'R'}",
                options={"color": term_colour, "alpha": 0.95})

    _log("[3D] smd_chip – done")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  SMD DIODE  (SOD-123 / SMA / DO-214AC)
# ─────────────────────────────────────────────────────────────────────────────

def _tmpl_smd_diode(dados, nome, show_fn, cq, _log):
    """
    3-D model for SMD diodes with gull-wing terminals and cathode band.
    """
    _log("[3D] smd_diode – start")

    corpo = dados.get("corpo", {})
    pinos = dados.get("pinos", {})

    body_w = float(corpo.get("largura", 2.8))
    body_l = float(corpo.get("comprimento", 1.8))
    body_h = float(corpo.get("altura_3d", 1.2))

    afast = float(corpo.get("afastamento_colunas", body_w + 1.0))

    body_colour = (25, 25, 25)
    term_colour = (200, 200, 210)
    band_colour = (220, 220, 220)

    # ── body ────────────────────────────────────────────────────────────────
    body = (
        cq.Workplane("XY")
        .box(body_w, body_l, body_h, centered=(True, True, False))
    )
    try:
        body = body.edges("|Z").fillet(min(0.1, body_l * 0.05))
    except Exception:
        pass
    try:
        body = body.edges("|Y").chamfer(0.08)
    except Exception:
        pass

    show_fn(body, name=f"{nome}_body",
            options={"color": body_colour, "alpha": 0.95})

    # ── cathode band (stripe on −X end) ────────────────────────────────────
    band_width = 0.5
    band = (
        cq.Workplane("XY")
        .center(-(body_w / 2.0 - band_width / 2.0 - 0.15), 0)
        .box(band_width, body_l + 0.02, body_h + 0.02,
             centered=(True, True, False))
    )
    show_fn(band, name=f"{nome}_cathode_band",
            options={"color": band_colour, "alpha": 0.95})

    # ── gull-wing terminals ─────────────────────────────────────────────────
    lead_thick = 0.15
    lead_width = body_l * 0.55
    foot_len   = 0.5                   # horizontal foot touching PCB
    # vertical riser height = body_h (goes from PCB to body centre-height)
    # standoff above body centre is negligible for diodes

    half_body = body_w / 2.0
    half_span = afast / 2.0            # from centre to pad centre
    ext_len   = half_span - half_body  # horizontal extension beyond body

    for side, label in [(-1, "A"), (+1, "K")]:
        # horizontal foot on PCB (z = 0..lead_thick)
        foot = (
            cq.Workplane("XY")
            .center(side * (half_span - foot_len / 2.0), 0)
            .box(foot_len, lead_width, lead_thick,
                 centered=(True, True, False))
        )
        # vertical riser
        riser_h = body_h * 0.5
        riser = (
            cq.Workplane("XY")
            .center(side * half_body, 0)
            .box(lead_thick, lead_width, riser_h,
                 centered=(True, True, False))
        )
        # horizontal extension from body to foot (at z = 0..lead_thick)
        if ext_len > 0.01:
            horiz = (
                cq.Workplane("XY")
                .center(side * (half_body + ext_len / 2.0), 0)
                .box(ext_len, lead_width, lead_thick,
                     centered=(True, True, False))
            )
            lead_assy = foot.union(riser).union(horiz)
        else:
            lead_assy = foot.union(riser)

        show_fn(lead_assy, name=f"{nome}_lead_{label}",
                options={"color": term_colour, "alpha": 0.95})

    _log("[3D] smd_diode – done")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  SOT-23  (SOT-23-3, SOT-23-5, SOT-223)
# ─────────────────────────────────────────────────────────────────────────────

def _tmpl_sot23(dados, nome, show_fn, cq, _log):
    """
    3-D model for SOT-23-3, SOT-23-5, and SOT-223 packages.
    Gull-wing leads distributed on two sides; pin-1 dot on body.
    """
    _log("[3D] sot23 – start")

    corpo = dados.get("corpo", {})
    pinos = dados.get("pinos", {})

    body_w = float(corpo.get("largura", 1.3))       # X  (across leads)
    body_l = float(corpo.get("comprimento", 2.9))    # Y  (along leads)
    body_h = float(corpo.get("altura_3d", 1.1))

    total  = int(pinos.get("total", 3))
    pitch  = float(pinos.get("pitch", 0.95))
    afast  = float(corpo.get("afastamento_colunas", body_w + 1.6))

    body_colour = (30, 30, 30)
    lead_colour = (200, 180, 60)
    dot_colour  = (220, 220, 220)

    # ── body ────────────────────────────────────────────────────────────────
    body = (
        cq.Workplane("XY")
        .box(body_w, body_l, body_h, centered=(True, True, False))
    )
    try:
        body = body.edges("|Z").chamfer(min(0.15, body_w * 0.08))
    except Exception:
        pass

    show_fn(body, name=f"{nome}_body",
            options={"color": body_colour, "alpha": 0.95})

    # ── pin distribution per side ───────────────────────────────────────────
    # SOT-223 with tab
    is_sot223 = (body_w > 3.0 or total == 4)

    if is_sot223:
        # SOT-223: 3 small leads on the right, 1 big tab on the left
        n_right = total - 1   # typically 3
        n_left  = 0           # tab handled separately
        _log(f"  SOT-223 mode: {n_right} leads + 1 tab")
    elif total == 3:
        # SOT-23-3 : 1 lead on left (pin 1), 2 leads on right (pins 2-3)
        n_left  = 1
        n_right = 2
    elif total == 5:
        # SOT-23-5 : 2 on left, 3 on right
        n_left  = 2
        n_right = 3
    else:
        # generic fallback
        n_right = (total + 1) // 2
        n_left  = total - n_right

    # ── lead geometry helpers ───────────────────────────────────────────────
    lead_thick = 0.15
    lead_w     = 0.4 if not is_sot223 else 0.7   # individual lead width
    foot_len   = 0.55

    half_body  = body_w / 2.0
    half_span  = afast / 2.0
    ext_len    = max(half_span - half_body, 0.1)

    def _make_gull_lead(cx, cy, side_sign, width):
        """Build a single gull-wing lead at (cx, cy).
        side_sign: -1 for left (−X), +1 for right (+X)."""
        # foot on PCB
        foot_cx = side_sign * (half_span - foot_len / 2.0)
        foot = (
            cq.Workplane("XY")
            .center(foot_cx, cy)
            .box(foot_len, width, lead_thick, centered=(True, True, False))
        )
        # horizontal extension
        horiz_cx = side_sign * (half_body + ext_len / 2.0)
        horiz = (
            cq.Workplane("XY")
            .center(horiz_cx, cy)
            .box(ext_len, width, lead_thick, centered=(True, True, False))
        )
        # vertical riser
        riser_h = body_h * 0.45
        riser_cx = side_sign * half_body
        riser = (
            cq.Workplane("XY")
            .center(riser_cx, cy)
            .box(lead_thick, width, riser_h, centered=(True, True, False))
        )
        return foot.union(horiz).union(riser)

    def _place_leads_on_side(n, side_sign, start_idx):
        if n <= 0:
            return start_idx
        span = (n - 1) * pitch
        y0   = -span / 2.0
        for i in range(n):
            cy = y0 + i * pitch
            lead = _make_gull_lead(0, cy, side_sign, lead_w)
            show_fn(lead,
                    name=f"{nome}_pin{start_idx + i}",
                    options={"color": lead_colour, "alpha": 0.95})
        return start_idx + n

    # right side (+X)
    idx = _place_leads_on_side(n_right, +1, 1)
    # left side  (−X)   – pins continue in counter-clockwise order
    idx = _place_leads_on_side(n_left, -1, idx)

    # ── SOT-223 tab (left side) ────────────────────────────────────────────
    if is_sot223:
        tab_w = body_l * 0.65       # wide tab
        tab_foot_len = 1.0
        tab_foot_cx  = -(half_span - tab_foot_len / 2.0)
        tab_foot = (
            cq.Workplane("XY")
            .center(tab_foot_cx, 0)
            .box(tab_foot_len, tab_w, lead_thick,
                 centered=(True, True, False))
        )
        tab_ext_cx = -(half_body + ext_len / 2.0)
        tab_horiz = (
            cq.Workplane("XY")
            .center(tab_ext_cx, 0)
            .box(ext_len, tab_w, lead_thick,
                 centered=(True, True, False))
        )
        tab_riser = (
            cq.Workplane("XY")
            .center(-half_body, 0)
            .box(lead_thick, tab_w, body_h * 0.45,
                 centered=(True, True, False))
        )
        tab_assy = tab_foot.union(tab_horiz).union(tab_riser)
        show_fn(tab_assy, name=f"{nome}_tab",
                options={"color": lead_colour, "alpha": 0.95})

    # ── pin-1 dot ───────────────────────────────────────────────────────────
    dot_r = 0.18
    dot_x = -(body_w / 2.0 - 0.35)
    dot_y = -(body_l / 2.0 - 0.35)
    dot = (
        cq.Workplane("XY")
        .transformed(offset=(dot_x, dot_y, body_h))
        .circle(dot_r)
        .extrude(0.02)
    )
    show_fn(dot, name=f"{nome}_pin1_dot",
            options={"color": dot_colour, "alpha": 0.95})

    _log("[3D] sot23 – done")


# ─────────────────────────────────────────────────────────────────────────────
# 4.  SSOP  (SSOP-20 and similar narrow-pitch gull-wing ICs)
# ─────────────────────────────────────────────────────────────────────────────

def _tmpl_ssop(dados, nome, show_fn, cq, _log):
    """
    3-D model for SSOP / TSSOP packages (e.g. SSOP-20).
    Rectangular body with gull-wing leads on two sides and pin-1 indent.
    """
    _log("[3D] ssop – start")

    corpo = dados.get("corpo", {})
    pinos = dados.get("pinos", {})

    body_w = float(corpo.get("largura", 5.3))        # X
    body_l = float(corpo.get("comprimento", 7.2))     # Y
    body_h = float(corpo.get("altura_3d", 1.75))

    total  = int(pinos.get("total", 20))
    pitch  = float(pinos.get("pitch", 0.635))
    afast  = float(corpo.get("afastamento_colunas", body_w + 2.0))

    body_colour = (30, 30, 30)
    lead_colour = (200, 180, 60)
    dot_colour  = (220, 220, 220)

    n_side = total // 2         # leads per side

    # ── body ────────────────────────────────────────────────────────────────
    body = (
        cq.Workplane("XY")
        .box(body_w, body_l, body_h, centered=(True, True, False))
    )
    try:
        fillet_r = min(0.2, body_w * 0.04, body_l * 0.04)
        body = body.edges("|Z").fillet(fillet_r)
    except Exception:
        pass

    show_fn(body, name=f"{nome}_body",
            options={"color": body_colour, "alpha": 0.95})
    _log(f"  body  {body_w:.2f} x {body_l:.2f} x {body_h:.2f}")
    _log(f"  {total} pins, pitch {pitch:.3f}, span {afast:.2f}")

    # ── lead dimensions ─────────────────────────────────────────────────────
    lead_thick = 0.15
    lead_w     = pitch * 0.55      # leave gap between leads
    foot_len   = 0.6               # PCB contact length

    half_body  = body_w / 2.0
    half_span  = afast / 2.0
    ext_len    = max(half_span - half_body, 0.1)

    riser_h = body_h * 0.50

    # ── lead span along Y ──────────────────────────────────────────────────
    span_y = (n_side - 1) * pitch
    y_start = -span_y / 2.0

    for side_sign, side_label in [(+1, "R"), (-1, "L")]:
        for i in range(n_side):
            cy = y_start + i * pitch

            # foot (on PCB surface)
            foot_cx = side_sign * (half_span - foot_len / 2.0)
            foot = (
                cq.Workplane("XY")
                .center(foot_cx, cy)
                .box(foot_len, lead_w, lead_thick,
                     centered=(True, True, False))
            )
            # horizontal extension (body edge → knee)
            horiz_cx = side_sign * (half_body + ext_len / 2.0)
            horiz = (
                cq.Workplane("XY")
                .center(horiz_cx, cy)
                .box(ext_len, lead_w, lead_thick,
                     centered=(True, True, False))
            )
            # vertical riser (knee → body mid-height)
            riser_cx = side_sign * half_body
            riser = (
                cq.Workplane("XY")
                .center(riser_cx, cy)
                .box(lead_thick, lead_w, riser_h,
                     centered=(True, True, False))
            )

            lead = foot.union(horiz).union(riser)

            # Pin numbering:  side R = pins 1…n_side,
            #                 side L = pins (n_side+1)…total  (counter-clockwise)
            if side_label == "R":
                pin_num = i + 1
            else:
                pin_num = total - i   # count backwards on left side

            show_fn(lead,
                    name=f"{nome}_pin{pin_num}",
                    options={"color": lead_colour, "alpha": 0.95})

    # ── pin-1 marker (circular indent on body top) ──────────────────────────
    indent_r = 0.3
    indent_x = body_w / 2.0 - 0.6
    indent_y = -(body_l / 2.0 - 0.6)
    indent = (
        cq.Workplane("XY")
        .transformed(offset=(indent_x, indent_y, body_h - 0.05))
        .circle(indent_r)
        .extrude(0.06)
    )
    try:
        indent = indent.edges().fillet(0.04)
    except Exception:
        pass

    # We subtract the indent from a tiny disc to show it as a depression
    # simpler approach: just show the disc in a lighter colour
    show_fn(indent, name=f"{nome}_pin1_mark",
            options={"color": dot_colour, "alpha": 0.95})

    _log("[3D] ssop – done")
