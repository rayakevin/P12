# CheckIt.AI — Pipeline ETL de données multimodales

Ce projet extrait, transforme, charge et surveille des publications associant
texte et image. L'acquisition s'appuie sur quatre sources complémentaires :

- NewsData.io : API REST JSON avec clé ;
- PolitiFact : flux RSS public ;
- Fakeddit : TSV local et URLs d’images Reddit ;
- The Conversation France : flux Atom puis pages HTML analysées avec Beautiful Soup.

## Préparation

```bash
uv sync
```

Créer un fichier `.env` à la racine :

```dotenv
NEWSDATA_API_KEY=votre_cle
```

Placer le TSV Fakeddit ici :

```text
data/external/fakeddit/multimodal_train.tsv
```

## Exécution

Lancer toutes les sources sans intervention :

```bash
uv run python scripts/run_extractions.py
```

Pour retélécharger les images et recréer une preuve forte URL–hash :

```bash
uv run python scripts/run_extractions.py --refresh-images
```

Ou lancer une seule source :

```bash
uv run python scripts/extract_newsdata.py --limit 10 --max-pages 1
uv run python scripts/extract_politifact.py --limit 20
uv run python scripts/extract_fakeddit.py --limit 100
uv run python scripts/extract_theconversation.py --limit 10
```

L’extracteur The Conversation suit uniquement les URLs du flux Atom, vérifie le
domaine, attend une seconde entre les articles et conserve la mention de licence
ainsi que la légende de l’image dans le JSON brut.

Chaque script possède une aide :

```bash
uv run python scripts/extract_newsdata.py --help
```

Les contrôles unitaires et la qualité statique s’exécutent sans accès réseau :

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check scripts dashboard airflow/dags tests
uv run ruff format --check scripts dashboard airflow/dags tests
```

## Sorties

```text
data/
├── raw/
│   ├── newsdata/extraction_<date>.json
│   ├── politifact/extraction_<date>.json
│   ├── fakeddit/extraction_<date>.json
│   └── theconversation/extraction_<date>.json
└── images/
    ├── newsdata/
    ├── politifact/
    ├── fakeddit/
    └── theconversation/

logs/
├── newsdata.log
├── politifact.log
├── fakeddit.log
├── theconversation.log
└── run_extractions.log
```

Les JSON conservent les champs fournis par chaque source et ajoutent seulement
les informations techniques nécessaires : `_image_path`, `_image_size`,
`_image_sha256`, `_downloaded_from_url` et `_image_provenance_status`.
Un fichier `<image_id>.metadata.json` conservé à côté de chaque image permet de
vérifier l’URL et le hash avant toute réutilisation.

## Transformation

Après l’extraction, lancer le pipeline reproductible :

```bash
uv run python scripts/transform_data.py
```

Par défaut, le script cumule tous les lots et garde l’occurrence la plus récente
de chaque publication. Une publication sans preuve complète reliant son URL à
son image locale est rejetée. Les choix de lecture et de dédoublonnage sont
configurables :

```bash
uv run python scripts/transform_data.py --sources politifact fakeddit
uv run python scripts/transform_data.py --sources theconversation
uv run python scripts/transform_data.py \
  --input-mode latest \
  --duplicate-policy keep-first
```

Le pipeline applique les étapes suivantes :

1. lecture et contrôle des lots JSON bruts ;
2. nettoyage des textes et du HTML PolitiFact ;
3. normalisation des dates, langues, auteurs et URLs ;
4. mapping des quatre sources vers 18 colonnes communes ;
5. validation du lien texte-image, de l’URL d’origine, du hash, de la signature
   et de la taille des fichiers ;
6. dédoublonnage par identifiant ou couple URL-image ;
7. typage, export et écriture des métriques d’audit.

Sorties produites :

```text
data/
├── processed/
│   ├── publications.parquet
│   ├── publications.jsonl
│   └── transformation_manifest.json
└── rejected/
    └── invalid_records.jsonl

logs/transform.log
```

Le manifeste conserve le chemin et le hash de chaque lot d’entrée, le hash du
pipeline, tous les paramètres, les compteurs par lot, les motifs de rejet et les
métriques de chaque étape. Le schéma conceptuel, le contrat Load, la clé primaire
et le dictionnaire des champs sont documentés dans
[`docs/E03_SCHEMA_DONNEES.ipynb`](docs/E03_SCHEMA_DONNEES.ipynb).

## Orchestration Airflow et chargement PostgreSQL

Le DAG `checkitai_multimodal_etl` orchestre les quatre extractions en parallèle,
puis la transformation, l'upsert PostgreSQL et un contrôle final. L'environnement
local complet se lance ainsi :

```bash
uv run python scripts/init_airflow_env.py
docker compose --env-file .env.airflow -f docker-compose.airflow.yml build
docker compose --env-file .env.airflow -f docker-compose.airflow.yml up airflow-init
docker compose --env-file .env.airflow -f docker-compose.airflow.yml up -d
```

L'interface Airflow est alors disponible sur <http://localhost:8080>. Les étapes,
les paramètres, la sécurité et les preuves d'exécution sont décrits dans
[`docs/E04_FLUX_ETL_AIRFLOW.ipynb`](docs/E04_FLUX_ETL_AIRFLOW.ipynb).

## Tableau de bord et monitoring

Le tableau de bord Streamlit calcule les KPI de qualité, rapidité, fiabilité et
coût à partir du manifeste, du Parquet et des logs Airflow :

```bash
uv run streamlit run dashboard/etl_kpi_dashboard.py
```

Il est disponible sur <http://localhost:8501>. Les formules, seuils d'alerte,
fréquences de contrôle et consignes en cas d'incident sont documentés dans
[`docs/E05_PLAN_MONITORING.ipynb`](docs/E05_PLAN_MONITORING.ipynb).

## Documentation détaillée

- [`E01_RAPPORT_EXPLORATION_SOURCES.ipynb`](docs/E01_RAPPORT_EXPLORATION_SOURCES.ipynb) — [PDF](docs/E01_RAPPORT_EXPLORATION_SOURCES.pdf)
- [`E03_SCHEMA_DONNEES.ipynb`](docs/E03_SCHEMA_DONNEES.ipynb) — [PDF](docs/E03_SCHEMA_DONNEES.pdf)
- [`E04_FLUX_ETL_AIRFLOW.ipynb`](docs/E04_FLUX_ETL_AIRFLOW.ipynb) — [PDF](docs/E04_FLUX_ETL_AIRFLOW.pdf)
- [`E05_PLAN_MONITORING.ipynb`](docs/E05_PLAN_MONITORING.ipynb) — [PDF](docs/E05_PLAN_MONITORING.pdf)
- [`INDEX_DOCUMENTATION_PERSONNELLE.html`](docs/perso/INDEX_DOCUMENTATION_PERSONNELLE.html)
- [`GUIDE_EXTRACTION_LIGNE_PAR_LIGNE.html`](docs/perso/GUIDE_EXTRACTION_LIGNE_PAR_LIGNE.html)
- [`GUIDE_TRANSFORMATION_LIGNE_PAR_LIGNE.html`](docs/perso/GUIDE_TRANSFORMATION_LIGNE_PAR_LIGNE.html)
- [`GUIDE_AIRFLOW_POSTGRES_LIGNE_PAR_LIGNE.html`](docs/perso/GUIDE_AIRFLOW_POSTGRES_LIGNE_PAR_LIGNE.html)
- [`GUIDE_MONITORING_STREAMLIT_LIGNE_PAR_LIGNE.html`](docs/perso/GUIDE_MONITORING_STREAMLIT_LIGNE_PAR_LIGNE.html)
- [`GUIDE_SESSION_BILAN_MENTOR.html`](docs/perso/GUIDE_SESSION_BILAN_MENTOR.html)

## Choix des outils

- `Requests` gère les APIs, le RSS et les téléchargements d’images.
- `Feedparser` interprète le RSS PolitiFact et le flux Atom The Conversation.
- `csv.DictReader` lit le TSV Fakeddit progressivement.
- Beautiful Soup extrait directement le contenu des pages The Conversation et
  nettoie le HTML PolitiFact pendant Transform.
- Scrapy et Selenium ne sont pas nécessaires : les pages The Conversation sont
  statiques et leur petit volume est correctement traité par Requests + Beautiful Soup.
