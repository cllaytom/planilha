import hashlib
import hmac
import re
import secrets


def hash_senha(senha):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', senha.encode(), bytes.fromhex(salt), 600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'


def conferir(senha, registro):
    try:
        algoritmo, n, salt, esperado = registro.split('$')
        if algoritmo != 'pbkdf2_sha256' or int(n) != 600000:
            return False
        atual = hashlib.pbkdf2_hmac('sha256', senha.encode(), bytes.fromhex(salt), int(n)).hex()
        return hmac.compare_digest(atual, esperado)
    except (ValueError, TypeError):
        return False


def permitido(papel, metodo, path):
    if papel == 'admin':
        return True
    if papel != 'usuario':
        return False
    if metodo == 'GET' and path in ('/clientes', '/senha', '/auth/me', '/auth/catalogo'):
        return True
    if metodo == 'POST' and path in ('/auth/senha', '/auth/logout', '/assinaturas'):
        return True
    if metodo == 'GET' and re.fullmatch(r'/assinaturas(?:/\d+)?', path):
        return True
    if metodo == 'PATCH' and re.fullmatch(r'/assinaturas/\d+', path):
        return True
    return bool(metodo == 'POST' and re.fullmatch(r'/assinaturas/\d+/(renovar|suspender)', path))
