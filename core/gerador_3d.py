# =============================================================================
# gerador_3d.py
# Motor 3D headless — gera modelos .step sem necessidade de CQ-Editor.
#
# Uso:
#   from gerador_3d import gerar_3d_step, listar_tipos_3d
#   gerar_3d_step(dados_dict, "saida/componente.step")
#
# Todas as funções de template são importadas dos módulos existentes ou
# definidas aqui (extraídas do gerador_universal.py original).
# =============================================================================

import logging
import os
import sys
import math

log = logging.getLogger(__name__)

# Garantir imports do core/
_CORE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_CORE)
for _p in [_PROJ, _CORE]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import cadquery as cq
    _HAS_CQ = True
except ImportError:
    _HAS_CQ = False


# =============================================================================
# Templates 3D built-in (extraídos de gerador_universal.py)
# =============================================================================

def _tmpl_axial_pth(dados, nome, show_fn, cq, _log):
    """Template 3D para componentes axiais PTH (diodo, resistor).
    Leads com dobra real: segmento horizontal + arco de 90° (8 cilindros) + vertical.
    """
    import math as _math

    espacamento = float(dados['pinos']['espacamento'])
    corpo_comp  = float(dados['corpo']['comprimento'])
    corpo_diam  = float(dados['corpo']['diametro'])
    furo_diam   = float(dados['pinos']['diametro_furo'])

    corpo_r  = corpo_diam / 2
    lead_r   = max(0.1, (furo_diam * 0.85) / 2)
    standoff = 1.0
    pcb_t    = float(dados.get('pcb', {}).get('espessura', 1.6))
    body_z   = standoff + corpo_r
    bend_r   = max(lead_r * 2.5, min(body_z * 0.4, 1.0))
    N_SEG    = 8

    corpo = (cq.Workplane("XY").cylinder(corpo_comp, corpo_r)
             .rotate((0,0,0),(0,1,0), 90).translate((0, 0, body_z)))

    _c = (210, 185, 80)

    def _make_bent_lead(x_body_end, x_pin):
        dx = 1 if x_pin > x_body_end else -1
        cx = x_pin - dx * bend_r
        cz = body_z - bend_r

        parts = []

        h_len = abs(cx - x_body_end)
        if h_len > 1e-3:
            parts.append(
                cq.Workplane("XY").cylinder(h_len, lead_r)
                .rotate((0,0,0),(0,1,0), 90)
                .translate(((x_body_end + cx) / 2, 0, body_z))
            )

        for i in range(N_SEG):
            a0 = _math.pi/2 + (-dx) * _math.pi/2 * (i     / N_SEG)
            a1 = _math.pi/2 + (-dx) * _math.pi/2 * ((i+1) / N_SEG)
            x0s = cx + bend_r * _math.cos(a0)
            z0s = cz + bend_r * _math.sin(a0)
            x1s = cx + bend_r * _math.cos(a1)
            z1s = cz + bend_r * _math.sin(a1)
            seg_len = _math.hypot(x1s - x0s, z1s - z0s)
            if seg_len < 1e-6:
                continue
            dxs = (x1s - x0s) / seg_len
            dzs = (z1s - z0s) / seg_len
            ang = _math.degrees(_math.atan2(dxs, dzs))
            try:
                seg = (cq.Workplane("XY").cylinder(seg_len, lead_r)
                       .rotate((0,0,0),(0,1,0), ang)
                       .translate(((x0s+x1s)/2, 0, (z0s+z1s)/2)))
                parts.append(seg)
            except Exception as e:
                log.debug('3D detail skipped: %s', e)

        v_len = cz - (-pcb_t)
        if v_len > 1e-3:
            parts.append(
                cq.Workplane("XY").circle(lead_r).extrude(v_len)
                .translate((x_pin, 0, -pcb_t))
            )

        if not parts:
            return cq.Workplane("XY").sphere(lead_r)
        result = parts[0]
        for p in parts[1:]:
            try:
                result = result.union(p)
            except Exception as e:
                log.debug('3D detail skipped: %s', e)
        return result

    lead_a = _make_bent_lead(-corpo_comp/2, -espacamento/2)
    lead_c = _make_bent_lead( corpo_comp/2,  espacamento/2)

    pcb = (cq.Workplane("XY")
           .box(espacamento+6, corpo_diam+6, pcb_t, centered=(True,True,False))
           .translate((0, 0, -pcb_t)))

    show_fn(corpo,  name=f"Corpo - {nome}",  options={"color": (30, 30, 30), "alpha": 0.95})
    show_fn(lead_a, name=f"LeadA - {nome}",  options={"color": _c,           "alpha": 0.95})
    show_fn(lead_c, name=f"LeadC - {nome}",  options={"color": _c,           "alpha": 0.95})
    show_fn(pcb,    name=f"PCB   - {nome}",  options={"color": (34,100,34),  "alpha": 0.90})

    try:
        endcap_a = cq.Workplane("XY").sphere(corpo_r * 0.6).translate((-corpo_comp/2, 0, body_z))
        endcap_c = cq.Workplane("XY").sphere(corpo_r * 0.6).translate(( corpo_comp/2, 0, body_z))
        show_fn(endcap_a, name=f'EndA - {nome}', options={'color': (30,30,30), 'alpha': 0.95})
        show_fn(endcap_c, name=f'EndC - {nome}', options={'color': (30,30,30), 'alpha': 0.95})
    except Exception as e:
        log.debug('3D detail skipped: %s', e)

    if dados.get('tipo') == 'diodo_pth':
        try:
            band_w = min(corpo_r * 0.55, 0.85)
            band = (cq.Workplane("XY").cylinder(band_w, corpo_r + 0.08)
                    .rotate((0,0,0),(0,1,0), 90)
                    .translate((corpo_comp/2 - band_w/2, 0, body_z)))
            show_fn(band, name=f"CatodoBand - {nome}",
                    options={"color": (210, 210, 210), "alpha": 0.99})
        except Exception as e:
            log.debug('3D detail skipped: %s', e)

    _log(f"Template axial PTH OK  esp={espacamento}mm  corpo={corpo_comp}x{corpo_diam}mm")


def _tmpl_resistor_pth(dados, nome, show_fn, cq, _log):
    """Template 3D para resistor PTH."""
    _tmpl_axial_pth(dados, nome, show_fn, cq, _log)
    _log('Template resistor_pth OK')


def _tmpl_castellated(dados, nome, show_fn, cq, _log):
    """Template 3D para módulos SMD com furos castelados."""
    pcb_w = float(dados['pcb']['largura'])
    pcb_h = float(dados['pcb']['altura'])
    pcb_t = float(dados['pcb']['espessura'])

    pcb = cq.Workplane("XY").box(pcb_w, pcb_h, pcb_t, centered=(True, True, False))
    show_fn(pcb, name=f"PCB - {nome}", options={"color": (34, 139, 34), "alpha": 0.95})

    if 'shield_metalico' in dados and dados['shield_metalico']:
        sh = dados['shield_metalico']
        sh_w = float(sh['largura'])
        sh_h = float(sh['altura'])
        sh_t = float(sh['espessura'])
        shield = (cq.Workplane("XY").workplane(offset=pcb_t)
                  .box(sh_w, sh_h, sh_t, centered=(True, True, False)))
        show_fn(shield, name=f"Shield - {nome}", options={"color": (180, 180, 190), "alpha": 0.85})

    pad_color = (184, 141, 20)
    from geometria_pads import calcular_pads
    pads = calcular_pads(dados)

    pad_vis_t  = 0.15
    cast_depth = 0.60
    wrap_frac  = 0.30
    wrap_h     = pcb_t * wrap_frac
    wrap_t     = 0.12

    def _draw_pad_v(x_edge, y, pw, ph, num):
        depth = cast_depth
        sign = 1.0 if x_edge < 0 else -1.0
        try:
            bottom = (cq.Workplane("XY")
                      .box(depth, ph, pad_vis_t, centered=(True, True, False))
                      .translate((x_edge + sign * depth / 2, y, -pad_vis_t)))
            side = (cq.Workplane("XY")
                    .box(wrap_t, ph, wrap_h, centered=(True, True, False))
                    .translate((x_edge + sign * wrap_t / 2, y, 0)))
            comp = cq.Compound.makeCompound([bottom.val(), side.val()])
            show_fn(comp, name=f"Pad{num} - {nome}", options={"color": pad_color, "alpha": 0.99})
        except Exception as e:
            log.debug('3D detail skipped: %s', e)

    def _draw_pad_h(x, y_edge, pw, ph, num):
        depth = cast_depth
        sign = 1.0 if y_edge < 0 else -1.0
        try:
            bottom = (cq.Workplane("XY")
                      .box(ph, depth, pad_vis_t, centered=(True, True, False))
                      .translate((x, y_edge + sign * depth / 2, -pad_vis_t)))
            side = (cq.Workplane("XY")
                    .box(ph, wrap_t, wrap_h, centered=(True, True, False))
                    .translate((x, y_edge + sign * wrap_t / 2, 0)))
            comp = cq.Compound.makeCompound([bottom.val(), side.val()])
            show_fn(comp, name=f"Pad{num} - {nome}", options={"color": pad_color, "alpha": 0.99})
        except Exception as e:
            log.debug('3D detail skipped: %s', e)

    for pad in pads:
        num = pad.num
        if pad.horizontal:
            _draw_pad_h(pad.x, pad.y, pad.w, pad.h, num)
        else:
            _draw_pad_v(pad.x, pad.y, pad.w, pad.h, num)

    n_esq  = sum(1 for p in pads if p.lado == 'esquerdo')
    n_base = sum(1 for p in pads if p.lado == 'base')
    n_dir  = sum(1 for p in pads if p.lado == 'direito')
    n_topo = sum(1 for p in pads if p.lado == 'topo')
    _log(f"Template castellated OK  PCB={pcb_w}x{pcb_h}mm  "
         f"pads E={n_esq} B={n_base} D={n_dir} T={n_topo}")


def _tmpl_ci_dip(dados, nome, show_fn, cq, _log):
    """Template 3D para CI DIP dual in-line."""
    pitch       = float(dados['pinos']['pitch'])
    total       = int(dados['pinos']['total'])
    afastamento = float(dados['corpo']['afastamento_colunas'])
    largura     = float(dados['corpo']['largura'])
    comp        = float(dados['corpo']['comprimento'])
    pcb_t   = float(dados.get('pcb', {}).get('espessura', 1.6))
    pin_h   = 3.5
    corpo_h = 4.5

    corpo = (cq.Workplane("XY")
             .workplane(offset=pcb_t)
             .box(largura, comp, corpo_h, centered=(True, True, False)))
    try:
        corpo = corpo.edges("|Z").fillet(0.3).edges(">Z").chamfer(0.2)
    except Exception as e:
        log.debug('3D detail skipped: %s', e)
    show_fn(corpo, name=f'Corpo - {nome}', options={'color': (30, 30, 30), 'alpha': 0.95})

    lead_r = 0.25
    meio   = total // 2
    for i in range(meio):
        y = -(meio - 1) * pitch / 2 + i * pitch
        for side in [-1, 1]:
            x     = side * afastamento / 2
            perna = (cq.Workplane("XY")
                     .circle(lead_r)
                     .extrude(pcb_t + pin_h)
                     .translate((x, y, -pcb_t)))
            label = 'L' if side < 0 else 'R'
            show_fn(perna, name=f'Lead_{i+1}_{label} - {nome}',
                    options={'color': (200, 180, 60)})

    _log(f'Template DIP OK: {total} pinos, pitch={pitch}mm')


def _tmpl_conector_pth(dados, nome, show_fn, cq, _log):
    """Template 3D para conector PTH de 1 fileira."""
    total     = int(dados['pinos']['total'])
    pitch     = float(dados['pinos']['pitch'])
    furo_diam = float(dados['pinos']['diametro_furo'])
    pin_h     = 6.0
    corpo_h   = 8.5
    corpo_w   = pitch * 0.85
    pcb_t     = float(dados.get('pcb', {}).get('espessura', 1.6))
    lead_r    = max(0.15, furo_diam * 0.4)

    for i in range(total):
        x = -(total - 1) * pitch / 2 + i * pitch
        bloco = (cq.Workplane("XY")
                 .workplane(offset=pcb_t)
                 .box(corpo_w, corpo_w, corpo_h, centered=(True, True, False))
                 .translate((x, 0, 0)))
        try:
            bloco = bloco.edges(">Z").chamfer(0.15)
        except Exception as e:
            log.debug('3D detail skipped: %s', e)
        show_fn(bloco, name=f'Bloco_{i+1} - {nome}', options={'color': (20, 20, 20)})

        pino = (cq.Workplane("XY")
                .circle(lead_r)
                .extrude(pcb_t + corpo_h + pin_h)
                .translate((x, 0, -pcb_t)))
        show_fn(pino, name=f'Pin_{i+1} - {nome}', options={'color': (200, 180, 60)})

    _log(f'Template conector PTH OK: {total} pinos')


def _tmpl_ci_soic(dados, nome, show_fn, cq, _log):
    """Template 3D para CI SOIC — corpo plano, leads gull-wing SMD."""
    pitch       = float(dados['pinos']['pitch'])
    total       = int(dados['pinos']['total'])
    afastamento = float(dados['corpo']['afastamento_colunas'])
    largura     = float(dados['corpo']['largura'])
    comp        = float(dados['corpo']['comprimento'])
    pad_w       = float(dados['pinos']['tamanho_pad']['largura'])
    corpo_h     = 1.5
    lead_t      = 0.18
    lead_h      = 0.35

    corpo = (cq.Workplane("XY")
             .box(largura, comp, corpo_h, centered=(True, True, False)))
    try:
        corpo = corpo.edges("|Z").fillet(0.15)
    except Exception as e:
        log.debug('3D detail skipped: %s', e)
    show_fn(corpo, name=f'Corpo - {nome}', options={'color': (30, 30, 30), 'alpha': 0.95})

    meio = total // 2
    for i in range(meio):
        y = -(meio - 1) * pitch / 2 + i * pitch
        for side in [-1, 1]:
            lead_reach = afastamento / 2 - largura / 2
            lx = side * (largura / 2 + lead_reach / 2)
            lead_h_shape = (cq.Workplane("XY")
                            .box(lead_reach, lead_t, lead_t, centered=(True, True, False))
                            .translate((lx, y, 0)))
            lead_v_shape = (cq.Workplane("XY")
                            .box(lead_t, lead_t, lead_h, centered=(True, True, False))
                            .translate((side * largura / 2, y, 0)))
            label = 'L' if side < 0 else 'R'
            show_fn(lead_h_shape, name=f'LeadH_{i+1}_{label} - {nome}',
                    options={'color': (200, 180, 60)})
            show_fn(lead_v_shape, name=f'LeadV_{i+1}_{label} - {nome}',
                    options={'color': (200, 180, 60)})

    _log(f'Template SOIC OK: {total} pinos, pitch={pitch}mm')


def _tmpl_led_pth(dados, nome, show_fn, cq, _log):
    """Template 3D para LED PTH — cilindro + dome translúcida."""
    diam        = float(dados['corpo']['diametro'])
    altura      = float(dados['corpo']['altura'])
    espacamento = float(dados['pinos']['espacamento'])
    furo_diam   = float(dados['pinos']['diametro_furo'])
    r           = diam / 2
    pcb_t       = float(dados.get('pcb', {}).get('espessura', 1.6))
    lead_r      = max(0.1, furo_diam * 0.4)
    standoff    = 1.0
    corpo_h     = altura - r

    corpo = (cq.Workplane("XY").cylinder(corpo_h, r)
             .translate((0, 0, pcb_t + standoff + corpo_h / 2)))
    dome = (cq.Workplane("XY").sphere(r)
            .translate((0, 0, pcb_t + standoff + corpo_h)))
    leg_len = pcb_t + standoff + 2
    perna_a = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
               .translate((-espacamento/2, 0, -pcb_t)))
    perna_k = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
               .translate(( espacamento/2, 0, -pcb_t)))

    show_fn(corpo,   name=f'Corpo - {nome}',      options={'color': (200, 40, 40),  'alpha': 0.85})
    show_fn(dome,    name=f'Dome - {nome}',       options={'color': (255, 80, 80),  'alpha': 0.5})
    show_fn(perna_a, name=f'AnodoLead - {nome}',  options={'color': (210, 185, 80)})
    show_fn(perna_k, name=f'CatodoLead - {nome}', options={'color': (210, 185, 80)})
    _log(f'Template LED PTH OK  d={diam}mm  h={altura}mm')


def _tmpl_capacitor_pth(dados, nome, show_fn, cq, _log):
    """Template 3D para capacitor eletrolítico PTH radial."""
    diam        = float(dados['corpo']['diametro'])
    altura      = float(dados['corpo']['altura'])
    espacamento = float(dados['pinos']['espacamento'])
    furo_diam   = float(dados['pinos']['diametro_furo'])
    r           = diam / 2
    pcb_t       = float(dados.get('pcb', {}).get('espessura', 1.6))
    lead_r      = max(0.1, furo_diam * 0.4)

    corpo = (cq.Workplane("XY").cylinder(altura, r)
             .translate((0, 0, pcb_t + altura / 2)))
    faixa_h = 1.8
    faixa = (cq.Workplane("XY").cylinder(faixa_h, r + 0.02)
             .translate((0, 0, pcb_t + altura - faixa_h / 2)))
    tampa = (cq.Workplane("XY").cylinder(0.4, r * 0.85)
             .translate((0, 0, pcb_t + altura + 0.2)))
    leg_len = pcb_t + 2
    lead_pos = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
                .translate((-espacamento/2, 0, -pcb_t)))
    lead_neg = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
                .translate(( espacamento/2, 0, -pcb_t)))

    show_fn(corpo,    name=f'Corpo - {nome}',   options={'color': (20, 70, 180),   'alpha': 0.95})
    show_fn(faixa,    name=f'Faixa - {nome}',   options={'color': (200, 200, 200), 'alpha': 0.90})
    show_fn(tampa,    name=f'Tampa - {nome}',   options={'color': (150, 150, 160), 'alpha': 0.95})
    show_fn(lead_pos, name=f'LeadPos - {nome}', options={'color': (210, 185, 80)})
    show_fn(lead_neg, name=f'LeadNeg - {nome}', options={'color': (210, 185, 80)})
    _log(f'Template capacitor PTH OK  d={diam}mm  h={altura}mm')


def _tmpl_transistor_to92(dados, nome, show_fn, cq, _log):
    """Template 3D para transistor TO-92 — corpo em D (semicilindro)."""
    pitch    = float(dados['pinos']['pitch'])
    furo_d   = float(dados['pinos']['diametro_furo'])
    d_corpo  = float(dados['corpo']['diametro'])
    h_corpo  = float(dados['corpo']['altura'])
    pcb_t    = float(dados.get('pcb', {}).get('espessura', 1.6))
    lead_r   = max(0.1, furo_d * 0.4)
    r        = d_corpo / 2
    standoff = 0.5

    try:
        cil   = cq.Workplane("XY").cylinder(h_corpo, r)
        corte = (cq.Workplane("XY")
                 .box(r * 2.5, r * 1.1, h_corpo * 2, centered=(True, False, True))
                 .translate((0, 0, 0)))
        corpo = cil.cut(corte).translate((0, 0, pcb_t + standoff + h_corpo / 2))
    except Exception:
        corpo = (cq.Workplane("XY").cylinder(h_corpo, r)
                 .translate((0, 0, pcb_t + standoff + h_corpo / 2)))

    leg_len = pcb_t + standoff + 2
    for i in range(3):
        x = -(1) * pitch + i * pitch
        perna = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
                 .translate((x, 0, -pcb_t)))
        show_fn(perna, name=f'Lead_{i+1} - {nome}', options={'color': (210, 185, 80)})

    show_fn(corpo, name=f'Corpo - {nome}', options={'color': (30, 30, 30), 'alpha': 0.95})
    _log(f'Template TO-92 OK  d={d_corpo}mm  h={h_corpo}mm')


def _tmpl_crystal_hc49(dados, nome, show_fn, cq, _log):
    """Template 3D para cristal HC-49."""
    larg        = float(dados['corpo']['largura'])
    comp        = float(dados['corpo']['comprimento'])
    alt         = float(dados['corpo']['altura'])
    espacamento = float(dados['pinos']['espacamento'])
    furo_d      = float(dados['pinos']['diametro_furo'])
    pcb_t       = float(dados.get('pcb', {}).get('espessura', 1.6))
    lead_r      = max(0.1, furo_d * 0.4)

    try:
        corpo = (cq.Workplane("XY")
                 .box(larg, comp, alt, centered=(True, True, False))
                 .edges("|Z").fillet(larg * 0.15)
                 .translate((0, 0, pcb_t)))
    except Exception:
        corpo = (cq.Workplane("XY")
                 .box(larg, comp, alt, centered=(True, True, False))
                 .translate((0, 0, pcb_t)))

    leg_len = pcb_t + 2
    lead_a = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
              .translate((-espacamento/2, 0, -pcb_t)))
    lead_b = (cq.Workplane("XY").circle(lead_r).extrude(leg_len)
              .translate(( espacamento/2, 0, -pcb_t)))

    show_fn(corpo,  name=f'Corpo - {nome}', options={'color': (170, 175, 180), 'alpha': 0.95})
    show_fn(lead_a, name=f'Lead1 - {nome}', options={'color': (210, 185, 80)})
    show_fn(lead_b, name=f'Lead2 - {nome}', options={'color': (210, 185, 80)})
    _log(f'Template crystal HC-49 OK  {larg}x{comp}x{alt}mm')


def _tmpl_generic_fallback(dados, nome, show_fn, cq, _log):
    """Template 3D genérico — caixa/cilindro baseado no campo corpo."""
    corpo = dados.get('corpo', {})
    largura = float(corpo.get('largura', 5.0))
    comp = float(corpo.get('comprimento', corpo.get('altura', largura)))
    alt = float(corpo.get('altura_3d', 2.0))
    formato = corpo.get('formato', 'retangulo')
    nome_lower = nome.lower()

    if 'batter' in nome_lower or 'bat' in nome_lower or 'cr20' in nome_lower:
        cor_corpo = (190, 190, 200)
        cor_detalhe = (50, 50, 50)
        alt = max(alt, 5.4)
    elif 'antena' in nome_lower or 'antenna' in nome_lower or 'gps' in nome_lower:
        cor_corpo = (215, 210, 185)
        cor_detalhe = (185, 140, 40)
    elif 'supercap' in nome_lower or 'cap' in nome_lower:
        cor_corpo = (35, 35, 35)
        cor_detalhe = (190, 190, 200)
    else:
        cor_corpo = (65, 65, 70)
        cor_detalhe = None

    if formato in ('cilindro', 'circulo'):
        raio = largura / 2.0
        _log(f"3D cilindro d={largura}mm h={alt}mm para '{nome}'")
        body = cq.Workplane("XY").cylinder(alt, raio)
        show_fn(body, name=f"Corpo - {nome}", options={"color": cor_corpo, "alpha": 0.95})
        if cor_detalhe:
            ring = cq.Workplane("XY").workplane(offset=alt/2 - 0.3).cylinder(0.3, raio * 0.85)
            show_fn(ring, name=f"Topo - {nome}", options={"color": cor_detalhe, "alpha": 0.95})
    else:
        _log(f"3D caixa {largura}x{comp}x{alt}mm para '{nome}'")
        body = cq.Workplane("XY").box(largura, comp, alt)
        show_fn(body, name=f"Corpo - {nome}", options={"color": cor_corpo, "alpha": 0.95})
        if cor_detalhe and ('antena' in nome_lower or 'antenna' in nome_lower or 'gps' in nome_lower):
            patch = cq.Workplane("XY").workplane(offset=alt/2).box(largura * 0.75, comp * 0.75, 0.05)
            show_fn(patch, name=f"Patch - {nome}", options={"color": cor_detalhe, "alpha": 0.95})
    return None


# =============================================================================
# Importar templates extras (SMD, Power, BGA)
# =============================================================================

try:
    from _3d_templates_smd import _tmpl_smd_chip, _tmpl_smd_diode, _tmpl_sot23, _tmpl_ssop
    _HAS_SMD = True
except ImportError:
    _HAS_SMD = False

try:
    from _3d_templates_power import _tmpl_dpak, _tmpl_to220, _tmpl_qfn, _tmpl_tqfp
    _HAS_POWER = True
except ImportError:
    _HAS_POWER = False

try:
    from _3d_templates_bga import _tmpl_bga
    _HAS_BGA = True
except ImportError:
    _HAS_BGA = False


# =============================================================================
# Registry de templates 3D
# =============================================================================

TEMPLATES_3D = {
    'diodo_pth':       _tmpl_axial_pth,
    'resistor_pth':    _tmpl_resistor_pth,
    'ci_dip':          _tmpl_ci_dip,
    'ci_soic':         _tmpl_ci_soic,
    'conector_pth':    _tmpl_conector_pth,
    'castellated':     _tmpl_castellated,
    'led_pth':         _tmpl_led_pth,
    'capacitor_pth':   _tmpl_capacitor_pth,
    'transistor_to92': _tmpl_transistor_to92,
    'crystal_hc49':    _tmpl_crystal_hc49,
}

if _HAS_SMD:
    TEMPLATES_3D.update({
        'smd_chip':  _tmpl_smd_chip,
        'smd_diode': _tmpl_smd_diode,
        'sot23':     _tmpl_sot23,
        'ssop':      _tmpl_ssop,
    })

if _HAS_POWER:
    TEMPLATES_3D.update({
        'dpak':  _tmpl_dpak,
        'to220': _tmpl_to220,
        'qfn':   _tmpl_qfn,
        'tqfp':  _tmpl_tqfp,
    })

if _HAS_BGA:
    TEMPLATES_3D['bga'] = _tmpl_bga


def listar_tipos_3d():
    """Retorna lista dos tipos de modelo 3D disponíveis."""
    return sorted(TEMPLATES_3D.keys())


# =============================================================================
# Motor headless: gera .step sem CQ-Editor
# =============================================================================

def gerar_3d_step(dados, caminho_saida, log_fn=None):
    """Gera modelo 3D .step a partir de um dict YAML. Sem GUI.

    Args:
        dados: dict com dados do componente (mesmo formato do YAML)
        caminho_saida: caminho do arquivo .step de saída
        log_fn: função de log opcional (default: print)

    Returns:
        Caminho do arquivo gerado, ou None se falhou

    Raises:
        ImportError: se cadquery não está instalado
    """
    if not _HAS_CQ:
        raise ImportError("cadquery não está instalado. Instale com: pip install cadquery")

    _log = log_fn or print
    nome = dados.get('nome', 'componente')
    tipo = dados.get('tipo', '')
    tipo_3d = dados.get('tipo_3d', '')

    # --- Coletor headless (substitui show_object) ---
    _partes = []

    def _show_fn(shape, name=None, options=None):
        """Coletor headless — acumula geometria sem exibir."""
        _partes.append((shape, name or f'part_{len(_partes)}'))

    # --- Rotear para template correto ---
    chave = tipo_3d or tipo
    fn = TEMPLATES_3D.get(chave)

    try:
        if fn:
            _log(f"[3D] Usando template '{chave}' para '{nome}'")
            result = fn(dados, nome, _show_fn, cq, _log)
        else:
            _log(f"[3D] Usando fallback genérico para '{nome}'")
            result = _tmpl_generic_fallback(dados, nome, _show_fn, cq, _log)
    except Exception as e:
        _log(f"[3D] ERRO: {type(e).__name__}: {e}")
        return None

    # --- Exportar STEP ---
    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida)), exist_ok=True)

    try:
        if isinstance(result, cq.Assembly):
            result.save(caminho_saida, exportType='STEP')
        elif _partes:
            assembly = cq.Assembly()
            for shape, name in _partes:
                try:
                    assembly.add(shape, name=name)
                except Exception as e:
                    log.debug('3D detail skipped: %s', e)
            assembly.save(caminho_saida, exportType='STEP')
        else:
            _log("[3D] Nenhuma geometria gerada")
            return None

        _log(f"[3D] STEP exportado: {os.path.basename(caminho_saida)}")
        return caminho_saida

    except Exception as e:
        _log(f"[3D] STEP falhou: {e}")
        return None


def rotear_template_3d(tipo, dados, nome, show_fn, cq_module, log_fn):
    """Roteia para o template 3D correto. Para uso pelo gerador_universal.py.

    Args:
        tipo: tipo ou tipo_3d do componente
        dados: dict completo do YAML
        nome: nome do componente
        show_fn: função show_object (real ou wrapper)
        cq_module: módulo cadquery
        log_fn: função de log

    Returns:
        cq.Assembly se o template retornar um, None caso contrário
    """
    tipo_3d = dados.get('tipo_3d', '')
    chave = tipo_3d or tipo
    fn = TEMPLATES_3D.get(chave)
    if fn:
        result = fn(dados, nome, show_fn, cq_module, log_fn)
        return result
    else:
        return _tmpl_generic_fallback(dados, nome, show_fn, cq_module, log_fn)
