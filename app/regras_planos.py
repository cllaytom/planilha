import math


def validar_campos(dados):
    d = dict(dados)
    if 'nome' in d:
        if not isinstance(d['nome'], str) or not 1 <= len(d['nome'].strip()) <= 80:
            raise ValueError('Nome deve ter entre 1 e 80 caracteres.')
        d['nome'] = d['nome'].strip()
    if 'produto' in d:
        if d['produto'] is not None and not isinstance(d['produto'], str):
            raise ValueError('Produto invalido.')
        d['produto'] = (d['produto'] or '').strip() or None
    for chave in ('valor', 'valor_custo'):
        if chave in d:
            v = d[chave]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError('Valor monetario deve ser finito e nao negativo.')
    for chave, limite in (('dias', 3650), ('conexoes', None)):
        if chave in d:
            v = d[chave]
            if type(v) is not int or v < 1 or (limite and v > limite):
                raise ValueError('Dias ou quantidade de acessos invalidos.')
    if 'ativo' in d and type(d['ativo']) is not bool:
        raise ValueError('Situacao ativa invalida.')
    return d
