"""Lance successivement les quatre extracteurs du projet."""

import argparse
import subprocess
import sys

from common import PROJECT_ROOT, configure_logging


SCRIPTS = (
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
        help="Transmet l'option de retéléchargement aux quatre extracteurs.",
    )
    return parser.parse_args()


def main() -> None:
    """Exécute chaque source et retourne une erreur si l'une échoue."""
    args = parse_args()
    logger = configure_logging("run_extraction")
    scripts_dir = PROJECT_ROOT / "scripts"
    failed_scripts: list[str] = []

    for script_name in SCRIPTS:
        logger.info("Démarrage de %s", script_name)
        command = [sys.executable, str(scripts_dir / script_name)]
        if args.refresh_images:
            command.append("--refresh-images")
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
        )

        if result.returncode == 0:
            logger.info("Succès de %s", script_name)
        else:
            failed_scripts.append(script_name)
            logger.error("Échec de %s (code %s)", script_name, result.returncode)

    if failed_scripts:
        logger.error("Extracteurs en échec : %s", ", ".join(failed_scripts))
        raise SystemExit(1)

    logger.info("Toutes les extractions sont terminées.")


if __name__ == "__main__":
    main()
