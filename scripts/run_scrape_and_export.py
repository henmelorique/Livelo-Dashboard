"""
Script standalone rodado pelo GitHub Actions (não usa Flask nem agendador).

Fluxo:
1. Se já existe um snapshot anterior em data/livelo_export.json (commitado
   no repo em execuções passadas), importa ele num banco local vazio —
   isso preserva o histórico completo entre execuções, já que o runner do
   GitHub Actions é efêmero (começa do zero a cada vez).
2. Roda o scraper de verdade contra livelo.com.br e grava um novo snapshot
   do dia no histórico.
3. Exporta o banco inteiro (com o novo snapshot já incluído) de volta para
   data/livelo_export.json — o workflow então faz commit desse arquivo.

Uso: python scripts/run_scrape_and_export.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Evita que a importação de app.py também crie e inicie a instância padrão
# (com agendador/sync automático) — este script controla sua própria
# instância explicitamente, com start_scheduler=False.
os.environ["LIVELO_SKIP_AUTOSTART"] = "1"

from app import create_app  # noqa: E402
from data_export import export_to_json, import_from_dict  # noqa: E402
from ingest import ingest_once  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PATH = os.path.join(REPO_ROOT, "data", "livelo_export.json")


def main() -> None:
    # start_scheduler=False: aqui é um script de execução única, não o
    # servidor web — não queremos agendador nem sync em background.
    app = create_app(start_scheduler=False)

    with app.app_context():
        if os.path.exists(EXPORT_PATH):
            with open(EXPORT_PATH, "r", encoding="utf-8") as f:
                previous = json.load(f)
            stats = import_from_dict(previous)
            print(f"[1/3] Snapshot anterior importado: {stats}")
        else:
            print("[1/3] Nenhum snapshot anterior encontrado (primeira execução).")

        log = ingest_once()
        print(
            f"[2/3] Coleta concluída: status={log.status} "
            f"encontrados={log.partners_found} novos={log.partners_new} "
            f"alterados={log.partners_changed}"
        )
        if log.status != "success":
            print(f"ERRO na coleta: {log.error_message}")
            sys.exit(1)

        os.makedirs(os.path.dirname(EXPORT_PATH), exist_ok=True)
        export_to_json(EXPORT_PATH)
        print(f"[3/3] Snapshot exportado para {EXPORT_PATH}")


if __name__ == "__main__":
    main()
