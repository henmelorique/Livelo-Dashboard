"""Configuração central do projeto, via variáveis de ambiente.

MODOS:
- "full" (padrão, uso local): o app faz o scraping ele mesmo e roda o
  agendador diário (APScheduler). É o que você usa na sua máquina.
- "readonly" (uso em produção, ex.: PythonAnywhere): o app NUNCA acessa
  livelo.com.br diretamente. Em vez disso, ele lê um snapshot em JSON
  publicado no GitHub (gerado pelo GitHub Actions) via
  raw.githubusercontent.com — que é um domínio liberado até no plano
  gratuito da PythonAnywhere.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODE = os.environ.get("LIVELO_MODE", "full")  # "full" | "readonly"

DB_PATH = os.environ.get("LIVELO_DB_PATH", os.path.join(BASE_DIR, "instance", "livelo.db"))

SCRAPE_HOUR = int(os.environ.get("LIVELO_SCRAPE_HOUR", "7"))

# URL pública (raw.githubusercontent.com) do snapshot exportado pelo GitHub
# Actions. Só é usada no modo "readonly". Exemplo:
# https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/data/livelo_export.json
GITHUB_DATA_URL = os.environ.get("LIVELO_GITHUB_DATA_URL", "")
