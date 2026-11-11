from datetime import date, datetime, timedelta
import re
import unicodedata

EPOCA_EXCEL = datetime(1899, 12, 30)


def chave_header(valor) -> str:
    """Normaliza um cabecalho: remove acentos, espacos e pontuacao, deixa maiusculo.

    'For . Pagamento' -> 'FORPAGAMENTO'
    '2º USUARIO'      -> '2OUSUARIO'
    """
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]", "", texto).upper()


def limpar(valor):
    """Remove vazios e artefatos comuns da planilha ('-', '0xf', etc.)."""
    if valor is None:
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        if texto in ("", "-", "0xf", "None", "#N/D", "#VALOR!", "#REF!"):
            return None
        return texto
    return valor


def como_texto(valor):
    valor = limpar(valor)
    return None if valor is None else str(valor).strip()


def como_float(valor, padrao=0.0):
    valor = limpar(valor)
    if valor is None:
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return padrao


def como_int(valor, padrao=None):
    valor = limpar(valor)
    if valor is None:
        return padrao
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return padrao


def excel_para_data(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)):
        if float(valor) <= 0:
            return None
        try:
            return (EPOCA_EXCEL + timedelta(days=float(valor))).date()
        except OverflowError:
            return None
    texto = str(valor).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return None


def serializar(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def situacao(vencimento: date | None, status: str | None, hoje: date | None = None):
    """Situacao derivada da assinatura + dias em atraso (negativo = dias restantes)."""
    hoje = hoje or date.today()
    status = (status or "").strip().upper()
    if status in ("CANCELADO", "CANCELADA"):
        return "cancelada", None
    if status == "SUSPENSO":
        return "suspensa", None
    if status == "INATIVO":
        return "inativa", None
    if vencimento is None:
        return "sem_vencimento", None
    dias = (vencimento - hoje).days
    if dias < 0:
        return "vencida", -dias
    if dias == 0:
        return "vence_hoje", 0
    if dias <= 7:
        return "vencendo", dias
    return "ativa", dias
