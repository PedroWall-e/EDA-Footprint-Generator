# -*- coding: utf-8 -*-
"""log_config — Configuração centralizada de logging da plataforma."""

import logging

_LOG_FORMAT = '[%(name)s] %(levelname)s: %(message)s'
_configured = False


def setup_logging(level=logging.INFO):
    """Configura o logging global da plataforma.

    Chamada uma vez em interface_dual.py (entry point).
    Os módulos individuais usam ``logging.getLogger(__name__)``.
    """
    global _configured
    if _configured:
        return
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Atalho para ``logging.getLogger(name)``."""
    return logging.getLogger(name)
