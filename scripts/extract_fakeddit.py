"""Extrait un échantillon texte-image depuis le TSV Fakeddit."""

import argparse
import csv
import logging
import time
from pathlib import Path

import requests

from common import (
    DATA_DIR,
    PROJECT_ROOT,
    configure_logging,
    create_http_session,
    download_image,
    relative_path,
    save_json_records,
)


DEFAULT_TSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "external"
    / "fakeddit"
    / "multimodal_train.tsv"
)
IMAGES_DIR = DATA_DIR / "images" / "fakeddit"
REQUEST_DELAY_SECONDS = 0.2


def extract_fakeddit(
    tsv_path: Path,
    limit: int,
    refresh_images: bool,
    logger: logging.Logger,
) -> list[dict]:
    """Lit le TSV progressivement et récupère ``limit`` couples texte-image."""
    if not tsv_path.is_file():
        raise FileNotFoundError(f"Fichier TSV absent : {tsv_path}")

    records: list[dict] = []
    failures = 0

    with create_http_session() as session, tsv_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file, delimiter="\t")

        for line_number, row in enumerate(reader, start=2):
            if len(records) >= limit:
                break

            image_id = (row.get("id") or "").strip()
            image_url = (row.get("image_url") or "").strip()
            clean_title = (row.get("clean_title") or "").strip()
            has_image = (
                (row.get("hasImage") or "").strip().lower() == "true"
            )

            if not image_id or not image_url or not clean_title or not has_image:
                continue

            try:
                image = download_image(
                    session,
                    image_url,
                    image_id,
                    IMAGES_DIR,
                    refresh_existing=refresh_images,
                )
            except (requests.RequestException, OSError, ValueError, RuntimeError) as error:
                failures += 1
                logger.warning("Ligne %s, image %s ignorée : %s", line_number, image_id, error)
                continue

            record = dict(row)
            record["_image_path"] = relative_path(image.path)
            record["_image_size"] = image.size_bytes
            record["_image_sha256"] = image.sha256
            record["_downloaded_from_url"] = image.source_url
            record["_image_provenance_status"] = image.provenance_status
            records.append(record)
            logger.info(
                "[%s/%s] %s (%s, provenance=%s)",
                len(records),
                limit,
                image_id,
                "téléchargé" if image.downloaded else "déjà présent",
                image.provenance_status,
            )

            if image.downloaded:
                time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Bilan : %s couples prêts, %s échecs", len(records), failures)
    if not records:
        raise RuntimeError("Aucun couple texte-image Fakeddit n'a été extrait.")
    return records


def parse_args() -> argparse.Namespace:
    """Lit la limite et le chemin TSV depuis la ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--tsv", type=Path, default=DEFAULT_TSV_PATH)
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Retélécharge les images même si une copie locale existe.",
    )
    return parser.parse_args()


def main() -> None:
    """Point d'entrée autonome du script."""
    args = parse_args()
    logger = configure_logging("fakeddit")

    try:
        if args.limit < 1:
            raise ValueError("--limit doit être positif.")
        records = extract_fakeddit(
            args.tsv,
            args.limit,
            args.refresh_images,
            logger,
        )
        output_path = save_json_records(records, "fakeddit")
        logger.info("Extraction terminée : %s couples dans %s", len(records), output_path)
    except Exception:
        logger.exception("Échec de l'extraction Fakeddit")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
