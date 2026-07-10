# -*- coding: utf-8 -*-
"""Painel de ajuda integrado com referência rápida YAML.

Mostra documentação completa sobre padrões de footprint, campos YAML,
atalhos de teclado e regras IPC — tudo dentro de um dock da janela principal.
"""

try:
    from core.version import __version__
except ImportError:
    __version__ = '3.0.0'

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextDocument


class HelpPanel(QWidget):
    """Painel de ajuda integrado (F1) com busca e referência rápida."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Barra de busca ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText('🔍  Buscar na ajuda…')
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setStyleSheet(
            'QLineEdit {'
            '  background: #313244; color: #CDD6F4; border: none;'
            '  padding: 8px 12px; font-size: 13px; font-family: "Segoe UI", sans-serif;'
            '}'
            'QLineEdit:focus { border-bottom: 2px solid #89B4FA; }'
        )
        self.search_bar.textChanged.connect(self.search)
        layout.addWidget(self.search_bar)

        # --- Navegador HTML ---
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet(
            'QTextBrowser {'
            '  background: #1E1E2E; color: #CDD6F4; border: none;'
            '  font-family: "Segoe UI", sans-serif; font-size: 13px;'
            '  selection-background-color: #45475A;'
            '}'
            'QScrollBar:vertical {'
            '  background: #181825; width: 10px; border: none;'
            '}'
            'QScrollBar::handle:vertical {'
            '  background: #45475A; min-height: 30px; border-radius: 5px;'
            '}'
        )
        self.browser.setHtml(self._build_help_html())
        layout.addWidget(self.browser)

    # -----------------------------------------------------------------
    # HTML do conteúdo de ajuda
    # -----------------------------------------------------------------
    def _build_help_html(self) -> str:
        """Retorna string HTML com toda a documentação de referência."""
        # Estilos reutilizáveis
        S = {
            'bg':       '#1E1E2E',
            'text':     '#CDD6F4',
            'muted':    '#A6ADC8',
            'heading':  '#89B4FA',
            'accent':   '#A6E3A1',
            'warn':     '#F9E2AF',
            'err':      '#F38BA8',
            'code_bg':  '#313244',
            'tbl_head': '#45475A',
            'link':     '#89B4FA',
            'border':   '#45475A',
        }

        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{
    background: {S['bg']}; color: {S['text']};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px; line-height: 1.6; padding: 16px 20px; margin: 0;
}}
h1 {{ color: {S['heading']}; font-size: 20px; margin: 24px 0 8px 0; border-bottom: 2px solid {S['border']}; padding-bottom: 6px; }}
h2 {{ color: {S['heading']}; font-size: 16px; margin: 20px 0 6px 0; }}
h3 {{ color: {S['accent']}; font-size: 14px; margin: 14px 0 4px 0; }}
a {{ color: {S['link']}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{ background: {S['code_bg']}; padding: 2px 6px; border-radius: 3px; font-family: Consolas, "Fira Code", monospace; font-size: 12px; }}
pre {{ background: {S['code_bg']}; padding: 12px 16px; border-radius: 6px; overflow-x: auto; font-family: Consolas, monospace; font-size: 12px; line-height: 1.5; border-left: 3px solid {S['heading']}; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 16px 0; }}
th {{ background: {S['tbl_head']}; color: {S['text']}; padding: 8px 12px; text-align: left; font-weight: 600; }}
td {{ padding: 6px 12px; border-bottom: 1px solid {S['border']}; }}
tr:hover td {{ background: #313244; }}
.toc {{ background: {S['code_bg']}; padding: 12px 18px; border-radius: 8px; margin-bottom: 16px; }}
.toc a {{ display: block; padding: 3px 0; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.badge-pth {{ background: #45475A; color: #89DCEB; }}
.badge-smd {{ background: #45475A; color: #F9E2AF; }}
.badge-bga {{ background: #45475A; color: #F38BA8; }}
.note {{ background: #313244; border-left: 3px solid {S['warn']}; padding: 8px 14px; border-radius: 4px; margin: 8px 0; color: {S['warn']}; }}
.tip  {{ background: #313244; border-left: 3px solid {S['accent']}; padding: 8px 14px; border-radius: 4px; margin: 8px 0; color: {S['accent']}; }}
hr {{ border: none; border-top: 1px solid {S['border']}; margin: 16px 0; }}
</style></head><body>

<h1>📘 Referência Rápida — Plataforma CAM-CAD</h1>
<p style="color:{S['muted']}">v{__version__} &mdash; Gerador de Footprints, Símbolos e Modelos 3D para KiCad</p>

<!-- ======================================================= -->
<!-- ÍNDICE -->
<!-- ======================================================= -->
<div class="toc">
<b>Índice</b>
<a href="#patterns">1. Padrões de Footprint</a>
<a href="#yaml-fields">2. Campos YAML Comuns</a>
<a href="#simbolo-ref">3. Campo simbolo: — Templates de Símbolo</a>
<a href="#pin-ref">4. Referência de Pinos</a>
<a href="#shortcuts">5. Atalhos de Teclado</a>
<a href="#ipc">6. Regras de Validação IPC</a>
<a href="#examples">7. Exemplos Rápidos</a>
</div>

<!-- ======================================================= -->
<!-- 1. PADRÕES DE FOOTPRINT -->
<!-- ======================================================= -->
<h1 id="patterns">1. Padrões de Footprint</h1>
<p>A plataforma suporta <b>7 padrões</b> de empacotamento, configuráveis via <code>formato:</code> no YAML.</p>

<h2>1.1 <span class="badge badge-pth">PTH</span> axial_pth</h2>
<p>Componentes axiais through-hole (resistores, diodos, fusíveis).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.espacamento</code></td><td>float</td><td>Distância entre furos (mm)</td></tr>
<tr><td><code>corpo.comprimento</code></td><td>float</td><td>Comprimento do corpo</td></tr>
<tr><td><code>corpo.diametro</code></td><td>float</td><td>Diâmetro do corpo</td></tr>
<tr><td><code>pinos.diametro_pad</code></td><td>float</td><td>Diâmetro do pad de cobre</td></tr>
<tr><td><code>pinos.diametro_furo</code></td><td>float</td><td>Diâmetro do furo (drill)</td></tr>
</table>

<h2>1.2 <span class="badge badge-pth">PTH</span> radial_pth</h2>
<p>Componentes radiais through-hole (capacitores eletrolíticos, LEDs).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.espacamento</code></td><td>float</td><td>Distância entre furos (mm)</td></tr>
<tr><td><code>corpo.diametro</code></td><td>float</td><td>Diâmetro do corpo</td></tr>
<tr><td><code>corpo.comprimento</code></td><td>float</td><td>Altura/comprimento do corpo</td></tr>
<tr><td><code>pinos.diametro_pad</code></td><td>float</td><td>Diâmetro do pad de cobre</td></tr>
<tr><td><code>pinos.diametro_furo</code></td><td>float</td><td>Diâmetro do furo (drill)</td></tr>
</table>

<h2>1.3 <span class="badge badge-pth">PTH</span> dual_pth</h2>
<p>Encapsulamentos DIP through-hole (DIP-8, DIP-14, DIP-28).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.total</code></td><td>int</td><td>Número total de pinos (par)</td></tr>
<tr><td><code>pinos.pitch</code></td><td>float</td><td>Espaçamento entre pinos (2.54 mm típico)</td></tr>
<tr><td><code>corpo.afastamento_colunas</code></td><td>float</td><td>Distância entre fileiras de pinos</td></tr>
<tr><td><code>pinos.diametro_pad</code></td><td>float</td><td>Diâmetro do pad de cobre</td></tr>
<tr><td><code>pinos.diametro_furo</code></td><td>float</td><td>Diâmetro do furo (drill)</td></tr>
</table>

<h2>1.4 <span class="badge badge-smd">SMD</span> dual_smd</h2>
<p>Encapsulamentos SMD de dois lados (SOIC, SOP, SSOP, TSSOP, SOT-23).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.total</code></td><td>int</td><td>Número total de pinos (par)</td></tr>
<tr><td><code>pinos.pitch</code></td><td>float</td><td>Espaçamento entre pinos</td></tr>
<tr><td><code>corpo.afastamento_colunas</code></td><td>float</td><td>Distância centro-centro entre lados opostos</td></tr>
<tr><td><code>pinos.tamanho_pad.largura</code></td><td>float</td><td>Extensão perpendicular à borda (comprimento do pad)</td></tr>
<tr><td><code>pinos.tamanho_pad.altura</code></td><td>float</td><td>Extensão paralela à borda (largura do pad)</td></tr>
</table>

<h2>1.5 <span class="badge badge-smd">SMD</span> quad_smd</h2>
<p>Encapsulamentos SMD de quatro lados (QFP, TQFP, LQFP, QFN).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.total</code></td><td>int</td><td>Número total de pinos (múltiplo de 4)</td></tr>
<tr><td><code>pinos.pitch</code></td><td>float</td><td>Espaçamento entre pinos</td></tr>
<tr><td><code>pinos.afastamento</code></td><td>float</td><td>Centro-centro entre lados opostos</td></tr>
<tr><td><code>pinos.tamanho_pad.largura</code></td><td>float</td><td>Extensão perpendicular à borda</td></tr>
<tr><td><code>pinos.tamanho_pad.altura</code></td><td>float</td><td>Extensão paralela à borda</td></tr>
<tr><td><code>pinos.lados</code></td><td>dict</td><td>Pinos por lado: <code>{{esquerdo, base, direito, topo}}</code></td></tr>
</table>

<h2>1.6 <span class="badge badge-smd">SMD</span> custom</h2>
<p>Componentes com layout de pinos personalizado (conectores, módulos).</p>
<table>
<tr><th>Campo</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos</code></td><td>list</td><td>Lista de dicts com <code>{{x, y, tipo, nome, ...}}</code></td></tr>
<tr><td><code>contorno</code></td><td>list</td><td>Lista de pontos <code>[x, y]</code> do contorno</td></tr>
</table>

<h2>1.7 <span class="badge badge-bga">BGA</span> bga</h2>
<p>Ball Grid Array (BGA, CSP, LGA).</p>
<table>
<tr><th>Campo YAML</th><th>Tipo</th><th>Descrição</th></tr>
<tr><td><code>pinos.linhas</code> / <code>pinos.colunas</code></td><td>int</td><td>Número de linhas / colunas do grid</td></tr>
<tr><td><code>pinos.pitch</code></td><td>float</td><td>Espaçamento entre esferas</td></tr>
<tr><td><code>pinos.diametro_pad</code></td><td>float</td><td>Diâmetro da esfera / pad</td></tr>
<tr><td><code>pinos.excluir</code></td><td>list</td><td>Lista de posições removidas (ex: <code>["A1", "B2"]</code>)</td></tr>
</table>

<hr>

<!-- ======================================================= -->
<!-- 2. CAMPOS YAML COMUNS -->
<!-- ======================================================= -->
<h1 id="yaml-fields">2. Campos YAML Comuns</h1>
<p>Campos compartilhados por todos os padrões de footprint.</p>

<table>
<tr><th>Campo</th><th>Tipo</th><th>Obrigatório</th><th>Descrição</th></tr>
<tr><td><code>nome</code></td><td>str</td><td>✅</td><td>Nome do componente (usado como nome do arquivo)</td></tr>
<tr><td><code>formato</code></td><td>str</td><td>✅</td><td>Padrão do footprint (um dos 7 listados acima)</td></tr>
<tr><td><code>descricao</code></td><td>str</td><td>—</td><td>Descrição textual do componente</td></tr>
<tr><td><code>fabricante</code></td><td>str</td><td>—</td><td>Nome do fabricante</td></tr>
<tr><td><code>part_number</code></td><td>str</td><td>—</td><td>Part number do fabricante</td></tr>
<tr><td><code>datasheet</code></td><td>str</td><td>—</td><td>URL do datasheet</td></tr>
<tr><td><code>num_pinos</code></td><td>int</td><td>✅*</td><td>Total de pinos (* exceto custom)</td></tr>
<tr><td><code>pitch</code></td><td>float</td><td>✅*</td><td>Espaçamento entre pinos (mm)</td></tr>
<tr><td><code>corpo</code></td><td>dict</td><td>—</td><td>Dimensões do corpo: <code>{{w, h, height}}</code></td></tr>
<tr><td><code>silkscreen</code></td><td>dict</td><td>—</td><td>Config. do silkscreen: <code>{{ref, value, pino1}}</code></td></tr>
<tr><td><code>courtyard</code></td><td>dict</td><td>—</td><td>Margem do courtyard: <code>{{margin}}</code></td></tr>
<tr><td><code>mascara</code></td><td>dict</td><td>—</td><td>Expansão da máscara de solda</td></tr>
<tr><td><code>pasta</code></td><td>dict</td><td>—</td><td>Expansão da máscara de pasta</td></tr>
<tr><td><code>modelo_3d</code></td><td>dict</td><td>—</td><td>Config. do modelo STEP: <code>{{gerar, escala, offset, rotacao}}</code></td></tr>
<tr><td><code>simbolo</code></td><td>str</td><td>—</td><td>Template de símbolo esquemático (auto-detectado se omitido)</td></tr>
</table>

<div class="tip">💡 Campos marcados com ✅* são obrigatórios para a maioria dos padrões, mas podem ser opcionais em <code>custom</code>.</div>

<hr>

<!-- ======================================================= -->
<!-- 3. CAMPO SIMBOLO -->
<!-- ======================================================= -->
<h1 id="simbolo-ref">3. Campo <code>simbolo:</code> — Templates de Símbolo Esquemático</h1>
<p>O campo <code>simbolo:</code> define o visual do símbolo <code>.kicad_sym</code>. Se omitido, o sistema auto-detecta pelo <code>tipo:</code>, <code>padrao:</code> e número de pinos.</p>

<table>
<tr><th>Valor</th><th>Visual</th><th>Pinos</th></tr>
<tr><td><code>resistor</code></td><td>Retângulo horizontal passivo</td><td>2</td></tr>
<tr><td><code>capacitor</code></td><td>Duas placas paralelas</td><td>2</td></tr>
<tr><td><code>diodo</code></td><td>Triângulo + barra catodo</td><td>2 (A/K)</td></tr>
<tr><td><code>diodo_zener</code></td><td>Diodo + barra Z</td><td>2 (A/K)</td></tr>
<tr><td><code>diodo_schottky</code></td><td>Diodo + barra S</td><td>2 (A/K)</td></tr>
<tr><td><code>led</code></td><td>Diodo + setas de luz</td><td>2 (A/K)</td></tr>
<tr><td><code>transistor</code></td><td>NPN BJT com círculo</td><td>3 (B/C/E)</td></tr>
<tr><td><code>mosfet_n</code></td><td>MOSFET canal N</td><td>3 (G/D/S)</td></tr>
<tr><td><code>mosfet_p</code></td><td>MOSFET canal P</td><td>3 (G/D/S)</td></tr>
<tr><td><code>regulador</code></td><td>Retângulo IN/GND/OUT</td><td>3</td></tr>
<tr><td><code>opamp</code></td><td>Triângulo op-amp</td><td>3-5</td></tr>
<tr><td><code>indutor</code></td><td>Bobina (4 arcos)</td><td>2</td></tr>
<tr><td><code>fusivel</code></td><td>Retângulo com fio</td><td>2</td></tr>
<tr><td><code>bateria</code></td><td>Placas +/−</td><td>2</td></tr>
<tr><td><code>antena</code></td><td>V invertido</td><td>1</td></tr>
<tr><td><code>crystal</code></td><td>Cristal (barras + retângulo)</td><td>2</td></tr>
<tr><td><code>conector</code></td><td>Retângulo com pinos na esquerda</td><td>N</td></tr>
<tr><td><code>ci</code></td><td>CI genérico (2 lados)</td><td>N</td></tr>
<tr><td><code>bga</code></td><td>CI quadrado (4 lados)</td><td>N</td></tr>
</table>

<h3>Auto-detecção</h3>
<p>Se <code>simbolo:</code> não for especificado, o template é determinado automaticamente:</p>
<table>
<tr><th>Condição</th><th>Template selecionado</th></tr>
<tr><td>1 pino</td><td><code>antena</code></td></tr>
<tr><td>2 pinos</td><td><code>resistor</code> (passivo genérico)</td></tr>
<tr><td>3 pinos</td><td><code>regulador</code></td></tr>
<tr><td>4–40 pinos</td><td><code>ci</code> (2 lados)</td></tr>
<tr><td>40+ pinos</td><td><code>bga</code> (4 lados)</td></tr>
</table>

<div class="tip">💡 Especificar <code>simbolo:</code> explicitamente garante o desenho correto — ex: um diodo com 2 pinos seria auto-detectado como <code>resistor</code>, mas <code>simbolo: diodo</code> gera o triângulo correto.</div>

<hr>

<!-- ======================================================= -->
<!-- 4. REFERÊNCIA DE PINOS -->
<!-- ======================================================= -->
<h1 id="pin-ref">4. Referência de Pinos</h1>

<h2>3.1 Tipos de Pad</h2>
<table>
<tr><th>Valor</th><th>Descrição</th><th>Camadas</th></tr>
<tr><td><code>thru_hole</code></td><td>Furo passante com anel</td><td>F.Cu + B.Cu + *.Mask</td></tr>
<tr><td><code>smd</code></td><td>Pad SMD (superfície)</td><td>F.Cu + F.Mask + F.Paste</td></tr>
<tr><td><code>np_thru_hole</code></td><td>Furo não-plated (mecânico)</td><td>NPTH</td></tr>
<tr><td><code>connect</code></td><td>Pad para conexão mecânica</td><td>F.Cu</td></tr>
</table>

<h2>3.2 Formas de Pad</h2>
<table>
<tr><th>Valor</th><th>Descrição</th></tr>
<tr><td><code>circle</code></td><td>Circular</td></tr>
<tr><td><code>rect</code></td><td>Retangular</td></tr>
<tr><td><code>oval</code></td><td>Oval (oblongo)</td></tr>
<tr><td><code>roundrect</code></td><td>Retangular com cantos arredondados</td></tr>
<tr><td><code>trapezoid</code></td><td>Trapezoidal</td></tr>
<tr><td><code>custom</code></td><td>Forma customizada (polígono)</td></tr>
</table>

<h2>3.3 Funções Elétricas (Símbolo)</h2>
<table>
<tr><th>Valor</th><th>Sigla</th><th>Uso</th></tr>
<tr><td><code>input</code></td><td>I</td><td>Entrada de sinal</td></tr>
<tr><td><code>output</code></td><td>O</td><td>Saída de sinal</td></tr>
<tr><td><code>bidirectional</code></td><td>B</td><td>Entrada/saída bidirecional</td></tr>
<tr><td><code>tri_state</code></td><td>T</td><td>Saída tri-state</td></tr>
<tr><td><code>passive</code></td><td>P</td><td>Passivo (R, C, L)</td></tr>
<tr><td><code>power_in</code></td><td>W</td><td>Entrada de alimentação (VCC, VDD)</td></tr>
<tr><td><code>power_out</code></td><td>w</td><td>Saída de alimentação</td></tr>
<tr><td><code>unspecified</code></td><td>U</td><td>Não especificado</td></tr>
<tr><td><code>no_connect</code></td><td>N</td><td>Sem conexão (NC)</td></tr>
</table>

<hr>

<!-- ======================================================= -->
<!-- 4. ATALHOS DE TECLADO -->
<!-- ======================================================= -->
<h1 id="shortcuts">5. Atalhos de Teclado</h1>

<table>
<tr><th>Atalho</th><th>Ação</th></tr>
<tr><td><code>F1</code></td><td>Abrir/fechar painel de ajuda</td></tr>
<tr><td><code>F5</code></td><td>Gerar footprint, símbolo e modelo 3D</td></tr>
<tr><td><code>Ctrl+S</code></td><td>Salvar arquivo YAML</td></tr>
<tr><td><code>Ctrl+Shift+S</code></td><td>Salvar YAML como…</td></tr>
<tr><td><code>Ctrl+O</code></td><td>Abrir arquivo YAML</td></tr>
<tr><td><code>Ctrl+R</code></td><td>Recarregar YAML do disco</td></tr>
<tr><td><code>Ctrl+N</code></td><td>Novo componente</td></tr>
<tr><td><code>Ctrl+D</code></td><td>Duplicar componente</td></tr>
<tr><td><code>Ctrl+Z</code></td><td>Desfazer</td></tr>
<tr><td><code>Ctrl+Y</code></td><td>Refazer</td></tr>
<tr><td><code>Ctrl+G</code></td><td>Ir para linha</td></tr>
<tr><td><code>Ctrl+L</code></td><td>Alternar números de linha</td></tr>
<tr><td><code>Ctrl+E</code></td><td>Abrir editor de pinos</td></tr>
<tr><td><code>Ctrl+Shift+E</code></td><td>Exportar para biblioteca</td></tr>
<tr><td><code>Ctrl+Shift+V</code></td><td>Verificar YAML (validação)</td></tr>
</table>

<hr>

<!-- ======================================================= -->
<!-- 5. REGRAS IPC -->
<!-- ======================================================= -->
<h1 id="ipc">6. Regras de Validação IPC</h1>
<p>Resumo das verificações aplicadas automaticamente ao gerar o footprint.</p>

<h2>5.1 Padronização de Pads (IPC-7351)</h2>
<table>
<tr><th>Regra</th><th>Descrição</th></tr>
<tr><td>Anel mínimo</td><td>Anel de cobre ao redor do furo ≥ 0.15 mm (PTH)</td></tr>
<tr><td>Pad / Furo</td><td>Pad diameter ≥ drill + 0.5 mm (recomendado)</td></tr>
<tr><td>Pad SMD mín.</td><td>Largura e altura do pad SMD ≥ 0.2 mm</td></tr>
<tr><td>Pitch mínimo</td><td>Distância mínima entre centros de pads ≥ 0.4 mm</td></tr>
</table>

<h2>5.2 Courtyard (IPC-7351B)</h2>
<table>
<tr><th>Tipo</th><th>Margem mínima</th></tr>
<tr><td>Componentes gerais</td><td>0.25 mm</td></tr>
<tr><td>Componentes altos (&gt;10mm)</td><td>0.50 mm</td></tr>
<tr><td>BGA</td><td>1.00 mm</td></tr>
</table>

<h2>5.3 Silkscreen</h2>
<table>
<tr><th>Regra</th><th>Valor</th></tr>
<tr><td>Espessura mínima de linha</td><td>0.10 mm</td></tr>
<tr><td>Espessura recomendada</td><td>0.12 mm</td></tr>
<tr><td>Clearance para pads</td><td>≥ 0.20 mm</td></tr>
<tr><td>Marcação pino 1</td><td>Obrigatória para CI's</td></tr>
</table>

<h2>5.4 Validações da Plataforma</h2>
<table>
<tr><th>Verificação</th><th>Severidade</th><th>Descrição</th></tr>
<tr><td><code>nome</code> vazio</td><td style="color:{S['err']}">❌ Erro</td><td>O campo <code>nome</code> é obrigatório</td></tr>
<tr><td><code>formato</code> inválido</td><td style="color:{S['err']}">❌ Erro</td><td>Deve ser um dos 7 padrões suportados</td></tr>
<tr><td><code>num_pinos</code> ímpar (DIP/QFP)</td><td style="color:{S['err']}">❌ Erro</td><td>Padrões duais requerem número par de pinos</td></tr>
<tr><td><code>pitch</code> ≤ 0</td><td style="color:{S['err']}">❌ Erro</td><td>Pitch deve ser positivo</td></tr>
<tr><td><code>pad</code> maior que <code>pitch</code></td><td style="color:{S['warn']}">⚠️ Aviso</td><td>Pads podem se sobrepor</td></tr>
<tr><td><code>courtyard</code> ausente</td><td style="color:{S['warn']}">⚠️ Aviso</td><td>Margem padrão será usada</td></tr>
<tr><td>Modelo 3D ausente</td><td style="color:{S['muted']}">ℹ Info</td><td>STEP não será gerado</td></tr>
</table>

<hr>

<!-- ======================================================= -->
<!-- 6. EXEMPLOS RÁPIDOS -->
<!-- ======================================================= -->
<h1 id="examples">7. Exemplos Rápidos</h1>

<h2>6.1 SOIC-8 (dual_smd)</h2>
<pre>
nome: "MCP3008-SOIC8"
padrao: "dual_smd"

corpo:
  largura: 4.9
  comprimento: 3.9
  afastamento_colunas: 6.0

pinos:
  total: 8
  pitch: 1.27
  tamanho_pad:
    largura: 1.55
    altura: 0.6

kicad:
  referencia: "U?"
  valor: "MCP3008"
  descricao: "ADC 10-bit 8-channel SPI"
</pre>

<h2>6.2 DIP-14 (dual_pth)</h2>
<pre>
nome: "DIP14"
tipo: "ci_dip"

pinos:
  total: 14
  pitch: 2.54
  diametro_pad: 1.6
  diametro_furo: 0.8

corpo:
  largura: 6.35
  comprimento: 17.78
  afastamento_colunas: 7.62

kicad:
  referencia: "U?"
  valor: "DIP14"
</pre>

<h2>6.3 QFP-44 (quad_smd)</h2>
<pre>
nome: "TQFP44"
padrao: "quad_smd"

corpo:
  largura: 10.0
  altura: 10.0

pinos:
  total: 44
  pitch: 0.8
  afastamento: 12.0
  tamanho_pad:
    largura: 1.2
    altura: 0.4
  lados:
    esquerdo: 11
    base: 11
    direito: 11
    topo: 11
</pre>

<h2>6.4 BGA-256 (bga)</h2>
<pre>
nome: "BGA256_17x17"
padrao: "bga"

corpo:
  largura: 17.0
  comprimento: 17.0

pinos:
  linhas: 16
  colunas: 16
  pitch: 1.0
  diametro_pad: 0.5
  total: 256
  excluir: []
</pre>

<h2>6.5 Resistor Axial (axial_pth)</h2>
<pre>
nome: "R_Axial_470R"
tipo: "resistor_pth"

corpo:
  comprimento: 6.0
  diametro: 2.5

pinos:
  espacamento: 10.16
  diametro_pad: 1.8
  diametro_furo: 0.8
</pre>

<hr>

<p style="text-align:center; color:{S['muted']}; font-size:11px; margin-top:20px;">
  EDA Footprint Generator &mdash; Pressione <code>F1</code> para abrir/fechar &mdash; v{__version__}
</p>

</body></html>'''

    # -----------------------------------------------------------------
    # Busca
    # -----------------------------------------------------------------
    def search(self, text: str):
        """Busca e destaca texto no navegador HTML."""
        if not text:
            # Limpar seleção anterior
            self.browser.find('')
            return
        # QTextDocument::FindFlags — busca sem case-sensitivity
        self.browser.find(text)
