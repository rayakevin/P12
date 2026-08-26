"""Extrait des actualités françaises avec images depuis NewsData.io."""

import argparse
import logging
import os

import requests
from dotenv import load_dotenv

from common import (
    DATA_DIR,
    PROJECT_ROOT,
    configure_logging,
    create_http_session,
    download_image,
    relative_path,
    save_json_records,
)


API_URL = "https://newsdata.io/api/1/latest"
IMAGES_DIR = DATA_DIR / "images" / "newsdata"


def extract_newsdata(
    api_key: str,
    limit: int,
    max_pages: int,
    query: str | None,
    logger: logging.Logger,
) -> list[dict]:
    """Récupère et sauvegarde en mémoire jusqu'à ``limit`` articles multimodaux."""
    records: list[dict] = []
    page_token: str | None = None
    seen_tokens: set[str] = set()

    with create_http_session() as session:
        for page_number in range(1, max_pages + 1):
            params: dict[str, str | int] = {
                "apikey": api_key,
                "language": "fr",
                "country": "fr",
                "category": "politics",
                "image": 1,
                "removeduplicate": 1,
                "size": 10,
            }
            if query:
                params["q"] = query
            if page_token:
                params["page"] = page_token

            response = session.get(API_URL, params=params, timeout=(5, 30))
            response.raise_for_status()
            payload = response.json()
            articles = payload.get("results", [])
            logger.info("Page %s : %s articles reçus", page_number, len(articles))

            for article in articles:
                if len(records) >= limit:
                    break

                article_id = str(article.get("article_id") or "").strip()
                image_url = str(article.get("image_url") or "").strip()
                title = str(article.get("title") or "").strip()
                description = str(article.get("description") or "").strip()

                if not article_id or not image_url or not (title or description):
                    logger.warning("Article incomplet ignoré : %s", article_id or "sans id")
                    continue

                try:
                    image_path, image_size, downloaded = download_image(
                        session,
                        image_url,
                        f"newsdata_{article_id}",
                        IMAGES_DIR,
                    )
                except (requests.RequestException, OSError, ValueError, RuntimeError) as error:
                    logger.warning("Image ignorée pour %s : %s", article_id, error)
                    continue

                # On conserve l'objet API brut et on ajoute seulement les infos d'extraction.
                record = dict(article)
                record["_image_path"] = relative_path(image_path)
                record["_image_size"] = image_size
                records.append(record)
                logger.info(
                    "Article %s prêt (%s)",
                    article_id,
                    "téléchargé" if downloaded else "déjà présent",
                )

            if len(records) >= limit:
                break

            next_token = payload.get("nextPage")
            if not next_token:
                break
            if next_token in seen_tokens:
                raise RuntimeError("NewsData.io a renvoyé un jeton de page déjà traité.")

            seen_tokens.add(next_token)
            page_token = next_token

    if not records:
        raise RuntimeError("Aucun article texte-image n'a pu être extrait.")
    return records


def parse_args() -> argparse.Namespace:
    """Lit les paramètres configurables depuis la ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--query", default=None)
    return parser.parse_args()


def main() -> None:
    """Point d'entrée autonome du script."""
    args = parse_args()
    logger = configure_logging("newsdata")

    try:
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("NEWSDATA_API_KEY")
        if not api_key:
            raise RuntimeError("La variable NEWSDATA_API_KEY est absente.")
        if args.limit < 1 or args.max_pages < 1:
            raise ValueError("--limit et --max-pages doivent être positifs.")

        records = extract_newsdata(
            api_key,
            args.limit,
            args.max_pages,
            args.query,
            logger,
        )
        output_path = save_json_records(records, "newsdata")
        logger.info("Extraction terminée : %s articles dans %s", len(records), output_path)
    except Exception:
        logger.exception("Échec de l'extraction NewsData.io")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
