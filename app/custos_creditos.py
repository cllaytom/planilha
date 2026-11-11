from decimal import Decimal


def custo_da_operacao(nome, controlar, regra, custo, dias):
    """Retorna custo monetario; nao movimenta quantidades de estoque."""
    if nome.strip().casefold() == "internet" and dias != 30:
        return Decimal("0.00")
    if not controlar or regra == 0:
        return Decimal("0.00")
    if regra == 2 and dias != 30:
        return Decimal("0.00")
    valor = Decimal(str(custo)).quantize(Decimal("0.01"))
    if valor <= 0:
        raise ValueError("Informe um custo por credito maior que zero em Produtos.")
    return valor
