"""Tests unitaires des règles critiques du pipeline, sans accès réseau."""

import json
import logging
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from collect_kpis import (
    count_multimodal_publications,
    manifest_counts,
    parse_task_log,
)
from common import write_json_atomic
from load_postgres import (
    create_table_sql,
    upsert_sql,
    validate_table_name,
)
from transform_data import (
    FINAL_COLUMNS,
    RecordValidationError,
    make_dataframe,
    normalize_datetime,
    transform_batch,
    validate_configuration,
)


class CommonTests(unittest.TestCase):
    """Vérifie les utilitaires partagés."""

    def test_write_json_atomic_writes_complete_payload(self) -> None:
        """L'écriture JSON produit le contenu attendu sans fichier temporaire."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            write_json_atomic({"clé": "valeur"}, path, sort_keys=True)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"clé": "valeur"},
            )
            self.assertFalse(path.with_suffix(".json.part").exists())


class TransformationTests(unittest.TestCase):
    """Vérifie normalisation, paramètres et contrat final."""

    def test_normalize_datetime_supports_iso_rss_and_unix(self) -> None:
        """Les trois formats de date utilisés finissent en UTC."""
        values = (
            "2026-09-02T12:00:00Z",
            "Wed, 02 Sep 2026 12:00:00 +0000",
            "1788350400",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(normalize_datetime(value).endswith("Z"))

    def test_normalize_datetime_rejects_missing_value(self) -> None:
        """Une publication sans date est rejetée explicitement."""
        with self.assertRaises(RecordValidationError):
            normalize_datetime(None)

    def test_validate_configuration_rejects_unknown_source(self) -> None:
        """Un appel programmatique ne peut pas contourner les choix de la CLI."""
        with self.assertRaisesRegex(ValueError, "non prises en charge"):
            validate_configuration(["inconnue"], "all", "keep-latest", "both")

    def test_make_dataframe_keeps_exact_contract(self) -> None:
        """Le DataFrame respecte l'ordre des 18 colonnes."""
        record = {column: None for column in FINAL_COLUMNS}
        record.update(
            {
                "publication_id": "source_1",
                "image_size_bytes": 1,
                "published_at": "2026-09-02T12:00:00Z",
                "collected_at": "2026-09-02T12:01:00Z",
            }
        )
        dataframe = make_dataframe([record])
        self.assertEqual(tuple(dataframe.columns), FINAL_COLUMNS)

    def test_transform_batch_rejects_non_object_record(self) -> None:
        """Un élément JSON invalide est isolé sans interrompre le lot."""
        payload = {
            "source": "newsdata",
            "collected_at": "2026-09-02T12:00:00Z",
            "count": 1,
            "records": ["record invalide"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "batch.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            logger = logging.getLogger("test_transform_batch")
            logger.disabled = True
            candidates, rejected, audit = transform_batch(
                "newsdata",
                path,
                batch_index=0,
                metrics=Counter(),
                logger=logger,
            )

        self.assertEqual(candidates, [])
        self.assertEqual(rejected[0]["reason"], "record_brut_invalide")
        self.assertEqual(audit["validation_rejected_count"], 1)


class LoadTests(unittest.TestCase):
    """Vérifie les protections et la requête du chargement."""

    def test_table_name_blocks_sql_injection(self) -> None:
        """Seuls les identifiants SQL simples sont acceptés."""
        with self.assertRaises(ValueError):
            validate_table_name("publication; DROP TABLE publication")

    def test_sql_contains_primary_key_constraints_and_upsert(self) -> None:
        """Le DDL et l'upsert portent les garanties essentielles."""
        ddl = create_table_sql("publication_multimodale")
        statement = upsert_sql("publication_multimodale")
        self.assertIn("publication_id TEXT PRIMARY KEY", ddl)
        self.assertIn("publication_source_image_unique", ddl)
        self.assertIn("ON CONFLICT (publication_id) DO UPDATE", statement)


class MonitoringTests(unittest.TestCase):
    """Vérifie les calculs KPI indépendamment de Streamlit."""

    def test_manifest_counts_distinguishes_duplicates_and_invalid_rows(self) -> None:
        """Les doublons ne sont pas additionnés aux rejets de validation."""
        counts = manifest_counts(
            {
                "inputs": [
                    {
                        "raw_count": 10,
                        "validated_count": 9,
                        "validation_rejected_count": 1,
                        "duplicate_discarded_count": 3,
                    }
                ]
            }
        )
        self.assertEqual(counts["raw_count"], 10)
        self.assertEqual(counts["validation_rejected_count"], 1)
        self.assertEqual(counts["duplicate_count"], 3)

    def test_count_multimodal_requires_text_and_complete_image_proof(self) -> None:
        """Une URL d'image seule ne suffit pas à valider une publication."""
        valid_hash = "a" * 64
        dataframe = pd.DataFrame(
            [
                {
                    "title": "Titre",
                    "text": None,
                    "image_url": "https://example.org/image.jpg",
                    "image_path": "data/images/source/1.jpg",
                    "image_sha256": valid_hash,
                    "image_size_bytes": 42,
                },
                {
                    "title": "Incomplète",
                    "text": None,
                    "image_url": "https://example.org/image.jpg",
                    "image_path": "",
                    "image_sha256": valid_hash,
                    "image_size_bytes": 42,
                },
            ]
        )
        self.assertEqual(count_multimodal_publications(dataframe), 1)

    def test_parse_task_log_uses_last_valid_attempt_timestamps(self) -> None:
        """Un log JSONL réussi fournit un statut et une durée."""
        events = (
            {"timestamp": "2026-09-02T12:00:00Z", "event": "Starting attempt"},
            {
                "timestamp": "2026-09-02T12:00:02Z",
                "event": "Done. Returned value was: 10",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt=1.log"
            path.write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )
            result = parse_task_log(path)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["duration_seconds"], 2.0)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
