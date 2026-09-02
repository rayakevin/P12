"""Charge le contrat Parquet transformé dans PostgreSQL de façon idempotente."""

import argparse
import logging
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from common import DATA_DIR, configure_logging
from transform_data import FINAL_COLUMNS


DEFAULT_PARQUET_PATH = DATA_DIR / "processed" / "publications.parquet"
DEFAULT_TABLE = "publication_multimodale"


def validate_table_name(table_name: str) -> str:
    """Refuse tout nom de table qui ne soit pas un identifiant SQL simple."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", table_name):
        raise ValueError("Le nom de table PostgreSQL est invalide.")
    return table_name


def create_table_sql(table_name: str) -> str:
    """Construit le DDL PostgreSQL correspondant au contrat de 18 colonnes."""
    table = validate_table_name(table_name)
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            publication_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_domain TEXT NOT NULL,
            source_url TEXT NOT NULL CHECK (source_url ~ '^https?://'),
            title TEXT,
            text TEXT,
            image_url TEXT NOT NULL CHECK (image_url ~ '^https?://'),
            image_path TEXT NOT NULL,
            image_size_bytes BIGINT NOT NULL CHECK (image_size_bytes > 0),
            image_sha256 CHAR(64) NOT NULL
                CHECK (image_sha256 ~ '^[0-9a-f]{{64}}$'),
            image_provenance_status TEXT NOT NULL
                CHECK (image_provenance_status IN ('downloaded', 'metadata_verified')),
            published_at TIMESTAMPTZ NOT NULL,
            language CHAR(2) NOT NULL CHECK (language ~ '^[a-z]{{2}}$'),
            author TEXT,
            source_label_raw TEXT,
            source_label_scheme TEXT,
            label_provenance TEXT,
            collected_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT publication_text_required CHECK (title IS NOT NULL OR text IS NOT NULL),
            CONSTRAINT label_provenance_complete CHECK (
                (source_label_raw IS NULL
                    AND source_label_scheme IS NULL
                    AND label_provenance IS NULL)
                OR
                (source_label_raw IS NOT NULL
                    AND source_label_scheme IS NOT NULL
                    AND label_provenance IS NOT NULL)
            ),
            CONSTRAINT publication_source_image_unique UNIQUE (source_url, image_sha256)
        )
    """


def read_publications(parquet_path: Path) -> pd.DataFrame:
    """Lit le Parquet et vérifie qu'il respecte exactement le contrat final."""
    if not parquet_path.is_file():
        raise FileNotFoundError(f"Parquet absent : {parquet_path}")

    dataframe = pd.read_parquet(parquet_path)
    if tuple(dataframe.columns) != FINAL_COLUMNS:
        raise ValueError("Les colonnes du Parquet ne correspondent pas au contrat final.")
    if dataframe.empty:
        raise ValueError("Le Parquet ne contient aucune publication.")
    if dataframe["publication_id"].isna().any() or not dataframe["publication_id"].is_unique:
        raise ValueError("publication_id doit être renseigné et unique.")
    return dataframe


def database_value(value: Any) -> Any:
    """Convertit les types pandas en valeurs acceptées par un pilote PostgreSQL."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_rows(dataframe: pd.DataFrame) -> list[tuple[Any, ...]]:
    """Transforme le DataFrame en lignes ordonnées selon le contrat final."""
    return [
        tuple(database_value(value) for value in row)
        for row in dataframe.itertuples(index=False, name=None)
    ]


def upsert_sql(table_name: str) -> str:
    """Construit la requête d'upsert basée sur la clé primaire publication_id."""
    table = validate_table_name(table_name)
    columns = ", ".join(FINAL_COLUMNS)
    placeholders = ", ".join(["%s"] * len(FINAL_COLUMNS))
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in FINAL_COLUMNS
        if column != "publication_id"
    )
    return f"""
        INSERT INTO {table} ({columns})
        VALUES ({placeholders})
        ON CONFLICT (publication_id) DO UPDATE SET {updates}
    """


def load_publications(
    connection: Any,
    parquet_path: Path,
    table_name: str,
    batch_size: int,
    logger: logging.Logger,
) -> int:
    """Crée la table puis insère ou met à jour les publications par lots."""
    if batch_size < 1:
        raise ValueError("batch_size doit être positif.")

    dataframe = read_publications(parquet_path)
    rows = dataframe_rows(dataframe)
    try:
        with connection.cursor() as cursor:
            cursor.execute(create_table_sql(table_name))
            statement = upsert_sql(table_name)
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                cursor.executemany(statement, batch)
                logger.info(
                    "Lot PostgreSQL chargé : lignes %s à %s",
                    start + 1,
                    start + len(batch),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    logger.info("Chargement terminé : %s publications traitées", len(rows))
    return len(rows)


def validate_loaded_table(
    connection: Any,
    table_name: str,
    minimum_count: int,
) -> dict[str, int]:
    """Contrôle le volume, les clés et l'association texte-image en base."""
    table = validate_table_name(table_name)
    query = f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE publication_id IS NULL
                   OR (title IS NULL AND text IS NULL)
                   OR image_url IS NULL
                   OR image_path IS NULL
                   OR image_sha256 IS NULL
            ) AS invalid_multimodal,
            COUNT(*) - COUNT(DISTINCT publication_id) AS duplicate_ids
        FROM {table}
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        total, invalid_multimodal, duplicate_ids = cursor.fetchone()

    result = {
        "total": int(total),
        "invalid_multimodal": int(invalid_multimodal),
        "duplicate_ids": int(duplicate_ids),
    }
    if result["total"] < minimum_count:
        raise RuntimeError("Le nombre de lignes PostgreSQL est inférieur au Parquet.")
    if result["invalid_multimodal"] or result["duplicate_ids"]:
        raise RuntimeError(f"Contrôle PostgreSQL en échec : {result}")
    return result


def parse_args() -> argparse.Namespace:
    """Lit les paramètres de chargement depuis la ligne de commande."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET_PATH)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    """Charge le Parquet avec l'URL conservée dans une variable d'environnement."""
    args = parse_args()
    logger = configure_logging("load_postgres")
    database_url = os.getenv("CHECKITAI_DATABASE_URL")
    if not database_url:
        raise SystemExit("La variable CHECKITAI_DATABASE_URL est absente.")

    try:
        import psycopg

        with psycopg.connect(database_url) as connection:
            loaded_count = load_publications(
                connection,
                args.parquet,
                args.table,
                args.batch_size,
                logger,
            )
            result = validate_loaded_table(
                connection,
                args.table,
                loaded_count,
            )
        logger.info("Contrôle final PostgreSQL : %s", result)
    except Exception:
        logger.exception("Échec du chargement PostgreSQL")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
