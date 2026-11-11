import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # carrega .env local, se existir
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "dados"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'assinaturas.db').as_posix()}")

# Chave exigida no header X-API-Key. Troque em producao (variavel de ambiente API_KEY).
API_KEY = os.getenv("API_KEY", "dev-local-troque-esta-chave")

APP_NAME = "API de Assinaturas"
APP_VERSION = "0.1.0"
