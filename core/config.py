# =============================================================================
# core/config.py
# Configurações persistentes da plataforma CAM-CAD Data Frontier.
# Usa QSettings para salvar preferências do usuário entre sessões.
# =============================================================================

from PyQt5.QtCore import QSettings


# Valores padrão de configuração
_DEFAULTS = {
    'grid/size':                  0.5,        # mm
    'viewer/background':          '#1A1A2E',
    'editor/font_size':           11,
    'output/directory':           'saida',
    'general/auto_generate':      True,
    'general/auto_save_interval': 2000,       # ms
}


class AppConfig:
    """Gerenciador centralizado de configurações persistentes."""

    _s = QSettings('DataFrontier', 'CAM-CAD')

    @classmethod
    def get(cls, key, default=None):
        """Retorna o valor salvo para *key*, ou *default* (ou o padrão interno)."""
        if default is None:
            default = _DEFAULTS.get(key)
        val = cls._s.value(key, default)
        # QSettings pode retornar strings para booleans — corrigir
        if isinstance(val, str):
            if val.lower() == 'true':
                return True
            if val.lower() == 'false':
                return False
            # Tentar converter para número
            try:
                if '.' in val:
                    return float(val)
                return int(val)
            except (ValueError, TypeError):
                pass
        return val

    @classmethod
    def set(cls, key, value):
        """Grava *value* para *key* persistentemente."""
        cls._s.setValue(key, value)

    @classmethod
    def defaults(cls):
        """Retorna cópia do dicionário de valores padrão."""
        return dict(_DEFAULTS)

    @classmethod
    def reset(cls, key=None):
        """Restaura um *key* (ou todos) para o valor padrão."""
        if key is not None:
            if key in _DEFAULTS:
                cls._s.setValue(key, _DEFAULTS[key])
        else:
            for k, v in _DEFAULTS.items():
                cls._s.setValue(k, v)

    @classmethod
    def sync(cls):
        """Força a gravação das configurações em disco."""
        cls._s.sync()
