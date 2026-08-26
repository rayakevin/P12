"""Lance successivement les trois extracteurs du projet."""

import subprocess
import sys

from common import PROJECT_ROOT, configure_logging


SCRIPTS = (
    "extract_newsdata.py",
    "extract_politifact.py",
    "extract_fakeddit.py",
)


def main() -> None:
    """Exécute chaque source et retourne une erreur si l'une échoue."""
    logger = configure_logging("run_extraction")
    scripts_dir = PROJECT_ROOT / "scripts"
    failed_scripts: list[str] = []

    for script_name in SCRIPTS:
        logger.info("Démarrage de %s", script_name)
        result = subprocess.run(
            [sys.executable, str(scripts_dir / script_name)],
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
