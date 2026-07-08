# =============================================================================
# _3d_templates_power.py
# Templates 3D para encapsulamentos de potência e CIs de alta densidade:
#   - DPAK / TO-252      (SMD power transistor / MOSFET)
#   - TO-220             (PTH power package)
#   - QFN                (Quad Flat No-lead)
#   - TQFP               (Thin Quad Flat Pack)
#
# Convenção:  def _tmpl_xxx(dados, nome, show_fn, cq, _log)
#   cq        — módulo cadquery já importado
#   show_fn   — show_object do CQ-Editor
#   dados     — dict completo do YAML
#   nome      — dados['nome']
#   _log(msg) — debug
# =============================================================================
import math as _math


def _safe_pinos(dados):
    """Extrai pinos info com fallback para formato custom (pads list).

    Quando padrao=custom, dados['pinos'] não existe.
    Tenta inferir total, pitch etc. do campo 'pads' (lista).
    """
    pinos = dados.get('pinos', {})
    if pinos:
        return pinos

    # Fallback: extrair de dados['pads'] (formato custom)
    pads_list = dados.get('pads', [])
    result = {
        'total': len(pads_list),
        'pitch': 0,
    }

    # Tentar inferir pitch das posições
    if len(pads_list) >= 2:
        xs = sorted(set(abs(float(p.get('x', 0))) for p in pads_list))
        ys = sorted(set(abs(float(p.get('y', 0))) for p in pads_list))
        if len(xs) > 1:
            diffs = [xs[i+1] - xs[i] for i in range(len(xs)-1)]
            result['pitch'] = min(diffs) if diffs else 2.54
        elif len(ys) > 1:
            diffs = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
            result['pitch'] = min(diffs) if diffs else 2.54

    # Tentar inferir tamanho de pad
    if pads_list:
        p0 = pads_list[0]
        result['tamanho_pad'] = {
            'largura': float(p0.get('largura', 1.0)),
            'altura': float(p0.get('altura', 1.0)),
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 1. DPAK / TO-252  —  SMD power transistor / MOSFET
# ─────────────────────────────────────────────────────────────────────────────
def _tmpl_dpak(dados, nome, show_fn, cq, _log):
    """Template 3D para DPAK (TO-252) — transistor/MOSFET de potência SMD.

    Corpo plástico grosso, aba metálica (heatsink) traseira e 3 leads
    gull-wing frontais (o pino central pode ser cortado em variantes de 2 pinos).
    """
    import math as _math

    # ── Dimensões do corpo ────────────────────────────────────────────────────
    corpo_w   = float(dados['corpo']['largura'])          # ~6.5 mm
    corpo_l   = float(dados['corpo']['comprimento'])      # ~6.1 mm
    corpo_h   = float(dados['corpo'].get('altura_3d', 2.3))
    pinos     = _safe_pinos(dados)
    pitch     = float(pinos.get('pitch', 2.28))            # ~2.28 mm
    total     = int(pinos.get('total', 3))                  # 3 (ou 2)

    # ── Corpo plástico (assenta sobre z=0) ────────────────────────────────────
    corpo = (cq.Workplane("XY")
             .box(corpo_w, corpo_l, corpo_h, centered=(True, True, False)))
    try:
        corpo = corpo.edges("|Z").fillet(0.25)
    except Exception:
        pass
    try:
        corpo = corpo.edges(">Z").chamfer(0.15)
    except Exception:
        pass

    show_fn(corpo, name=f"Corpo - {nome}",
            options={"color": (30, 30, 30), "alpha": 0.95})

    # ── Marcação pino 1 — pequeno ponto no canto frontal-esquerdo ─────────────
    try:
        dot_r = 0.35
        dot = (cq.Workplane("XY")
               .workplane(offset=corpo_h)
               .moveTo(-corpo_w / 2 + 1.0, -corpo_l / 2 + 1.0)
               .circle(dot_r)
               .extrude(0.05))
        show_fn(dot, name=f"Pin1Mark - {nome}",
                options={"color": (200, 200, 200), "alpha": 0.95})
    except Exception:
        pass

    # ── Aba metálica (heatsink) — traseira ────────────────────────────────────
    tab_w  = corpo_w * 0.80          # largura da aba
    tab_l  = 1.0                     # extensão para trás do corpo
    tab_t  = 0.50                    # espessura
    tab_in = corpo_l * 0.35          # parte que fica sob o corpo

    # Parte exposta (para trás)
    tab_ext = (cq.Workplane("XY")
               .box(tab_w, tab_l, tab_t, centered=(True, True, False))
               .translate((0, corpo_l / 2 + tab_l / 2, 0)))
    # Parte interna (sob o corpo)
    tab_int = (cq.Workplane("XY")
               .box(tab_w, tab_in, tab_t, centered=(True, True, False))
               .translate((0, corpo_l / 2 - tab_in / 2, 0)))
    try:
        tab = tab_ext.union(tab_int)
    except Exception:
        tab = tab_ext

    show_fn(tab, name=f"Tab - {nome}",
            options={"color": (180, 180, 190), "alpha": 0.95})

    # ── Leads gull-wing (frontais, saem de -Y) ────────────────────────────────
    lead_t   = 0.20      # espessura do lead
    lead_w   = 0.60      # largura de cada lead
    foot_l   = 0.80      # comprimento da parte horizontal (pé)
    rise_h   = 0.45      # altura da subida até o corpo
    exit_l   = 0.40      # comprimento da extensão saindo do corpo

    def _make_dpak_lead(x_pos):
        """Cria um lead gull-wing individual na posição x dada."""
        # Pé horizontal (toca a PCB, z=0)
        foot = (cq.Workplane("XY")
                .box(lead_w, foot_l, lead_t, centered=(True, True, False))
                .translate((x_pos, -corpo_l / 2 - foot_l / 2, 0)))
        # Parte vertical (sobe do pé até o corpo)
        vert = (cq.Workplane("XY")
                .box(lead_w, lead_t, rise_h, centered=(True, True, False))
                .translate((x_pos, -corpo_l / 2, 0)))
        # Extensão horizontal entrando no corpo
        ext = (cq.Workplane("XY")
               .box(lead_w, exit_l, lead_t, centered=(True, True, False))
               .translate((x_pos, -corpo_l / 2 + exit_l / 2, rise_h)))
        try:
            lead = foot.union(vert).union(ext)
        except Exception:
            lead = foot
        return lead

    # Posicionar leads conforme total de pinos
    if total >= 3:
        positions = [i * pitch - (total - 1) * pitch / 2 for i in range(total)]
    else:
        # Variante de 2 pinos (sem central)
        positions = [-pitch, pitch]

    for idx, xp in enumerate(positions):
        lead = _make_dpak_lead(xp)
        show_fn(lead, name=f"Lead_{idx + 1} - {nome}",
                options={"color": (200, 180, 60), "alpha": 0.95})

    _log(f"Template DPAK OK  corpo={corpo_w}x{corpo_l}x{corpo_h}mm  "
         f"pinos={total}  pitch={pitch}mm")


# ─────────────────────────────────────────────────────────────────────────────
# 2. TO-220  —  PTH power package
# ─────────────────────────────────────────────────────────────────────────────
def _tmpl_to220(dados, nome, show_fn, cq, _log):
    """Template 3D para TO-220 — encapsulamento de potência PTH.

    Corpo plástico retangular alto, aba metálica com furo de montagem
    estendendo-se acima do corpo, e 3 leads PTH retos.
    """
    import math as _math

    # ── Dimensões ─────────────────────────────────────────────────────────────
    corpo_w = float(dados['corpo'].get('largura', 10.0))
    corpo_l = float(dados['corpo'].get('comprimento', 4.5))   # profundidade (Y)
    corpo_h = float(dados['corpo'].get('altura_3d', 10.0))
    pinos   = _safe_pinos(dados)
    pitch   = float(pinos.get('pitch', 2.54))                   # ~2.54 mm
    total   = int(pinos.get('total', 3))                        # geralmente 3
    pcb_t   = float(dados.get('pcb', {}).get('espessura', 1.6))

    # ── Corpo plástico (assenta sobre a PCB) ──────────────────────────────────
    corpo = (cq.Workplane("XY")
             .workplane(offset=pcb_t)
             .box(corpo_w, corpo_l, corpo_h, centered=(True, True, False)))
    try:
        corpo = corpo.edges("|Z").fillet(0.3)
    except Exception:
        pass
    try:
        corpo = corpo.edges(">Z").chamfer(0.2)
    except Exception:
        pass

    show_fn(corpo, name=f"Corpo - {nome}",
            options={"color": (30, 30, 30), "alpha": 0.95})

    # ── Aba metálica (heatsink) — se estende para cima do corpo ───────────────
    tab_w  = corpo_w                 # mesma largura do corpo
    tab_h  = 5.0                     # extensão acima do corpo
    tab_t  = 0.60                    # espessura da aba
    hole_d = 3.5                     # diâmetro do furo de montagem

    tab = (cq.Workplane("XY")
           .workplane(offset=pcb_t + corpo_h)
           .box(tab_w, tab_t, tab_h, centered=(True, True, False)))

    # Furo de montagem no centro da aba
    try:
        tab = (tab.faces(">Z")
               .workplane(offset=-tab_h / 2)
               .hole(hole_d))
    except Exception:
        pass

    # Parte da aba que fica atrás do corpo (cobre a face traseira)
    tab_back = (cq.Workplane("XY")
                .workplane(offset=pcb_t)
                .box(tab_w, tab_t, corpo_h, centered=(True, True, False))
                .translate((0, -corpo_l / 2 + tab_t / 2, 0)))

    try:
        tab_full = tab.union(tab_back)
    except Exception:
        tab_full = tab

    show_fn(tab_full, name=f"Tab - {nome}",
            options={"color": (180, 180, 190), "alpha": 0.95})

    # ── Leads PTH — fios retos verticais ──────────────────────────────────────
    lead_r   = 0.40      # raio do lead
    pin_below = pcb_t    # parte abaixo da PCB (desce até z=0)
    pin_above = 3.5      # parte acima da PCB (entra no corpo)
    lead_len  = pin_below + pin_above

    for i in range(total):
        x = -(total - 1) * pitch / 2 + i * pitch
        lead = (cq.Workplane("XY")
                .circle(lead_r)
                .extrude(lead_len)
                .translate((x, corpo_l / 4, -pin_below + pcb_t)))

        show_fn(lead, name=f"Lead_{i + 1} - {nome}",
                options={"color": (200, 180, 60), "alpha": 0.95})

    # ── Marcação pino 1 — entalhe na base ─────────────────────────────────────
    try:
        notch = (cq.Workplane("XY")
                 .workplane(offset=pcb_t + corpo_h - 0.1)
                 .moveTo(-corpo_w / 2 + 1.2, corpo_l / 2 - 0.5)
                 .circle(0.4)
                 .extrude(0.15))
        show_fn(notch, name=f"Pin1Mark - {nome}",
                options={"color": (180, 180, 180), "alpha": 0.95})
    except Exception:
        pass

    _log(f"Template TO-220 OK  corpo={corpo_w}x{corpo_l}x{corpo_h}mm  "
         f"pinos={total}  pitch={pitch}mm  pcb_t={pcb_t}mm")


# ─────────────────────────────────────────────────────────────────────────────
# 3. QFN  —  Quad Flat No-lead
# ─────────────────────────────────────────────────────────────────────────────
def _tmpl_qfn(dados, nome, show_fn, cq, _log):
    """Template 3D para QFN (Quad Flat No-lead).

    Corpo fino quadrado/retangular com pads metálicos planos na face
    inferior (sem leads gull-wing), pad térmico exposto central e
    marcação de pino 1.
    """
    import math as _math

    # ── Dimensões do corpo ────────────────────────────────────────────────────
    corpo_w = float(dados['corpo']['largura'])
    corpo_l = float(dados['corpo'].get('comprimento', corpo_w))  # quadrado se omitido
    corpo_h = float(dados['corpo'].get('altura_3d', 0.85))
    pinos   = _safe_pinos(dados)
    total   = int(pinos.get('total', 16))
    pitch   = float(pinos.get('pitch', 0.5))
    pps     = int(pinos.get('por_lado', total // 4))            # pinos por lado

    # ── Corpo plástico (assenta sobre z=0) ────────────────────────────────────
    corpo = (cq.Workplane("XY")
             .box(corpo_w, corpo_l, corpo_h, centered=(True, True, False)))
    try:
        corpo = corpo.edges("|Z").fillet(0.10)
    except Exception:
        pass

    show_fn(corpo, name=f"Corpo - {nome}",
            options={"color": (40, 40, 45), "alpha": 0.95})

    # ── Marcação pino 1 — ponto circular no topo, canto (-X, -Y) ─────────────
    try:
        dot_r = min(0.30, corpo_w * 0.04)
        dot = (cq.Workplane("XY")
               .workplane(offset=corpo_h)
               .moveTo(-corpo_w / 2 + 0.7, -corpo_l / 2 + 0.7)
               .circle(dot_r)
               .extrude(0.02))
        show_fn(dot, name=f"Pin1Dot - {nome}",
                options={"color": (220, 220, 220), "alpha": 0.99})
    except Exception:
        pass

    # ── Dimensões dos pads periféricos ────────────────────────────────────────
    pad_w   = 0.25       # largura do pad (perpendicular à borda)
    pad_l   = 0.60       # comprimento do pad (paralelo à borda)
    pad_t   = 0.05       # espessura (na face inferior)
    pad_ext = 0.10       # quanto se estende para fora do corpo
    pad_color = (200, 200, 210)

    def _draw_pads_side(side, count, pin_start):
        """Desenha pads para um lado do QFN.
        side: 'bottom'(-Y), 'right'(+X), 'top'(+Y), 'left'(-X)
        """
        for i in range(count):
            idx = i - (count - 1) / 2.0
            pin_num = pin_start + i

            if side == 'bottom':
                # Pads ao longo de -Y
                x = idx * pitch
                y = -corpo_l / 2 - pad_ext + pad_w / 2
                pw, pl = pad_w, pad_l
                pad = (cq.Workplane("XY")
                       .box(pl, pw, pad_t, centered=(True, True, False))
                       .translate((x, y, -pad_t)))
            elif side == 'right':
                # Pads ao longo de +X
                x = corpo_w / 2 + pad_ext - pad_w / 2
                y = idx * pitch
                pw, pl = pad_l, pad_w
                pad = (cq.Workplane("XY")
                       .box(pw, pl, pad_t, centered=(True, True, False))
                       .translate((x, y, -pad_t)))
            elif side == 'top':
                # Pads ao longo de +Y  (numeração espelhada)
                x = -idx * pitch
                y = corpo_l / 2 + pad_ext - pad_w / 2
                pw, pl = pad_w, pad_l
                pad = (cq.Workplane("XY")
                       .box(pl, pw, pad_t, centered=(True, True, False))
                       .translate((x, y, -pad_t)))
            else:  # left
                # Pads ao longo de -X  (numeração espelhada)
                x = -corpo_w / 2 - pad_ext + pad_w / 2
                y = -idx * pitch
                pw, pl = pad_l, pad_w
                pad = (cq.Workplane("XY")
                       .box(pw, pl, pad_t, centered=(True, True, False))
                       .translate((x, y, -pad_t)))

            show_fn(pad, name=f"Pad_{pin_num} - {nome}",
                    options={"color": pad_color, "alpha": 0.99})

    # Distribuir pinos: bottom → right → top → left
    _draw_pads_side('bottom', pps, 1)
    _draw_pads_side('right',  pps, pps + 1)
    _draw_pads_side('top',    pps, 2 * pps + 1)
    _draw_pads_side('left',   pps, 3 * pps + 1)

    # ── Pad térmico exposto (centro, face inferior) ───────────────────────────
    tp = dados.get('thermal_pad', {})
    tp_w = float(tp.get('largura', corpo_w * 0.60))
    tp_l = float(tp.get('altura', tp.get('comprimento', corpo_l * 0.60)))
    tp_t = 0.05   # espessura do pad térmico visível

    epad = (cq.Workplane("XY")
            .box(tp_w, tp_l, tp_t, centered=(True, True, False))
            .translate((0, 0, -tp_t)))

    show_fn(epad, name=f"ThermalPad - {nome}",
            options={"color": (184, 141, 20), "alpha": 0.99})

    _log(f"Template QFN OK  corpo={corpo_w}x{corpo_l}x{corpo_h}mm  "
         f"pinos={total} ({pps}/lado)  pitch={pitch}mm")


# ─────────────────────────────────────────────────────────────────────────────
# 4. TQFP  —  Thin Quad Flat Pack
# ─────────────────────────────────────────────────────────────────────────────
def _tmpl_tqfp(dados, nome, show_fn, cq, _log):
    """Template 3D para TQFP (Thin Quad Flat Pack).

    Corpo plástico fino quadrado com chanfro no canto do pino 1 e leads
    gull-wing nos 4 lados (pé horizontal + subida vertical).
    """
    import math as _math

    # ── Dimensões ─────────────────────────────────────────────────────────────
    corpo_w = float(dados['corpo']['largura'])
    corpo_l = float(dados['corpo'].get('comprimento', corpo_w))
    corpo_h = float(dados['corpo'].get('altura_3d', 1.2))
    pinos   = _safe_pinos(dados)
    total   = int(pinos.get('total', 32))
    pitch   = float(pinos.get('pitch', 0.8))                    # ~0.8 mm
    pps     = int(pinos.get('por_lado', total // 4))            # pinos por lado

    # ── Corpo plástico ────────────────────────────────────────────────────────
    # Chanfro no canto pino 1 (-X, -Y): corte diagonal
    chamfer_size = min(0.8, corpo_w * 0.08)

    corpo = (cq.Workplane("XY")
             .box(corpo_w, corpo_l, corpo_h, centered=(True, True, False)))

    # Chanfro de pino 1 no canto (-X, -Y): corta um cubo diagonal
    try:
        # Cubo de corte rotacionado 45° no canto
        cut_size = chamfer_size * _math.sqrt(2)
        cut_block = (cq.Workplane("XY")
                     .box(cut_size, cut_size, corpo_h + 1, centered=(True, True, True))
                     .rotate((0, 0, 0), (0, 0, 1), 45)
                     .translate((-corpo_w / 2, -corpo_l / 2, corpo_h / 2)))
        corpo = corpo.cut(cut_block)
    except Exception:
        pass

    # Filetes leves nas arestas verticais
    try:
        corpo = corpo.edges("|Z").fillet(0.12)
    except Exception:
        pass

    show_fn(corpo, name=f"Corpo - {nome}",
            options={"color": (30, 30, 30), "alpha": 0.95})

    # ── Marcação pino 1 — ponto no topo ───────────────────────────────────────
    try:
        dot_r = min(0.25, corpo_w * 0.03)
        dot = (cq.Workplane("XY")
               .workplane(offset=corpo_h)
               .moveTo(-corpo_w / 2 + 1.0, -corpo_l / 2 + 1.0)
               .circle(dot_r)
               .extrude(0.02))
        show_fn(dot, name=f"Pin1Dot - {nome}",
                options={"color": (200, 200, 200), "alpha": 0.99})
    except Exception:
        pass

    # ── Leads gull-wing ───────────────────────────────────────────────────────
    lead_t   = 0.15       # espessura do lead
    lead_w   = max(0.18, pitch * 0.45)   # largura do lead (< pitch)
    foot_l   = 0.50       # comprimento do pé horizontal
    rise_h   = 0.30       # altura da subida vertical
    stub_l   = 0.25       # extensão que entra no corpo

    lead_color = (200, 180, 60)

    def _make_gullwing(x_center, y_center, angle_deg):
        """Cria um lead gull-wing orientado no ângulo dado.
        angle_deg: 0=saindo para -Y, 90=saindo para +X, 180=+Y, 270=-X
        """
        # Construir o lead orientado saindo para -Y e depois rotacionar
        # Pé horizontal (toca a PCB, z=0)
        foot = (cq.Workplane("XY")
                .box(lead_w, foot_l, lead_t, centered=(True, True, False))
                .translate((0, -foot_l / 2, 0)))
        # Subida vertical
        vert = (cq.Workplane("XY")
                .box(lead_w, lead_t, rise_h, centered=(True, True, False))
                .translate((0, 0, 0)))
        # Stub horizontal (entra no corpo)
        stub = (cq.Workplane("XY")
                .box(lead_w, stub_l, lead_t, centered=(True, True, False))
                .translate((0, stub_l / 2, rise_h)))

        try:
            lead = foot.union(vert).union(stub)
        except Exception:
            lead = foot

        # Rotacionar e posicionar
        lead = (lead.rotate((0, 0, 0), (0, 0, 1), angle_deg)
                .translate((x_center, y_center, 0)))
        return lead

    def _draw_leads_side(side, count, pin_start):
        """Gera leads gull-wing para um lado do TQFP."""
        for i in range(count):
            idx = i - (count - 1) / 2.0
            pin_num = pin_start + i

            if side == 'bottom':
                # Leads saindo para -Y
                x = idx * pitch
                y = -corpo_l / 2 - foot_l / 2
                lead = _make_gullwing(x, y, 0)
            elif side == 'right':
                # Leads saindo para +X
                x = corpo_w / 2 + foot_l / 2
                y = idx * pitch
                lead = _make_gullwing(x, y, -90)
            elif side == 'top':
                # Leads saindo para +Y (numeração espelhada)
                x = -idx * pitch
                y = corpo_l / 2 + foot_l / 2
                lead = _make_gullwing(x, y, 180)
            else:  # left
                # Leads saindo para -X (numeração espelhada)
                x = -corpo_w / 2 - foot_l / 2
                y = -idx * pitch
                lead = _make_gullwing(x, y, 90)

            show_fn(lead, name=f"Lead_{pin_num} - {nome}",
                    options={"color": lead_color, "alpha": 0.95})

    # Distribuir leads: bottom → right → top → left
    _draw_leads_side('bottom', pps, 1)
    _draw_leads_side('right',  pps, pps + 1)
    _draw_leads_side('top',    pps, 2 * pps + 1)
    _draw_leads_side('left',   pps, 3 * pps + 1)

    total_rendered = pps * 4
    _log(f"Template TQFP OK  corpo={corpo_w}x{corpo_l}x{corpo_h}mm  "
         f"pinos={total_rendered} ({pps}/lado)  pitch={pitch}mm")
