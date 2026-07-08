"""Parser de S-Expressions para formatos KiCad (.kicad_mod, .kicad_sym).

Funções utilitárias para parsear e consultar árvores S-Expression usadas
nos formatos de arquivo do KiCad. Usado internamente pelos módulos de
exportação (Altium, Eagle, etc.).
"""


def parse_sexpr(text):
    """Parseia texto S-Expression em listas Python aninhadas.

    Trata strings entre aspas, tokens simples e parênteses aninhados.

    Args:
        text: Conteúdo S-Expression como string.

    Returns:
        Lista aninhada representando a árvore S-Expression.
        Se houver apenas um nó raiz, retorna esse nó diretamente.
    """
    tokens = []
    i = 0
    length = len(text)

    while i < length:
        c = text[i]
        if c in ' \t\n\r':
            i += 1
        elif c == '(':
            tokens.append('(')
            i += 1
        elif c == ')':
            tokens.append(')')
            i += 1
        elif c == '"':
            j = i + 1
            while j < length and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            tokens.append(text[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < length and text[j] not in ' \t\n\r()':
                j += 1
            tokens.append(text[i:j])
            i = j

    def _build(idx):
        result = []
        while idx < len(tokens):
            tok = tokens[idx]
            if tok == '(':
                sub, idx = _build(idx + 1)
                result.append(sub)
            elif tok == ')':
                return result, idx + 1
            else:
                result.append(tok)
                idx += 1
        return result, idx

    tree, _ = _build(0)
    return tree[0] if len(tree) == 1 else tree


def find_all(sexpr, tag):
    """Encontra todas as sub-expressões que começam com ``tag``.

    Busca recursiva na árvore S-Expression.

    Args:
        sexpr: Árvore S-Expression (lista aninhada).
        tag:   Nome do nó a buscar (ex: ``'pad'``, ``'fp_line'``).

    Returns:
        Lista de sub-expressões encontradas.
    """
    results = []
    if isinstance(sexpr, list):
        if len(sexpr) > 0 and sexpr[0] == tag:
            results.append(sexpr)
        for item in sexpr:
            results.extend(find_all(item, tag))
    return results


def find_one(sexpr, tag):
    """Encontra a primeira sub-expressão que começa com ``tag``.

    Args:
        sexpr: Árvore S-Expression (lista aninhada).
        tag:   Nome do nó a buscar.

    Returns:
        Sub-expressão encontrada ou ``None``.
    """
    all_found = find_all(sexpr, tag)
    return all_found[0] if all_found else None


def get_at(sexpr):
    """Extrai posição ``(at x y [angle])`` de uma sub-expressão.

    Args:
        sexpr: Sub-expressão contendo nó ``at``.

    Returns:
        Tupla ``(x, y, angle)`` com valores float. Padrão ``(0.0, 0.0, 0.0)``.
    """
    at = find_one(sexpr, 'at')
    if at is None:
        return 0.0, 0.0, 0.0
    x = float(at[1]) if len(at) > 1 else 0.0
    y = float(at[2]) if len(at) > 2 else 0.0
    angle = float(at[3]) if len(at) > 3 else 0.0
    return x, y, angle


def get_size(sexpr):
    """Extrai dimensão ``(size w h)`` de uma sub-expressão.

    Args:
        sexpr: Sub-expressão contendo nó ``size``.

    Returns:
        Tupla ``(w, h)`` com valores float. Padrão ``(1.0, 1.0)``.
    """
    size = find_one(sexpr, 'size')
    if size is None:
        return 1.0, 1.0
    w = float(size[1]) if len(size) > 1 else 1.0
    h = float(size[2]) if len(size) > 2 else 1.0
    return w, h


def get_attr(sexpr, key):
    """Obtém valor após chave em lista S-Expression: ``(... key value ...)`` → ``value``.

    Args:
        sexpr: Lista S-Expression.
        key:   Chave a buscar.

    Returns:
        Valor encontrado ou ``None``.
    """
    if not isinstance(sexpr, list):
        return None
    for i, item in enumerate(sexpr):
        if item == key and i + 1 < len(sexpr):
            return sexpr[i + 1]
    return None
