# CheckIt.AI — Acquisition de données multimodales

Ce projet extrait automatiquement du texte et des images depuis trois sources :

- NewsData.io : API REST JSON avec clé ;
- PolitiFact : flux RSS public ;
- Fakeddit : TSV local et URLs d’images Reddit.

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
uv run python scripts/run_etl.py
```

Ou lancer une seule source :

```bash
uv run python scripts/extract_newsdata.py --limit 10 --max-pages 1
uv run python scripts/extract_politifact.py --limit 20
uv run python scripts/extract_fakeddit.py --limit 100
```

Chaque script possède une aide :

```bash
uv run python scripts/extract_newsdata.py --help
```

## Sorties

```text
data/
├── raw/
│   ├── newsdata/extraction_<date>.json
│   ├── politifact/extraction_<date>.json
│   └── fakeddit/extraction_<date>.json
└── images/
    ├── newsdata/
    ├── politifact/
    └── fakeddit/

logs/
├── newsdata.log
├── politifact.log
├── fakeddit.log
└── run_extraction.log
```

Les JSON conservent les champs fournis par chaque source et ajoutent seulement
`_image_path` et `_image_size`. La normalisation vers le schéma commun sera
réalisée pendant l’étape Transform.

## Transformation

Après l’extraction, lancer le pipeline reproductible :

```bash
uv run python scripts/transform_data.py
```

Par défaut, le script sélectionne le dernier lot de chaque source. Il est aussi
possible de choisir les sources, les fichiers d’entrée et le format de sortie :

```bash
uv run python scripts/transform_data.py --sources politifact fakeddit
uv run python scripts/transform_data.py \
  --newsdata-file data/raw/newsdata/extraction_20260826T111009Z.json \
  --output-format parquet
```

Le pipeline applique les étapes suivantes :

1. lecture et contrôle des lots JSON bruts ;
2. nettoyage des textes et du HTML PolitiFact ;
3. normalisation des dates, langues, auteurs et URLs ;
4. mapping des trois sources vers 17 colonnes communes ;
5. validation du lien texte-image, de la signature et de la taille des fichiers ;
6. calcul du hash SHA-256, dédoublonnage et export.

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

Le manifeste conserve le chemin et le hash de chaque lot d’entrée ainsi que les
compteurs d’acceptation et de rejet. Le schéma conceptuel et le dictionnaire des
champs sont documentés dans
[`docs/E03_SCHEMA_CONCEPTUEL_DONNEES.md`](docs/E03_SCHEMA_CONCEPTUEL_DONNEES.md).

## Choix des outils

- `Requests` gère les APIs, le RSS et les téléchargements d’images.
- `Feedparser` interprète le flux RSS PolitiFact.
- `csv.DictReader` lit le TSV Fakeddit progressivement.
- Beautiful Soup nettoie le HTML PolitiFact pendant Transform.
- Scrapy et Selenium ne sont pas nécessaires : les sources retenues proposent
  déjà une API, un RSS ou un fichier structuré.
