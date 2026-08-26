"""Fonctions partagées par les scripts d'extraction."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

MAX_IMAGE_BYTES = 10 * 1024 * 1024
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def configure_logging(source: str) -> logging.Logger:
    """Crée un logger affiché dans le terminal et conservé dans un fichier voir dossier /logs."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(source)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(
        LOGS_DIR / f"{source}.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def create_http_session() -> requests.Session:
    """Retourne une session HTTP avec retries sur les erreurs temporaires.""" 


    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
        respect_retry_after_header=True,
    )
        #429  quota ou débit dépassé
        #500  erreur interne
        #502  mauvaise passerelle
        #503  service indisponible
        #504  délai de passerelle dépassé
        
    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.headers.update({"User-Agent": "CheckItAI-P12/1.0"})
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def download_image(
    session: requests.Session,
    image_url: str,
    image_id: str,
    output_dir: Path,
) -> tuple[Path, int, bool]:
    """Télécharge une image valide et retourne chemin, taille et état nouveau/existant."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Une image existante et non vide rend le script relançable sans doublon.
    for extension in CONTENT_TYPE_EXTENSIONS.values():
        existing_path = output_dir / f"{image_id}{extension}"
        if existing_path.is_file() and existing_path.stat().st_size > 0:
            return existing_path, existing_path.stat().st_size, False

    with session.get(
        image_url,
        timeout=(5, 30),
        stream=True,
    ) as response:
        response.raise_for_status()
        content_type = (
            response.headers.get("Content-Type", "").split(";")[0].lower()
        )
        extension = CONTENT_TYPE_EXTENSIONS.get(content_type)

        if extension is None:
            raise ValueError(
                f"Format d'image non accepté : {content_type or 'absent'}"
            )

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_IMAGE_BYTES:
            raise ValueError("L'image dépasse la taille maximale de 10 Mo.")

        destination = output_dir / f"{image_id}{extension}"
        temporary_path = destination.with_suffix(f"{destination.suffix}.part")
        downloaded_bytes = 0

        try:
            with temporary_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue

                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > MAX_IMAGE_BYTES:
                        raise ValueError(
                            "L'image dépasse la taille maximale de 10 Mo."
                        )
                    file.write(chunk)

            if downloaded_bytes == 0:
                raise RuntimeError("Le serveur n'a renvoyé aucun octet.")

            # Le fichier final n'apparaît qu'après un téléchargement complet.
            temporary_path.replace(destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    return destination, downloaded_bytes, True


def relative_path(path: Path) -> str:
    """Retourne un chemin relatif au projet pour rendre le JSON portable."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def utc_now() -> str:
    """Retourne la date UTC actuelle au format ISO 8601."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def save_json_records(records: list[dict], source: str) -> Path:
    """Sauvegarde atomiquement une extraction JSON horodatée."""
    output_dir = DATA_DIR / "raw" / source
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_at = utc_now()
    filename_timestamp = collected_at.replace(":", "").replace("-", "")
    output_path = output_dir / f"extraction_{filename_timestamp}.json"
    temporary_path = output_path.with_suffix(".json.part")

    payload = {
        "source": source,
        "collected_at": collected_at,
        "count": len(records),
        "records": records,
    }

    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return output_path
