"""Orchestre l'ETL multimodal CheckIt.AI vers PostgreSQL."""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

DAG_ID = "checkitai_multimodal_etl"
POSTGRES_CONN_ID = "checkitai_warehouse"


def project_root() -> Path:
    """Retourne la racine du projet montée dans le conteneur Airflow."""
    return Path(os.getenv("CHECKITAI_PROJECT_ROOT", "/opt/checkitai"))


def import_project_scripts() -> Path:
    """Rend les modules du dossier scripts importables par les tâches."""
    root = project_root()
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return root


def positive_int_env(name: str, default: int) -> int:
    """Lit un entier positif configurable depuis l'environnement."""
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} doit être positif.")
    return value


def extract_newsdata_task() -> int:
    """Extrait et sauvegarde un lot NewsData.io."""
    import_project_scripts()
    from extract_newsdata import extract_newsdata

    from common import configure_logging, save_json_records

    api_key = os.getenv("NEWSDATA_API_KEY")
    if not api_key:
        raise RuntimeError("NEWSDATA_API_KEY est absente de l'environnement Airflow.")
    logger = configure_logging("newsdata")
    records = extract_newsdata(
        api_key=api_key,
        limit=positive_int_env("CHECKITAI_NEWSDATA_LIMIT", 10),
        max_pages=positive_int_env("CHECKITAI_NEWSDATA_MAX_PAGES", 1),
        query=os.getenv("CHECKITAI_NEWSDATA_QUERY") or None,
        refresh_images=False,
        logger=logger,
    )
    save_json_records(records, "newsdata")
    return len(records)


def extract_politifact_task() -> int:
    """Extrait et sauvegarde un lot PolitiFact."""
    import_project_scripts()
    from extract_politifact import extract_politifact

    from common import configure_logging, save_json_records

    logger = configure_logging("politifact")
    records = extract_politifact(
        limit=positive_int_env("CHECKITAI_POLITIFACT_LIMIT", 20),
        refresh_images=False,
        logger=logger,
    )
    save_json_records(records, "politifact")
    return len(records)


def extract_fakeddit_task() -> int:
    """Extrait et sauvegarde un lot Fakeddit depuis le TSV monté."""
    root = import_project_scripts()
    from extract_fakeddit import extract_fakeddit

    from common import configure_logging, save_json_records

    logger = configure_logging("fakeddit")
    tsv_path = Path(
        os.getenv(
            "CHECKITAI_FAKEDDIT_TSV",
            str(root / "data/external/fakeddit/multimodal_train.tsv"),
        )
    )
    records = extract_fakeddit(
        tsv_path=tsv_path,
        limit=positive_int_env("CHECKITAI_FAKEDDIT_LIMIT", 100),
        refresh_images=False,
        logger=logger,
    )
    save_json_records(records, "fakeddit")
    return len(records)


def extract_theconversation_task() -> int:
    """Extrait et sauvegarde un lot The Conversation France."""
    import_project_scripts()
    from extract_theconversation import extract_theconversation

    from common import configure_logging, save_json_records

    logger = configure_logging("theconversation")
    request_delay = float(os.getenv("CHECKITAI_REQUEST_DELAY", "1.0"))
    if request_delay < 0:
        raise ValueError("CHECKITAI_REQUEST_DELAY doit être positif ou nul.")
    records = extract_theconversation(
        limit=positive_int_env("CHECKITAI_THECONVERSATION_LIMIT", 10),
        request_delay=request_delay,
        refresh_images=False,
        logger=logger,
    )
    save_json_records(records, "theconversation")
    return len(records)


def transform_task() -> int:
    """Consolide tous les lots bruts dans le contrat Parquet final."""
    root = import_project_scripts()
    from common import configure_logging
    from transform_data import SUPPORTED_SOURCES, run_transformation

    logger = configure_logging("transform")
    manifest = run_transformation(
        sources=SUPPORTED_SOURCES,
        input_mode=os.getenv("CHECKITAI_INPUT_MODE", "all"),
        duplicate_policy=os.getenv("CHECKITAI_DUPLICATE_POLICY", "keep-latest"),
        raw_dir=root / "data/raw",
        processed_dir=root / "data/processed",
        rejected_dir=root / "data/rejected",
        output_format="both",
        logger=logger,
    )
    return int(manifest["accepted_count"])


def load_postgres_task() -> int:
    """Charge le Parquet dans la base métier via une connexion Airflow."""
    root = import_project_scripts()
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    from common import configure_logging
    from load_postgres import load_publications

    logger = configure_logging("load_postgres")
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    connection = hook.get_conn()
    try:
        return load_publications(
            connection=connection,
            parquet_path=root / "data/processed/publications.parquet",
            table_name=os.getenv("CHECKITAI_TABLE", "publication_multimodale"),
            batch_size=positive_int_env("CHECKITAI_LOAD_BATCH_SIZE", 500),
            logger=logger,
        )
    finally:
        connection.close()


def validate_postgres_task(ti) -> dict[str, int]:
    """Compare le volume chargé et contrôle les associations multimodales."""
    import_project_scripts()
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    from load_postgres import validate_loaded_table

    expected_count = int(ti.xcom_pull(task_ids="transform"))
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    connection = hook.get_conn()
    try:
        return validate_loaded_table(
            connection=connection,
            table_name=os.getenv("CHECKITAI_TABLE", "publication_multimodale"),
            minimum_count=expected_count,
        )
    finally:
        connection.close()


with DAG(
    dag_id=DAG_ID,
    description="Extraction, transformation et chargement des publications multimodales",
    schedule=os.getenv("CHECKITAI_SCHEDULE") or None,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "checkitai",
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["etl", "multimodal", "postgresql"],
) as dag:
    extract_newsdata = PythonOperator(
        task_id="extract_newsdata",
        python_callable=extract_newsdata_task,
    )
    extract_politifact = PythonOperator(
        task_id="extract_politifact",
        python_callable=extract_politifact_task,
    )
    extract_fakeddit = PythonOperator(
        task_id="extract_fakeddit",
        python_callable=extract_fakeddit_task,
    )
    extract_theconversation = PythonOperator(
        task_id="extract_theconversation",
        python_callable=extract_theconversation_task,
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=transform_task,
    )
    load_postgres = PythonOperator(
        task_id="load_postgres",
        python_callable=load_postgres_task,
    )
    validate_postgres = PythonOperator(
        task_id="validate_postgres",
        python_callable=validate_postgres_task,
    )

    (
        [
            extract_newsdata,
            extract_politifact,
            extract_fakeddit,
            extract_theconversation,
        ]
        >> transform
        >> load_postgres
        >> validate_postgres
    )
