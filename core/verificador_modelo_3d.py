"""
Verificador de modelo 3D referenciado pelo footprint.

Confere se o caminho declarado em `(model ...)` dentro do .kicad_mod aponta
para um arquivo que existe de fato. Um `.step` órfão (referenciado mas
inexistente) não gera erro nenhum no KiCad: o footprint abre normal e o
visualizador 3D simplesmente mostra nada. É falha silenciosa — o footprint
"gerou sem erro" e mesmo assim está errado.

Variáveis de ambiente do KiCad (${KIPRJMOD}, ${KICAD9_3DMODEL_DIR}, ...):
o caminho só é checado quando dá para resolver a variável. Variável não
resolvida vira NAO_VERIFICAVEL, nunca "arquivo não existe" — acusar ausência
de um arquivo cujo caminho não se conhece seria falso positivo.
"""

import os
import re

# ${KIPRJMOD} é a pasta do .kicad_pro. O gerador emite o .step ao lado do
# .kicad_mod, então a pasta do próprio .kicad_mod é a resolução correta aqui.
_VAR_PROJETO = 'KIPRJMOD'

_RE_MODEL = re.compile(r'\(model\s+("([^"]*)"|([^\s)]+))')
_RE_VAR = re.compile(r'\$\{([^}]+)\}|\$\(([^)]+)\)')

# Status possíveis por referência de modelo
OK = 'ok'
AUSENTE = 'ausente'
NAO_VERIFICAVEL = 'nao_verificavel'


class ResultadoModelo3D:
    """Resultado da verificação dos modelos 3D de um footprint.

    referencias: lista de dicts com {caminho_bruto, caminho_resolvido,
                 status, variaveis_nao_resolvidas, detalhe}
    """

    def __init__(self, caminho_footprint):
        self.caminho_footprint = caminho_footprint
        self.referencias = []

    @property
    def ok(self):
        """Falso apenas quando há modelo comprovadamente ausente."""
        return not self.ausentes

    @property
    def ausentes(self):
        return [r for r in self.referencias if r['status'] == AUSENTE]

    @property
    def nao_verificaveis(self):
        return [r for r in self.referencias if r['status'] == NAO_VERIFICAVEL]

    @property
    def resolvidos(self):
        return [r for r in self.referencias if r['status'] == OK]

    def __repr__(self):
        return (f'ResultadoModelo3D(refs={len(self.referencias)}, '
                f'ok={len(self.resolvidos)}, ausentes={len(self.ausentes)}, '
                f'nao_verificaveis={len(self.nao_verificaveis)})')

    def __str__(self):
        linhas = []
        for r in self.referencias:
            if r['status'] == AUSENTE:
                linhas.append(
                    f'ERRO 3D: modelo referenciado nao existe: '
                    f'{r["caminho_bruto"]} -> {r["caminho_resolvido"]}')
            elif r['status'] == NAO_VERIFICAVEL:
                vs = ', '.join(r['variaveis_nao_resolvidas'])
                linhas.append(
                    f'INFO 3D: nao verificavel (variavel {vs} nao definida no '
                    f'ambiente): {r["caminho_bruto"]}')
            else:
                linhas.append(f'INFO 3D: modelo OK: {r["caminho_resolvido"]}')
        if not self.referencias:
            linhas.append('INFO 3D: footprint nao referencia modelo 3D')
        return '\n'.join(linhas)


def extrair_referencias_modelo(conteudo_kicad_mod):
    """Extrai os caminhos declarados em `(model ...)`, na ordem do arquivo."""
    achados = []
    for m in _RE_MODEL.finditer(conteudo_kicad_mod):
        achados.append(m.group(2) if m.group(2) is not None else m.group(3))
    return achados


def resolver_caminho_modelo(caminho_bruto, dir_footprint):
    """Expande as variáveis do caminho.

    Retorna (caminho_resolvido_ou_None, variaveis_nao_resolvidas).
    ${KIPRJMOD} resolve para `dir_footprint`; as demais saem de os.environ.
    """
    nao_resolvidas = []

    def _sub(m):
        nome = m.group(1) or m.group(2)
        if nome == _VAR_PROJETO:
            return dir_footprint
        valor = os.environ.get(nome)
        if valor:
            return valor
        nao_resolvidas.append(nome)
        return m.group(0)

    resolvido = _RE_VAR.sub(_sub, caminho_bruto)
    if nao_resolvidas:
        return None, nao_resolvidas

    if not os.path.isabs(resolvido):
        resolvido = os.path.join(dir_footprint, resolvido)
    return os.path.normpath(resolvido), []


def verificar_modelo_3d(caminho_kicad_mod, dados=None):
    """Confere se os modelos 3D referenciados pelo footprint existem em disco.

    Args:
        caminho_kicad_mod: caminho do .kicad_mod já gerado.
        dados: dict do YAML (opcional; hoje só usado para contexto futuro).

    Returns:
        ResultadoModelo3D. `.ok` é False somente quando um modelo é
        comprovadamente ausente — caminho com variável não resolvida entra
        como NAO_VERIFICAVEL e não reprova.
    """
    res = ResultadoModelo3D(caminho_kicad_mod)

    with open(caminho_kicad_mod, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    dir_fp = os.path.dirname(os.path.abspath(caminho_kicad_mod))

    for bruto in extrair_referencias_modelo(conteudo):
        resolvido, nao_res = resolver_caminho_modelo(bruto, dir_fp)
        if nao_res:
            res.referencias.append({
                'caminho_bruto': bruto,
                'caminho_resolvido': None,
                'status': NAO_VERIFICAVEL,
                'variaveis_nao_resolvidas': nao_res,
                'detalhe': 'variavel de ambiente do KiCad nao definida',
            })
            continue
        existe = os.path.isfile(resolvido)
        res.referencias.append({
            'caminho_bruto': bruto,
            'caminho_resolvido': resolvido,
            'status': OK if existe else AUSENTE,
            'variaveis_nao_resolvidas': [],
            'detalhe': '' if existe else 'arquivo nao encontrado',
        })

    return res
