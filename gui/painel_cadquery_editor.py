# -*- coding: utf-8 -*-
"""
painel_cadquery_editor.py — Editor/visualizador de código CadQuery.

Janela QDialog para visualizar e editar o código CadQuery gerado pelo
template 3D ou código customizado armazenado no campo modelo_3d_python
do YAML.
"""

import sys
import yaml
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QWidget, QMessageBox, QApplication
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from widgets_common import PythonHighlighter, CodeEditor


# =========================================================================
# Diálogo principal
# =========================================================================

class CadQueryEditorDialog(QDialog):
    """
    Janela para visualizar e editar código CadQuery.

    Parameters
    ----------
    dados : dict
        Dicionário carregado do YAML do componente.
    filepath : str
        Caminho absoluto do arquivo YAML de origem.
    parent : QWidget, optional
        Widget pai.
    """

    def __init__(self, dados: dict, filepath: str, parent=None):
        super().__init__(parent)
        self.dados = dados
        self.filepath = filepath
        self.fonte = ""

        self.setWindowTitle("CadQuery Editor")
        self.setMinimumSize(800, 600)
        self._setup_ui()
        self._load_code()

    # -----------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Status bar ──────────────────────────────────────────────
        self.status_label = QLabel()
        self.status_label.setFixedHeight(32)
        self.status_label.setStyleSheet(
            "QLabel {"
            "  background: #181825;"
            "  color: #CDD6F4;"
            "  padding: 0 12px;"
            "  font-size: 12px;"
            "  border-bottom: 1px solid #313244;"
            "}"
        )
        layout.addWidget(self.status_label)

        # ── Editor de código ────────────────────────────────────────
        self.editor = CodeEditor()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setTabStopDistance(
            self.editor.fontMetrics().horizontalAdvance(" ") * 4
        )
        self.editor.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #1E1E2E;"
            "  color: #CDD6F4;"
            "  border: none;"
            "  selection-background-color: #45475A;"
            "  selection-color: #CDD6F4;"
            "}"
        )
        self._highlighter = PythonHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        # ── Barra de botões ─────────────────────────────────────────
        btn_bar = QWidget()
        btn_bar.setFixedHeight(48)
        btn_bar.setStyleSheet(
            "QWidget {"
            "  background: #181825;"
            "  border-top: 1px solid #313244;"
            "}"
        )
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 6, 12, 6)
        btn_layout.setSpacing(8)

        btn_style = (
            "QPushButton {"
            "  background: #313244;"
            "  color: #CDD6F4;"
            "  border: 1px solid #45475A;"
            "  border-radius: 4px;"
            "  padding: 6px 16px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  background: #45475A;"
            "}"
            "QPushButton:pressed {"
            "  background: #585B70;"
            "}"
        )

        self.btn_salvar = QPushButton("💾 Salvar no YAML")
        self.btn_testar = QPushButton("▶️ Testar")
        self.btn_resetar = QPushButton("🔄 Resetar")
        self.btn_fechar = QPushButton("❌ Fechar")

        for btn in (self.btn_salvar, self.btn_testar,
                    self.btn_resetar, self.btn_fechar):
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        layout.addWidget(btn_bar)

        # ── Conexões ────────────────────────────────────────────────
        self.btn_salvar.clicked.connect(self._on_salvar)
        self.btn_testar.clicked.connect(self._on_testar)
        self.btn_resetar.clicked.connect(self._on_resetar)
        self.btn_fechar.clicked.connect(self.close)

    # -----------------------------------------------------------------
    # Carregar código
    # -----------------------------------------------------------------

    def _load_code(self):
        codigo = self.dados.get("modelo_3d_python", "")
        if codigo:
            self.fonte = "customizado"
            self.editor.setPlainText(str(codigo))
        else:
            self.fonte = self.dados.get("tipo", "desconhecido")
            self.editor.setPlainText(
                f'# Template "{self.fonte}" — código gerado automaticamente.\n'
                f'# Para customizar, escreva seu código CadQuery aqui e salve.\n'
                f'#\n'
                f'# Variáveis disponíveis:\n'
                f'#   cq, show_object, dados, nome, os, math\n'
            )

        # Atualizar status
        if self.fonte == "customizado":
            self.status_label.setText("📝  Fonte: Código customizado")
        else:
            self.status_label.setText(f"📐  Fonte: Template {self.fonte}")

    # -----------------------------------------------------------------
    # Ações dos botões
    # -----------------------------------------------------------------

    def _on_salvar(self):
        """Salva o código atual no campo modelo_3d_python do YAML."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                conteudo = yaml.safe_load(f)

            conteudo["modelo_3d_python"] = self.editor.toPlainText()

            with open(self.filepath, "w", encoding="utf-8") as f:
                yaml.dump(conteudo, f, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)

            self.fonte = "customizado"
            self.status_label.setText("📝  Fonte: Código customizado")

            QMessageBox.information(
                self, "Salvo",
                "Código CadQuery salvo no YAML com sucesso."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro ao salvar",
                f"Não foi possível salvar:\n{e}"
            )

    def _on_testar(self):
        """Placeholder — orienta o usuário a usar o CQ-Editor."""
        QMessageBox.information(
            self, "Testar código",
            "Execute no CQ-Editor para visualizar o modelo 3D.\n\n"
            "1. Salve o código no YAML (💾)\n"
            "2. Abra o CQ-Editor\n"
            "3. Gere o modelo 3D pela interface principal"
        )

    def _on_resetar(self):
        """Remove o campo modelo_3d_python do YAML e recarrega."""
        reply = QMessageBox.question(
            self, "Confirmar reset",
            "Isso removerá o código customizado do YAML.\n"
            "O template padrão será usado novamente.\n\nContinuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                conteudo = yaml.safe_load(f)

            if "modelo_3d_python" in conteudo:
                del conteudo["modelo_3d_python"]
                with open(self.filepath, "w", encoding="utf-8") as f:
                    yaml.dump(conteudo, f, allow_unicode=True,
                              default_flow_style=False, sort_keys=False)

            # Recarregar dados e código
            self.dados = conteudo
            self._load_code()

            QMessageBox.information(
                self, "Resetado",
                "Código customizado removido. Template padrão restaurado."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro ao resetar",
                f"Não foi possível resetar:\n{e}"
            )


# =========================================================================
# Execução standalone (para teste)
# =========================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Dados de exemplo para teste
    dados_teste = {
        "nome": "TestComponent",
        "tipo": "diodo_pth",
        "corpo": {"comprimento": 5.0, "diametro": 2.0},
        "pinos": {"espacamento": 10.0, "diametro_pad": 1.8,
                  "diametro_furo": 0.8},
    }

    dialog = CadQueryEditorDialog(
        dados=dados_teste,
        filepath="modulos_config/_template.yaml"
    )
    dialog.show()
    sys.exit(app.exec_())
