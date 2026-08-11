"""Usado no modo 'readonly': busca o snapshot JSON publicado pelo GitHub
Actions (via raw.githubusercontent.com) e importa no banco local, sem
nunca acessar livelo.com.br diretamente."""
import logging

import requests

import config
from data_export import import_from_dict

logger = logging.getLogger(__name__)


def sync_from_github(url: str | None = None, timeout: int = 20) -> dict:
    url = url or config.GITHUB_DATA_URL
    if not url:
        raise RuntimeError(
            "LIVELO_GITHUB_DATA_URL não está configurada. Defina essa variável de "
            "ambiente apontando para o raw.githubusercontent.com do seu "
            "data/livelo_export.json (veja o README)."
        )
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    stats = import_from_dict(data)
    logger.info("Sincronizado a partir do GitHub: %s", stats)
    return stats
