"""Extrait des articles texte-image de The Conversation France."""

import argparse
import hashlib
import logging
import re
import time
from urllib.parse import urljoin, urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

from common import (
    DATA_DIR,
    configure_logging,
    create_http_session,
    download_image,
    relative_path,
    save_json_records,
)


FEED_URL = "https://theconversation.com/fr/articles.atom"
IMAGES_DIR = DATA_DIR / "images" / "theconversation"


def make_article_id(feed_id: str, article_url: str) -> str:
    """Retourne l'identifiant numérique de l'article ou un hash stable de son URL."""
    match = re.search(r"article/(\d+)$", feed_id) or re.search(
        r"-(\d+)(?:[/?#]|$)",
        article_url,
    )
    if match:
        return match.group(1)
    return hashlib.sha256(article_url.encode("utf-8")).hexdigest()[:16]


def meta_content(soup: BeautifulSoup, selector: str) -> str | None:
    """Lit et nettoie l'attribut content d'une balise meta."""
    tag = soup.select_one(selector)
    value = tag.get("content") if tag else None
    return str(value).strip() if value else None


def parse_article_page(html: bytes, requested_url: str) -> dict[str, str | None]:
    """Extrait les champs éditoriaux directement depuis une page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one('[itemprop="articleBody"]')
    if body is None:
        raise ValueError("Corps d'article introuvable dans le HTML.")

    caption_tag = soup.select_one("figure.magazine figcaption")
    # Les figures et éléments techniques ne doivent pas être mélangés au texte.
    for unwanted in body.select("script, style, figure, aside, form"):
        unwanted.decompose()

    title_tag = soup.select_one("h1")
    time_tag = soup.select_one("time[datetime]")

    source_url = meta_content(soup, 'meta[property="og:url"]') or requested_url
    image_url = meta_content(soup, 'meta[property="og:image"]')
    return {
        "link": source_url,
        "title": meta_content(soup, 'meta[property="og:title"]')
        or (title_tag.get_text(" ", strip=True) if title_tag else None),
        "text": " ".join(body.stripped_strings),
        "published": str(time_tag.get("datetime")).strip()
        if time_tag and time_tag.get("datetime")
        else None,
        "author": meta_content(soup, 'meta[name="author"]'),
        "image_url": urljoin(source_url, image_url) if image_url else None,
        "image_caption": caption_tag.get_text(" ", strip=True)
        if caption_tag
        else None,
    }


def extract_theconversation(
    limit: int,
    request_delay: float,
    refresh_images: bool,
    logger: logging.Logger,
) -> list[dict]:
    """Parcourt le flux Atom puis analyse jusqu'à ``limit`` pages avec Beautiful Soup."""
    records: list[dict] = []
    attempted_pages = 0

    with create_http_session() as session:
        response = session.get(FEED_URL, timeout=(5, 30))
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        if feed.bozo:
            logger.warning("Flux Atom imparfait mais lisible : %s", feed.bozo_exception)
        if not feed.entries:
            raise RuntimeError("Le flux The Conversation ne contient aucune entrée.")

        logger.info("%s entrées Atom reçues", len(feed.entries))

        for entry in feed.entries:
            if len(records) >= limit:
                break

            article_url = str(entry.get("link") or "").strip()
            hostname = (urlsplit(article_url).hostname or "").lower()
            if hostname not in {"theconversation.com", "www.theconversation.com"}:
                logger.warning("URL hors domaine ignorée : %s", article_url or "absente")
                continue

            if attempted_pages and request_delay:
                time.sleep(request_delay)
            attempted_pages += 1

            try:
                page_response = session.get(article_url, timeout=(5, 30))
                page_response.raise_for_status()
                page = parse_article_page(page_response.content, article_url)

                article_id = make_article_id(str(entry.get("id") or ""), article_url)
                image_id = f"theconversation_{article_id}"
                image_url = page["image_url"] or ""
                if not page["title"] or not page["text"] or not image_url:
                    raise ValueError("Titre, texte ou image absent de la page.")

                image = download_image(
                    session,
                    image_url,
                    image_id,
                    IMAGES_DIR,
                    refresh_existing=refresh_images,
                )
            except (requests.RequestException, OSError, ValueError, RuntimeError) as error:
                logger.warning("Article ignoré (%s) : %s", article_url or "sans URL", error)
                continue

            records.append({
                "id": article_id,
                "feed_id": entry.get("id"),
                "link": page["link"],
                "title": page["title"],
                "text": page["text"],
                "summary": entry.get("summary"),
                "published": page["published"] or entry.get("published"),
                "author": page["author"] or entry.get("author"),
                "image_url": image_url,
                "image_caption": page["image_caption"],
                "rights": entry.get("rights"),
                "_image_path": relative_path(image.path),
                "_image_size": image.size_bytes,
                "_image_sha256": image.sha256,
                "_downloaded_from_url": image.source_url,
                "_image_provenance_status": image.provenance_status,
            })
            logger.info(
                "[%s/%s] Article %s prêt (%s, provenance=%s)",
                len(records),
                limit,
                article_id,
                "téléchargé" if image.downloaded else "déjà présent",
                image.provenance_status,
            )

    if not records:
        raise RuntimeError("Aucun article texte-image The Conversation n'a été extrait.")
    return records


def parse_args() -> argparse.Namespace:
    """Lit les paramètres configurables de l'extracteur."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--request-delay",
        type=float,
        default=1.0,
        help="Pause en secondes entre deux articles (défaut : 1).",
    )
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Retélécharge les images même si une copie locale existe.",
    )
    return parser.parse_args()


def main() -> None:
    """Point d'entrée autonome du script."""
    args = parse_args()
    logger = configure_logging("theconversation")

    try:
        if args.limit < 1 or args.request_delay < 0:
            raise ValueError("--limit doit être positif et --request-delay positif ou nul.")
        records = extract_theconversation(
            args.limit,
            args.request_delay,
            args.refresh_images,
            logger,
        )
        output_path = save_json_records(records, "theconversation")
        logger.info("Extraction terminée : %s articles dans %s", len(records), output_path)
    except Exception:
        logger.exception("Échec de l'extraction The Conversation")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
