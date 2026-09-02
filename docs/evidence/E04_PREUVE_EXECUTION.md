# Preuve d'exécution — DAG `checkitai_multimodal_etl`

Date du test : 2 septembre 2026  
Version Airflow : 3.3.1  
Run ID : `manual__2026-09-02T12:28:34.482208+00:00`  
État final : `success`

## État des tâches retourné par Airflow

| Tâche | État | Début UTC | Fin UTC |
|---|---|---|---|
| `extract_fakeddit` | success | 12:28:35.191654 | 12:28:39.413250 |
| `extract_politifact` | success | 12:28:35.191654 | 12:28:39.520097 |
| `extract_newsdata` | success | 12:28:35.191654 | 12:28:39.693560 |
| `extract_theconversation` | success | 12:28:35.191657 | 12:28:49.017224 |
| `transform` | success | 12:28:49.930398 | 12:28:53.329083 |
| `load_postgres` | success | 12:28:54.245860 | 12:28:55.218680 |
| `validate_postgres` | success | 12:28:55.391706 | 12:28:56.158492 |

## Valeurs retournées par les tâches

```text
transform           -> 1077
load_postgres       -> 1077
validate_postgres   -> {
  'total': 1077,
  'invalid_multimodal': 0,
  'duplicate_ids': 0
}
```

## Contrôle de la table métier

```text
source_name                publications
Fakeddit                   1000
NewsData.io                  20
PolitiFact                   24
The Conversation France      33

total       1077
ids_uniques 1077
associations_invalides 0
```

## Contrôle du rôle de chargement

```text
rolname           rolsuper  rolcreatedb  rolcreaterole  rolcanlogin
checkitai_loader  false     false        false          true
```

## Commandes de reproduction

```bash
docker compose --env-file .env.airflow -f docker-compose.airflow.yml \
  exec airflow-scheduler airflow dags list-import-errors

docker compose --env-file .env.airflow -f docker-compose.airflow.yml \
  exec airflow-scheduler airflow dags trigger checkitai_multimodal_etl

docker compose --env-file .env.airflow -f docker-compose.airflow.yml \
  exec airflow-scheduler airflow tasks states-for-dag-run \
  checkitai_multimodal_etl '<run_id>'
```

Le graphe [`checkitai_multimodal_etl.png`](checkitai_multimodal_etl.png) a été
exporté directement par la commande `airflow dags show`.

## Test d'idempotence

Le même Parquet de 1 077 lignes a été chargé une seconde fois avec des lots de
250. Le contrôle après upsert retourne toujours 1 077 lignes et 1 077
`publication_id` distincts : la relance n'a donc créé aucun doublon.
