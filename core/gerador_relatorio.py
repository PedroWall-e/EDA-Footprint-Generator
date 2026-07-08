"""Gerador de relatório técnico para componentes.

Gera folhas de relatório com:
- Footprint 2D com réguas/cotas
- Modelo 3D (captura ou renderização)
- Símbolo esquemático 2D
- Tabela de especificações técnicas
- Tabela de pinagem
- Validação IPC/DRC

Formatos: PDF (via matplotlib PdfPages) e HTML.
"""
import os
import sys

try:
    from core.version import __version__
except ImportError:
    __version__ = '3.0.0'
import yaml
import logging
import datetime
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for PDF generation
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec

log = logging.getLogger(__name__)

# ── Attempt imports (graceful degradation) ────────────────────────────────────
try:
    from core.renderizador_footprint_print import render_footprint_print, parse_kicad_mod
    _HAS_RENDERER = True
except ImportError:
    try:
        from renderizador_footprint_print import render_footprint_print, parse_kicad_mod
        _HAS_RENDERER = True
    except ImportError:
        _HAS_RENDERER = False

try:
    from core.renderizador_cotas import DesenhadorCotas
    _HAS_COTAS = True
except ImportError:
    try:
        from renderizador_cotas import DesenhadorCotas
        _HAS_COTAS = True
    except ImportError:
        _HAS_COTAS = False


def gerar_relatorio(yaml_paths, output_path, opcoes=None):
    """Gera relatório técnico em PDF e/ou HTML.

    Args:
        yaml_paths: list of YAML file paths
        output_path: output file path (.pdf or .html)
        opcoes: dict with:
            - formato: 'pdf', 'html', or 'ambos' (default: 'ambos')
            - footprint_2d: bool (default: True)
            - modelo_3d: bool (default: True)
            - modelo_3d_modo: 'viewport' or 'offline' (default: 'viewport')
            - simbolo: bool (default: True)
            - specs: bool (default: True)
            - pinagem: bool (default: True)
            - validacao: bool (default: True)
            - cotas: bool (default: True)
            - escala: float (default: 1.0 for 1:1)
            - saida_dir: directory for generated files
    Returns:
        dict with 'pdf_path', 'html_path', 'total', 'erros'
    """
    if opcoes is None:
        opcoes = {}

    formato = opcoes.get('formato', 'ambos')
    escala = opcoes.get('escala', 1.0)
    saida_dir = opcoes.get('saida_dir', os.path.dirname(output_path))

    resultado = {'total': 0, 'erros': [], 'pdf_path': None, 'html_path': None}
    componentes = []

    # Process each YAML
    for yaml_path in yaml_paths:
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                dados = yaml.safe_load(f)
            if not dados or 'nome' not in dados:
                resultado['erros'].append(f'{yaml_path}: YAML inválido')
                continue

            nome = dados['nome']
            tipo = dados.get('tipo', dados.get('padrao', 'custom'))

            # Find the .kicad_mod file
            kicad_mod = os.path.join(saida_dir, f'{nome}.kicad_mod')
            if not os.path.exists(kicad_mod):
                # Try same directory as YAML
                alt = os.path.join(os.path.dirname(yaml_path), f'{nome}.kicad_mod')
                if os.path.exists(alt):
                    kicad_mod = alt
                else:
                    kicad_mod = None

            # Find the .kicad_sym file
            kicad_sym = os.path.join(saida_dir, f'{nome}.kicad_sym')
            if not os.path.exists(kicad_sym):
                alt = os.path.join(os.path.dirname(yaml_path), f'{nome}.kicad_sym')
                if os.path.exists(alt):
                    kicad_sym = alt
                else:
                    kicad_sym = None

            componentes.append({
                'nome': nome,
                'tipo': tipo,
                'dados': dados,
                'yaml_path': yaml_path,
                'kicad_mod': kicad_mod,
                'kicad_sym': kicad_sym,
            })
            resultado['total'] += 1
        except Exception as e:
            resultado['erros'].append(f'{yaml_path}: {e}')

    # Generate PDF
    if formato in ('pdf', 'ambos'):
        pdf_path = output_path if output_path.endswith('.pdf') else output_path + '.pdf'
        try:
            _gerar_pdf(componentes, pdf_path, opcoes)
            resultado['pdf_path'] = pdf_path
        except Exception as e:
            resultado['erros'].append(f'PDF: {e}')
            log.exception('Erro ao gerar PDF')

    # Generate HTML
    if formato in ('html', 'ambos'):
        html_path = (output_path.replace('.pdf', '.html')
                     if output_path.endswith('.pdf')
                     else output_path + '.html')
        try:
            _gerar_html(componentes, html_path, opcoes)
            resultado['html_path'] = html_path
        except Exception as e:
            resultado['erros'].append(f'HTML: {e}')
            log.exception('Erro ao gerar HTML')

    return resultado


# =============================================================================
# PDF Generation
# =============================================================================

def _gerar_pdf(componentes, pdf_path, opcoes):
    """Generate multi-page PDF report."""
    escala = opcoes.get('escala', 1.0)
    show_cotas = opcoes.get('cotas', True)
    show_specs = opcoes.get('specs', True)
    show_pinagem = opcoes.get('pinagem', True)
    show_validacao = opcoes.get('validacao', True)
    show_3d = opcoes.get('modelo_3d', True)
    show_simbolo = opcoes.get('simbolo', True)

    os.makedirs(os.path.dirname(pdf_path) or '.', exist_ok=True)

    with PdfPages(pdf_path) as pdf:
        for comp in componentes:
            fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape
            fig.set_facecolor('white')

            # Use GridSpec for layout: 3 rows x 2 columns
            gs = GridSpec(3, 2, figure=fig,
                         left=0.05, right=0.95, top=0.92, bottom=0.05,
                         hspace=0.3, wspace=0.2)

            dados = comp['dados']
            nome = comp['nome']
            tipo = comp['tipo']

            # ── Header ──
            fig.suptitle(f'RELATÓRIO TÉCNICO — {nome}',
                         fontsize=14, fontweight='bold', y=0.97,
                         color='#1A1A2E')

            # Subheader with type and date
            escala_str = '1:1' if escala == 1.0 else f'1:{1 / escala:.0f}'
            data_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            fig.text(0.05, 0.935,
                     f'Tipo: {tipo}  \u2502  '
                     f'Escala: {escala_str}  \u2502  '
                     f'Data: {data_str}  \u2502  '
                     f'Gerado por Plataforma CAM-CAD Data Frontier v{__version__}',
                     fontsize=7, color='#616161', fontfamily='sans-serif')

            # ── Panel 1: Footprint 2D (top-left, large) ──
            ax_fp = fig.add_subplot(gs[0:2, 0])  # spans 2 rows
            if comp['kicad_mod'] and _HAS_RENDERER:
                render_footprint_print(ax_fp, comp['kicad_mod'],
                                       cotas=show_cotas, escala=escala,
                                       titulo=f'Footprint — {nome}')
            else:
                ax_fp.text(0.5, 0.5, 'Footprint não disponível',
                           ha='center', va='center', transform=ax_fp.transAxes,
                           fontsize=10, color='#9E9E9E')
                ax_fp.set_facecolor('#F5F5F5')

            # ── Panel 2: Specs table (top-right) ──
            if show_specs:
                ax_specs = fig.add_subplot(gs[0, 1])
                _draw_specs_table(ax_specs, dados)

            # ── Panel 3: Pinagem table (middle-right) ──
            if show_pinagem:
                ax_pins = fig.add_subplot(gs[1, 1])
                _draw_pinagem_table(ax_pins, dados)

            # ── Panel 4: 3D / Symbol / Validation (bottom row) ──
            if show_3d or show_simbolo:
                ax_3d = fig.add_subplot(gs[2, 0])
                _draw_3d_placeholder(ax_3d, dados, opcoes)

            if show_validacao:
                ax_val = fig.add_subplot(gs[2, 1])
                _draw_validation_info(ax_val, dados)

            pdf.savefig(fig)
            plt.close(fig)

    log.info('Relatório PDF gerado: %s (%d páginas)', pdf_path, len(componentes))


def _draw_specs_table(ax, dados):
    """Draw technical specifications table."""
    ax.set_facecolor('#FAFAFA')
    ax.set_title('ESPECIFICAÇÕES TÉCNICAS', fontsize=9, fontweight='bold',
                 color='#1A1A2E', loc='left', pad=6)
    ax.axis('off')

    # Build specs list
    specs = []
    specs.append(('Nome', dados.get('nome', '')))
    specs.append(('Tipo', dados.get('tipo', dados.get('padrao', ''))))

    if dados.get('fabricante'):
        specs.append(('Fabricante', dados['fabricante']))
    if dados.get('mpn'):
        specs.append(('MPN', dados['mpn']))

    kicad = dados.get('kicad', {})
    if kicad.get('referencia'):
        specs.append(('Referência', kicad['referencia']))
    if kicad.get('valor'):
        specs.append(('Valor', kicad['valor']))
    if kicad.get('descricao'):
        specs.append(('Descrição', str(kicad['descricao'])[:50]))

    pinos = dados.get('pinos', {})
    if pinos.get('total'):
        specs.append(('Pinos', str(pinos['total'])))
    if pinos.get('pitch'):
        specs.append(('Pitch', f'{pinos["pitch"]} mm'))
    if pinos.get('espacamento'):
        specs.append(('Espaçamento', f'{pinos["espacamento"]} mm'))
    if pinos.get('diametro_pad'):
        specs.append(('Pad \u00d8', f'{pinos["diametro_pad"]} mm'))
    if pinos.get('diametro_furo'):
        specs.append(('Furo \u00d8', f'{pinos["diametro_furo"]} mm'))

    tamanho_pad = pinos.get('tamanho_pad', {})
    if tamanho_pad:
        specs.append(('Pad', f'{tamanho_pad.get("largura", "?")} '
                             f'\u00d7 {tamanho_pad.get("altura", "?")} mm'))

    corpo = dados.get('corpo', {})
    if corpo.get('largura'):
        specs.append(('Corpo L', f'{corpo["largura"]} mm'))
    if corpo.get('comprimento'):
        specs.append(('Corpo C', f'{corpo["comprimento"]} mm'))
    if corpo.get('diametro'):
        specs.append(('Corpo \u00d8', f'{corpo["diametro"]} mm'))

    margens = dados.get('margens', {})
    if margens.get('courtyard'):
        specs.append(('Courtyard', f'{margens["courtyard"]} mm'))

    eletrico = dados.get('eletrico', {})
    for key in ('tolerancia', 'potencia', 'tensao_maxima', 'corrente_maxima'):
        if eletrico.get(key):
            label = key.replace('_', ' ').title()
            specs.append((label, str(eletrico[key])))

    if not specs:
        ax.text(0.5, 0.5, 'Sem dados', ha='center', va='center',
                transform=ax.transAxes, color='#9E9E9E')
        return

    # Draw as table
    col_labels = ['Parâmetro', 'Valor']
    table = ax.table(
        cellText=specs,
        colLabels=col_labels,
        cellLoc='left',
        loc='upper center',
        colWidths=[0.4, 0.55],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)

    # Style header
    for j in range(2):
        cell = table[0, j]
        cell.set_facecolor('#1A1A2E')
        cell.set_text_props(color='white', fontweight='bold')

    # Style data rows
    for i in range(1, len(specs) + 1):
        for j in range(2):
            cell = table[i, j]
            cell.set_facecolor('#F5F5F5' if i % 2 == 0 else '#FFFFFF')
            cell.set_edgecolor('#E0E0E0')


def _draw_pinagem_table(ax, dados):
    """Draw pin assignment table."""
    ax.set_facecolor('#FAFAFA')
    ax.set_title('PINAGEM', fontsize=9, fontweight='bold',
                 color='#1A1A2E', loc='left', pad=6)
    ax.axis('off')

    pin_names = dados.get('pin_names', {})
    pin_types = dados.get('pin_types', {})
    pinos = dados.get('pinos', {})
    total = pinos.get('total', len(pin_names) if pin_names else 0)

    # For custom pads
    pads_list = dados.get('pads', [])

    if not pin_names and not pads_list:
        # Auto-generate from total
        if total > 0:
            rows = [[str(i + 1), '', ''] for i in range(min(total, 20))]
            if total > 20:
                rows.append(['...', f'(+{total - 20} pinos)', ''])
        else:
            ax.text(0.5, 0.5, 'Pinagem não definida', ha='center', va='center',
                    transform=ax.transAxes, color='#9E9E9E', fontsize=8)
            return
    else:
        rows = []
        if pads_list:
            for pad in pads_list[:20]:
                rows.append([
                    str(pad.get('numero', '')),
                    pad.get('nome', ''),
                    pad.get('tipo_eletrico', '')
                ])
            if len(pads_list) > 20:
                rows.append(['...', f'(+{len(pads_list) - 20} pinos)', ''])
        else:
            sorted_keys = sorted(
                pin_names.keys(),
                key=lambda x: int(x) if str(x).isdigit() else x
            )
            for pin_num in sorted_keys[:20]:
                rows.append([
                    str(pin_num),
                    str(pin_names.get(pin_num, '')),
                    str(pin_types.get(pin_num, ''))
                ])
            if len(sorted_keys) > 20:
                rows.append(['...', f'(+{len(sorted_keys) - 20} pinos)', ''])

    if not rows:
        return

    table = ax.table(
        cellText=rows[:17],  # limit to 17 rows per page
        colLabels=['Pino', 'Nome', 'Tipo'],
        cellLoc='center',
        loc='upper center',
        colWidths=[0.15, 0.45, 0.35],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)

    for j in range(3):
        cell = table[0, j]
        cell.set_facecolor('#1A1A2E')
        cell.set_text_props(color='white', fontweight='bold')

    for i in range(1, min(len(rows), 17) + 1):
        for j in range(3):
            cell = table[i, j]
            cell.set_facecolor('#F5F5F5' if i % 2 == 0 else '#FFFFFF')
            cell.set_edgecolor('#E0E0E0')


def _draw_3d_placeholder(ax, dados, opcoes):
    """Draw 3D model section. Try viewport capture or show placeholder."""
    ax.set_facecolor('#F0F0F0')
    ax.set_title('MODELO 3D', fontsize=9, fontweight='bold',
                 color='#1A1A2E', loc='left', pad=6)
    ax.axis('off')

    modo_3d = opcoes.get('modelo_3d_modo', 'viewport')

    # Try to find a 3D capture image
    nome = dados.get('nome', '')
    saida_dir = opcoes.get('saida_dir', '')
    img_path = os.path.join(saida_dir, f'{nome}_3d.png')

    if os.path.exists(img_path):
        try:
            img = plt.imread(img_path)
            ax.imshow(img)
            ax.set_title('MODELO 3D (captura)', fontsize=9, fontweight='bold',
                         color='#1A1A2E', loc='left', pad=6)
        except Exception as e:
            ax.text(0.5, 0.5, f'Erro ao carregar 3D:\n{e}',
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=8, color='#757575')
    else:
        # Placeholder with component info
        tipo_3d = dados.get('tipo_3d', dados.get('tipo', '?'))
        ax.text(0.5, 0.5,
                f'Modelo 3D\n{tipo_3d}\n\n'
                f'(gerar captura com CQ-Editor\n'
                f'ou usar modo offline)',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=9, color='#757575',
                bbox=dict(boxstyle='round,pad=0.5',
                          facecolor='#E0E0E0', edgecolor='#BDBDBD'))


def _draw_validation_info(ax, dados):
    """Draw IPC/DRC validation results."""
    ax.set_facecolor('#FAFAFA')
    ax.set_title('VALIDAÇÃO', fontsize=9, fontweight='bold',
                 color='#1A1A2E', loc='left', pad=6)
    ax.axis('off')

    lines = []

    # Try IPC validation
    try:
        core_dir = os.path.dirname(os.path.abspath(__file__))
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)
        from validador_ipc import validar_yaml
        ipc = validar_yaml(dados)
        status = '[OK] IPC-7351B OK' if ipc.ok else '[FAIL] IPC-7351B FALHOU'
        lines.append(status)
        for e in ipc.errors[:3]:
            lines.append(f'  - {e}')
        for w in ipc.warnings[:3]:
            lines.append(f'  * {w}')
    except Exception as e:
        lines.append(f'IPC: não disponível ({e})')

    # Try DRC validation
    try:
        from verificador_drc import verificar_drc
        drc = verificar_drc(dados)
        status = '[OK] DRC OK' if drc.ok else '[FAIL] DRC FALHOU'
        lines.append(status)
        for e in drc.errors[:3]:
            lines.append(f'  - {e}')
        for w in drc.warnings[:2]:
            lines.append(f'  * {w}')
    except Exception as e:
        lines.append(f'DRC: não disponível ({e})')

    lines.append('')
    lines.append(f'Data: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'Plataforma CAM-CAD Data Frontier v{__version__}')

    text = '\n'.join(lines)
    ax.text(0.05, 0.95, text, transform=ax.transAxes,
            fontsize=7, fontfamily='monospace', color='#424242',
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor='#FAFAFA', edgecolor='#E0E0E0'))


# =============================================================================
# HTML Generation
# =============================================================================

def _gerar_html(componentes, html_path, opcoes):
    """Generate HTML report with embedded images."""
    escala = opcoes.get('escala', 1.0)
    show_cotas = opcoes.get('cotas', True)
    saida_dir = opcoes.get('saida_dir', os.path.dirname(html_path))

    # Generate PNG images for each component
    img_dir = os.path.join(os.path.dirname(html_path), '_relatorio_imgs')
    os.makedirs(img_dir, exist_ok=True)

    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="pt-BR"><head><meta charset="UTF-8">')
    html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append('<title>Relat\u00f3rio T\u00e9cnico \u2014 Data Frontier</title>')
    html_parts.append('<style>')
    html_parts.append('''
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5;
               color: #212121; margin: 0; padding: 20px; }
        .page { background: white; max-width: 1000px; margin: 20px auto;
                padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 8px; page-break-after: always; }
        h1 { color: #1A1A2E; border-bottom: 3px solid #89B4FA; padding-bottom: 8px; }
        h2 { color: #1565C0; font-size: 16px; margin-top: 24px; }
        .meta { color: #757575; font-size: 12px; margin-bottom: 16px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        .footprint-img { width: 100%; border: 1px solid #e0e0e0; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { background: #1A1A2E; color: white; padding: 8px 12px; text-align: left; }
        td { padding: 6px 12px; border-bottom: 1px solid #e0e0e0; }
        tr:nth-child(even) { background: #f5f5f5; }
        .badge-ok { background: #4CAF50; color: white; padding: 2px 8px;
                    border-radius: 12px; font-size: 11px; }
        .badge-fail { background: #f44336; color: white; padding: 2px 8px;
                     border-radius: 12px; font-size: 11px; }
        .footer { text-align: center; color: #9E9E9E; font-size: 11px;
                  margin-top: 24px; padding-top: 12px;
                  border-top: 1px solid #E0E0E0; }
        @media print {
            .page { box-shadow: none; margin: 0; padding: 20px; }
            body { background: white; padding: 0; }
        }
    ''')
    html_parts.append('</style></head><body>')

    for comp in componentes:
        dados = comp['dados']
        nome = comp['nome']
        tipo = comp['tipo']

        # Generate footprint image
        fp_img_path = os.path.join(img_dir, f'{nome}_fp.png')
        if comp['kicad_mod'] and _HAS_RENDERER:
            try:
                fig_fp, ax_fp = plt.subplots(1, 1, figsize=(8, 6))
                fig_fp.set_facecolor('white')
                render_footprint_print(ax_fp, comp['kicad_mod'],
                                       cotas=show_cotas, escala=escala)
                fig_fp.savefig(fp_img_path, dpi=200, bbox_inches='tight',
                               facecolor='white')
                plt.close(fig_fp)
            except Exception as e:
                log.warning('Erro ao gerar imagem footprint %s: %s', nome, e)

        escala_str = '1:1' if escala == 1.0 else f'1:{1 / escala:.0f}'
        data_str = datetime.datetime.now().strftime('%Y-%m-%d')

        html_parts.append(f'<div class="page">')
        html_parts.append(f'<h1>\U0001f4cb {_html_escape(nome)}</h1>')
        html_parts.append(f'<div class="meta">Tipo: {_html_escape(tipo)} \u2502 '
                          f'Escala: {escala_str} \u2502 '
                          f'Data: {data_str} \u2502 '
                          f'Data Frontier v{__version__}</div>')

        html_parts.append('<div class="grid">')

        # Footprint image
        html_parts.append('<div>')
        html_parts.append('<h2>Footprint 2D</h2>')
        if os.path.exists(fp_img_path):
            rel_path = os.path.relpath(fp_img_path, os.path.dirname(html_path))
            rel_path = rel_path.replace('\\', '/')
            html_parts.append(
                f'<img src="{rel_path}" class="footprint-img" '
                f'alt="Footprint {_html_escape(nome)}">'
            )
        else:
            html_parts.append(
                '<p style="color:#9e9e9e">Footprint n\u00e3o dispon\u00edvel</p>'
            )
        html_parts.append('</div>')

        # Specs table
        html_parts.append('<div>')
        html_parts.append('<h2>Especifica\u00e7\u00f5es T\u00e9cnicas</h2>')
        html_parts.append(_specs_to_html(dados))

        # Pinagem table
        html_parts.append('<h2>Pinagem</h2>')
        html_parts.append(_pinagem_to_html(dados))
        html_parts.append('</div>')

        html_parts.append('</div>')  # end grid

        # Validation
        html_parts.append('<h2>Valida\u00e7\u00e3o</h2>')
        html_parts.append(_validation_to_html(dados))

        # Footer
        html_parts.append(
            f'<div class="footer">Gerado em {data_str} por '
            f'Plataforma CAM-CAD Data Frontier v{__version__}</div>'
        )

        html_parts.append('</div>')  # end page

    html_parts.append('</body></html>')

    os.makedirs(os.path.dirname(html_path) or '.', exist_ok=True)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

    log.info('Relatório HTML gerado: %s (%d componentes)',
             html_path, len(componentes))


def _html_escape(text):
    """Basic HTML escaping."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _specs_to_html(dados):
    """Build HTML specs table."""
    rows = []
    rows.append(('Nome', dados.get('nome', '')))
    rows.append(('Tipo', dados.get('tipo', dados.get('padrao', ''))))
    if dados.get('fabricante'):
        rows.append(('Fabricante', dados['fabricante']))
    if dados.get('mpn'):
        rows.append(('MPN', dados['mpn']))

    kicad = dados.get('kicad', {})
    if kicad.get('referencia'):
        rows.append(('Refer\u00eancia', kicad['referencia']))
    if kicad.get('valor'):
        rows.append(('Valor', kicad['valor']))
    if kicad.get('descricao'):
        rows.append(('Descri\u00e7\u00e3o', str(kicad['descricao'])[:60]))

    pinos = dados.get('pinos', {})
    if pinos.get('total'):
        rows.append(('Pinos', str(pinos['total'])))
    if pinos.get('pitch'):
        rows.append(('Pitch', f'{pinos["pitch"]} mm'))
    if pinos.get('espacamento'):
        rows.append(('Espa\u00e7amento', f'{pinos["espacamento"]} mm'))
    if pinos.get('diametro_pad'):
        rows.append(('Pad \u00d8', f'{pinos["diametro_pad"]} mm'))
    if pinos.get('diametro_furo'):
        rows.append(('Furo \u00d8', f'{pinos["diametro_furo"]} mm'))

    tamanho_pad = pinos.get('tamanho_pad', {})
    if tamanho_pad:
        rows.append(('Pad', f'{tamanho_pad.get("largura", "?")} '
                            f'\u00d7 {tamanho_pad.get("altura", "?")} mm'))

    corpo = dados.get('corpo', {})
    if corpo.get('largura'):
        rows.append(('Corpo L', f'{corpo["largura"]} mm'))
    if corpo.get('comprimento'):
        rows.append(('Corpo C', f'{corpo["comprimento"]} mm'))
    if corpo.get('diametro'):
        rows.append(('Corpo \u00d8', f'{corpo["diametro"]} mm'))

    margens = dados.get('margens', {})
    if margens.get('courtyard'):
        rows.append(('Courtyard', f'{margens["courtyard"]} mm'))

    eletrico = dados.get('eletrico', {})
    for key in ('tolerancia', 'potencia', 'tensao_maxima', 'corrente_maxima'):
        if eletrico.get(key):
            label = key.replace('_', ' ').title()
            rows.append((label, str(eletrico[key])))

    html = '<table><tr><th>Par\u00e2metro</th><th>Valor</th></tr>'
    for param, val in rows:
        html += f'<tr><td>{_html_escape(param)}</td><td>{_html_escape(val)}</td></tr>'
    html += '</table>'
    return html


def _pinagem_to_html(dados):
    """Build HTML pinagem table."""
    pin_names = dados.get('pin_names', {})
    pin_types = dados.get('pin_types', {})
    pads_list = dados.get('pads', [])

    html = '<table><tr><th>Pino</th><th>Nome</th><th>Tipo</th></tr>'

    if pads_list:
        for pad in pads_list[:20]:
            html += (f'<tr><td>{_html_escape(pad.get("numero", ""))}</td>'
                     f'<td>{_html_escape(pad.get("nome", ""))}</td>'
                     f'<td>{_html_escape(pad.get("tipo_eletrico", ""))}</td></tr>')
        if len(pads_list) > 20:
            html += (f'<tr><td colspan="3" style="color:#9e9e9e">'
                     f'(+{len(pads_list) - 20} pinos adicionais)</td></tr>')
    elif pin_names:
        sorted_keys = sorted(
            pin_names.keys(),
            key=lambda x: int(x) if str(x).isdigit() else x
        )
        for num in sorted_keys[:20]:
            html += (f'<tr><td>{_html_escape(num)}</td>'
                     f'<td>{_html_escape(pin_names.get(num, ""))}</td>'
                     f'<td>{_html_escape(pin_types.get(num, ""))}</td></tr>')
        if len(sorted_keys) > 20:
            html += (f'<tr><td colspan="3" style="color:#9e9e9e">'
                     f'(+{len(sorted_keys) - 20} pinos adicionais)</td></tr>')
    else:
        total = dados.get('pinos', {}).get('total', 0)
        if total:
            html += (f'<tr><td colspan="3">{total} pinos '
                     f'(nomes n\u00e3o definidos)</td></tr>')
        else:
            html += '<tr><td colspan="3">Pinagem n\u00e3o definida</td></tr>'

    html += '</table>'
    return html


def _validation_to_html(dados):
    """Build HTML validation section."""
    lines = []
    try:
        core_dir = os.path.dirname(os.path.abspath(__file__))
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)
        from validador_ipc import validar_yaml
        ipc = validar_yaml(dados)
        badge = 'badge-ok' if ipc.ok else 'badge-fail'
        text = 'OK' if ipc.ok else 'FALHOU'
        lines.append(f'<span class="{badge}">IPC-7351B: {text}</span> ')
        for e in ipc.errors[:3]:
            lines.append(f'<br><small>\u274c {_html_escape(e)}</small>')
        for w in ipc.warnings[:3]:
            lines.append(f'<br><small>\u26a0\ufe0f {_html_escape(w)}</small>')
    except Exception:
        lines.append('<span class="badge-fail">IPC: n\u00e3o dispon\u00edvel</span>')

    try:
        from verificador_drc import verificar_drc
        drc = verificar_drc(dados)
        badge = 'badge-ok' if drc.ok else 'badge-fail'
        text = 'OK' if drc.ok else 'FALHOU'
        lines.append(f' <span class="{badge}">DRC: {text}</span>')
        for e in drc.errors[:3]:
            lines.append(f'<br><small>\u274c {_html_escape(e)}</small>')
        for w in drc.warnings[:2]:
            lines.append(f'<br><small>\u26a0\ufe0f {_html_escape(w)}</small>')
    except Exception:
        lines.append(' <span class="badge-fail">DRC: n\u00e3o dispon\u00edvel</span>')

    return '<p>' + ''.join(lines) + '</p>'
