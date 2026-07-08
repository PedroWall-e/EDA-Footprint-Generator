# =============================================================================
# runner_stub.py
# Arquivo permanente carregado pelo CQ-Editor.
# A cada execucao (F5 ou debugger.render()), le e executa o
# gerador_universal.py ATUAL do disco — garantindo que modificacoes
# sejam sempre aplicadas sem precisar recarregar o editor.
# =============================================================================

import os as _os
import sys as _sys

_PROJ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_CORE = _os.path.join(_PROJ, 'core')
_GUI  = _os.path.join(_PROJ, 'gui')

# Garantir que core/ e gui/ estejam no sys.path para imports internos
for _p in [_PROJ, _CORE, _GUI]:
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

_GEN = _os.path.join(_CORE, 'gerador_universal.py')

if not _os.path.isfile(_GEN):
    raise FileNotFoundError(f"gerador_universal.py nao encontrado em: {_CORE}")

with open(_GEN, 'r', encoding='utf-8') as _f:
    _code = _f.read()

# Executa com os globals() atuais — show_object, debug, etc. do CQ-Editor
# estao disponiveis porque compartilhamos o mesmo espaco de nomes.
# Injetamos __file__ apontando para o gerador_universal.py real,
# para que os.path.dirname(__file__) resolva corretamente.
globals()['__file__'] = _GEN
exec(compile(_code, _GEN, 'exec'), globals())
