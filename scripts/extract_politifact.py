"""Extrait les fact-checks texte-image du flux RSS PolitiFact."""

import argparse
import hashlib
import logging

import feedparser
import requests

from common import (
    DATA_DIR,
    configure_logging,
    create_http_session,
    download_image,
    relative_path,
    save_json_records,
)


RSS_URL = "https://www.politifact.com/rss/factchecks/"
IMAGES_DIR = DATA_DIR / "images" / "politifact"


def make_image_id(entry_id: str) -> str:
    """Construit un nom de fichier stable à partir de l'identifiant RSS."""
    digest = hashlib.sha256(entry_id.encode("utf-8")).hexdigest()[:16]
    return f"politifact_{digest}"


def extract_politifact(
    limit: int,
    refresh_images: bool,
    logger: logging.Logger,
) -> list[dict]:
    """Récupère jusqu'à ``limit`` entrées RSS possédant texte et image."""
    records: list[dict] = []

    with create_http_session() as session:
        response = session.get(RSS_URL, timeout=(5, 30))
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        if feed.bozo:
            logger.warning("Flux XML imparfait mais lisible : %s", feed.bozo_exception)
        if not feed.entries:
            raise RuntimeError("Le flux PolitiFact ne contient aucune entrée.")

        logger.info("%s entrées RSS reçues", len(feed.entries))

        for entry in feed.entries:
            if len(records) >= limit:
                break

            entry_id = str(entry.get("id") or entry.get("link") or "").strip()
            content_items = entry.get("content", [])
            content_html = (
                content_items[0].get("value", "") if content_items else ""
            )
            thumbnails = entry.get("media_thumbnail", [])
            image_url = thumbnails[0].get("url", "") if thumbnails else ""

            if not entry_id or not image_url or not (entry.get("summary") or content_html):
                logger.warning("Entrée RSS incomplète ignorée : %s", entry_id or "sans id")
                continue

            try:
                image = download_image(
                    session,
                    image_url,
                    make_image_id(entry_id),
                    IMAGES_DIR,
                    refresh_existing=refresh_images,
                )
            except (requests.RequestException, OSError, ValueError, RuntimeError) as error:
                logger.warning("Image ignorée pour %s : %s", entry_id, error)
                continue

            # Feedparser contient aussi des objets non sérialisables : seuls les champs bruts utiles sont gardés.
            records.append({
                "id": entry_id,
                "title": entry.get("title"),
                "link": entry.get("link"),
                "summary": entry.get("summary"),
                "content_html": content_html,
                "published": entry.get("published"),
                "author": entry.get("author"),
                "image_url": image_url,
                "_image_path": relative_path(image.path),
                "_image_size": image.size_bytes,
                "_image_sha256": image.sha256,
                "_downloaded_from_url": image.source_url,
                "_image_provenance_status": image.provenance_status,
            })
            logger.info(
                "Fact-check prêt : %s (%s, provenance=%s)",
                entry_id,
                "téléchargé" if image.downloaded else "déjà présent",
                image.provenance_status,
            )

    if not records:
        raise RuntimeError("Aucun fact-check texte-image n'a pu être extrait.")
    return records


def parse_args() -> argparse.Namespace:
    """Lit la limite d'entrées depuis la ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Retélécharge les images même si une copie locale existe.",
    )
    return parser.parse_args()


def main() -> None:
    """Point d'entrée autonome du script."""
    args = parse_args()
    logger = configure_logging("politifact")

    try:
        if args.limit < 1:
            raise ValueError("--limit doit être positif.")
        records = extract_politifact(args.limit, args.refresh_images, logger)
        output_path = save_json_records(records, "politifact")
        logger.info("Extraction terminée : %s entrées dans %s", len(records), output_path)
    except Exception:
        logger.exception("Échec de l'extraction PolitiFact")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
