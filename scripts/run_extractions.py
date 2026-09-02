"""Lance successivement les quatre extracteurs du projet."""

import argparse
import subprocess
import sys

from common import PROJECT_ROOT, configure_logging

EXTRACTION_SCRIPTS = (
    "extract_newsdata.py",
    "extract_politifact.py",
    "extract_fakeddit.py",
    "extract_theconversation.py",
)


def parse_args() -> argparse.Namespace:
    """Lit l'option de rafraîchissement des images existantes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Retélécharge les images pour les quatre sources.",
    )
    return parser.parse_args()


def run_extractor(script_name: str, refresh_images: bool) -> int:
    """Exécute un extracteur et retourne son code de sortie."""
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / script_name)]
    if refresh_images:
        command.append("--refresh-images")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return result.returncode


def main() -> None:
    """Exécute chaque source et signale un échec global si nécessaire."""
    args = parse_args()
    logger = configure_logging("run_extractions")
    failed_scripts: list[str] = []

    for script_name in EXTRACTION_SCRIPTS:
        logger.info("Démarrage de %s", script_name)
        try:
            return_code = run_extractor(script_name, args.refresh_images)
        except OSError:
            failed_scripts.append(script_name)
            logger.exception("Impossible de démarrer %s", script_name)
            continue

        if return_code == 0:
            logger.info("Succès de %s", script_name)
            continue

        failed_scripts.append(script_name)
        logger.error("Échec de %s (code %s)", script_name, return_code)

    if failed_scripts:
        logger.error("Extracteurs en échec : %s", ", ".join(failed_scripts))
        raise SystemExit(1)

    logger.info("Toutes les extractions sont terminées.")


if __name__ == "__main__":
    main()
