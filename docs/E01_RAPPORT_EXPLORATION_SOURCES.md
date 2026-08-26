# CheckIt.AI — Rapport d’exploration des sources

**Étape 01 — Explorez et qualifiez les sources de données**  
**Date :** 26 août 2026

## 1. Objectif du rapport

Ce rapport identifie et compare des sources capables de fournir des publications contenant du **texte et une image associés**. Ces données serviront, dans la suite du projet, à entraîner ou évaluer un détecteur de désinformation multimodale.

Dans ce document, le traitement est toutefois limité à la partie **workflow ETL**, tout en gardant en tête l'usage qui sera fait au final des données.

**<u>Workflow ETL envisagé :</u>**

1. extraire les données depuis plusieurs types de sources ;
2. transformer et normaliser les publications ;
3. contrôler la qualité des couples texte-image ;
4. charger les données dans des fichiers réutilisables.


## 2. Critères utilisés pour qualifier une source

Une source est considérée comme intéressante si elle permet de récupérer la majorité des éléments suivants :

| Élément | Utilité dans l’ETL |
|---|---|
| Identifiant de la publication | Éviter les doublons et mettre à jour une entrée |
| Titre et texte | Conserver le contenu éditorial |
| Nom de domaine | Avoir la source de l'information |
| URL de l’image | Télécharger l’image liée à la publication |
| URL de la publication | Assurer la traçabilité |
| Date de publication | Trier et filtrer les données |
| Source et nom de domaine | Identifier l’origine du contenu |
| Auteur | Champ secondaire utile, lorsqu’il existe |
| Langue | Filtrer ou constituer un corpus multilingue |
| Fiabilité fournie | Conserver une éventuelle annotation vrai/faux |
| Origine du label | Savoir qui a produit l’annotation et selon quelle méthode |
| Date de collecte | Suivre les exécutions du pipeline |

Le point le plus important est l’**association texte-image** : l’image doit appartenir à la même publication que le texte. Une simple recherche d’images par mots-clés ne garantit pas cette relation.

### Échelle de qualité des labels

- **Élevée** : verdict produit par une organisation de fact-checking, avec justification et URL de preuve.
- **Moyenne** : label exploitable, mais produit automatiquement, déduit d’une catégorie ou dépendant d’une source moins rigoureuse.
- **Faible** : vote communautaire, flair ou opinion d’un utilisateur sans vérification externe.
- **Absente** : la source fournit des actualités, mais aucun verdict vrai/faux.

Un label décrit la méthode d’annotation d’un jeu de données ; il ne constitue jamais une vérité absolue. L’ETL le conserve avec sa provenance sans le modifier.

## 3. Cas typiques de désinformation multimodale

Les sources recherchées doivent permettre d’observer plusieurs cas :

- **image sortie de son contexte** : l’image est réelle, mais la légende, le lieu ou la date sont faux ;
- **fausse connexion** : le titre ou l’image ne correspond pas au contenu de l’article ;
- **image manipulée ou générée** : des éléments ont été ajoutés, supprimés ou créés ;
- **usurpation de source** : une image imite la présentation d’un média connu ;
- **contenu satirique repris comme une information réelle**.

Une opinion controversée reste un jugement subjectif. Une désinformation porte sur des faits vérifiables et cherche à tromper. 
L’ETL ne doit donc pas transformer automatiquement une opinion, une satire ou un contenu impopulaire en label `fake`.

## 4. Comparaison des sources identifiées

| Source | Modalités disponibles | Format et accès | Langue | Labels et qualité | Méthode d’extraction proposée |
|---|---|---|---|---|---|
| [Fakeddit](https://github.com/entitize/Fakeddit) | Titre de post, image, métadonnées Reddit, commentaires selon les fichiers | TSV et fichiers d’images à télécharger | Anglais | Labels à 2, 3 ou 6 classes. **Qualité moyenne** : annotation à grande échelle par supervision distante, donc bruit possible | Téléchargement officiel, puis `pandas` et `Requests` pour les images manquantes |
| [FakeNewsNet](https://github.com/KaiDMML/FakeNewsNet) | Texte d’article, images, date, éditeur et données sociales selon disponibilité | Index CSV, données JSON et scripts officiels | Anglais | `fake`/`real` issus de PolitiFact et GossipCop. **Qualité moyenne à élevée**, mais variable selon la collection | Scripts officiels du dépôt ; lecture CSV/JSON ; téléchargement contrôlé avec `Requests` |
| [NewsCLIPpings](https://github.com/g-luo/news_clippings) | Image d’actualité et légende associée ou falsifiée | Métadonnées JSON et images de VisualNews | Anglais | Couple image-texte `pristine` ou `falsified`. **Qualité élevée pour l’incohérence multimodale**, mais ce n’est pas un verdict factuel complet | Téléchargement officiel et lecture JSON ; pas de scraping |
| [COSMOS](https://github.com/shivangi-aneja/COSMOS) | Image, légendes provenant de contextes différents et URL d’article | Fichiers d’annotations et images accessibles selon les instructions du projet | Principalement anglais | Annotation d’utilisation hors contexte. **Qualité élevée** pour ce cas précis, mais couverture plus spécialisée | Téléchargement officiel et script Python fourni par le projet |
| [MuMiN](https://mumin-dataset.github.io/) | Claims, tweets/posts, images, articles, utilisateurs et relations | Tables et graphe via package Python ; certaines données doivent être réhydratées | 41 langues annoncées, dont le français | Labels dérivés de sites de fact-checking. **Qualité moyenne à élevée**, avec bruit possible lors de la mise en relation automatique | Package officiel ; APIs des plateformes si les conditions d’accès le permettent |
| [NewsData.io](https://newsdata.io/documentation) | Titre, résumé, contenu, image, date, auteur, pays, catégorie et source | API REST, réponse JSON | Multilingue, dont français | Aucun label vrai/faux. **Label absent** | `Requests` sur l’API officielle, avec pagination et téléchargement séparé des images |
| [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search) | Claim, auteur du claim, verdict textuel, fact-checker, date et URL ; image non garantie | API REST, réponse JSON | Multilingue | Verdict produit par un fact-checker. **Qualité élevée et traçable**, mais les échelles de verdict sont hétérogènes | `Requests` sur l’API officielle ; enrichissement éventuel depuis la page source |
| [NewsAPI](https://newsapi.org/docs) | Titre, description, extrait, URL d’image, date, auteur et source | API REST, réponse JSON | Plusieurs langues, dont français | Aucun label vrai/faux. **Label absent** | `Requests` ; solution de remplacement à NewsData.io |
| [PolitiFact](https://www.politifact.com/rss/) | Claim, verdict, résumé, date, URL d’article et illustrations de page | Flux RSS/XML et pages HTML | Principalement anglais | Échelle Truth-O-Meter. **Qualité élevée**, avec justification éditoriale | `Feedparser` pour le RSS, puis `Requests` + `Beautiful Soup` pour la page et son image |
| [Reddit Data API](https://redditinc.com/policies/data-api-terms) | Titre, texte, image ou lien, commentaires, auteur et date | API REST JSON, OAuth ; bibliothèque PRAW possible | Multilingue | Pas de label fiable natif. Flairs et votes : **qualité faible** | API officielle/PRAW ; source secondaire, non retenue pour le pipeline principal |

### Remarque sur les catalogues de données

[Google Dataset Search](https://datasetsearch.research.google.com/), [Hugging Face Datasets](https://huggingface.co/datasets), [Kaggle](https://www.kaggle.com/datasets) et [public-apis.io](https://publicapis.io/) sont surtout des **outils de découverte ou d’hébergement**. Ils aident à trouver une source, mais ne garantissent ni la qualité des labels, ni la licence, ni la présence réelle des images.

Avant d’utiliser un dataset trouvé dans un catalogue, il faut donc remonter à sa publication ou à son dépôt officiel et vérifier :

- qui a créé les labels ;
- si les images sont incluses ou seulement référencées par des URLs ;
- si le lien texte-image est conservé ;
- si les données peuvent être téléchargées et réutilisées.

## 5. Analyse des sources les plus utiles

### 5.1 Fakeddit — dataset multimodal volumineux

Fakeddit est directement adapté à l’étude de contenus trompeurs sur les réseaux sociaux. Chaque exemple peut associer un titre Reddit à une image. Le dataset propose plusieurs niveaux de classification, ce qui le rend pratique pour comprendre qu’un label ne se limite pas toujours à `true` ou `fake`.

**Avantages :** volume important, texte et image déjà associés, format tabulaire simple.  
**Limites :** corpus anglophone ; labels issus d’une supervision distante et donc potentiellement bruités.

**Usage dans ce projet :** source batch permettant de tester l’import de fichiers TSV et d’images, sans entraîner de modèle.

### 5.2 FakeNewsNet — articles et fact-checking

FakeNewsNet regroupe deux collections : PolitiFact pour les sujets politiques et GossipCop pour les actualités people. Les fichiers contiennent des identifiants et des métadonnées ; les scripts du dépôt permettent de récupérer les contenus encore disponibles.

**Avantages :** labels documentés, données proches d’un cas réel d’article de presse, métadonnées sociales possibles.  
**Limites :** dépendance à des pages et APIs externes ; liens anciens parfois indisponibles ; qualité différente entre PolitiFact et GossipCop.

**Usage dans ce projet :** source batch de référence pour étudier l’import CSV/JSON et la gestion des URLs devenues invalides.

### 5.3 NewsCLIPpings et COSMOS — cohérence entre texte et image

Ces deux datasets portent spécifiquement sur la relation entre une image et son contexte textuel. Ils sont utiles pour les cas où l’image est réelle, mais associée à une mauvaise légende.

Leurs labels ne signifient pas nécessairement que tout l’article est faux. Ils indiquent surtout si le **couple image-texte** est cohérent ou hors contexte. Cette distinction doit être conservée dans le schéma de données.

**Usage dans ce projet :** exemples de formats d’annotation spécialisés ; import facultatif si le temps le permet.

### 5.4 NewsData.io — meilleure source pour l’ETL automatisé

NewsData.io fournit des actualités récentes sous forme de JSON. Les réponses peuvent inclure le titre, la description, le contenu, l’URL de l’article, l’URL d’image, la date, la langue et la source.

**Avantages :** API officielle, appels simples, données récentes, filtre de langue, aucune navigation dans un navigateur.  
**Limites :** contenus parfois tronqués, image parfois absente, quota du plan gratuit, aucun label vrai/faux.

**Usage dans ce projet :** source principale pour démontrer une extraction automatisée avec `Requests`, pagination, contrôles de champs et téléchargement d’images.

### 5.5 Google Fact Check Tools API — labels traçables

Cette API permet de rechercher des claims déjà examinés par des organisations de fact-checking. Elle renvoie notamment le texte de l’affirmation, son auteur, la date, le nom du fact-checker, l’URL de la vérification et un verdict textuel.

**Avantages :** accès officiel, provenance claire du verdict, plusieurs langues.  
**Limites :** l’image n’est pas garantie ; les verdicts ne suivent pas tous la même échelle (`False`, `Mostly false`, etc.).

**Usage dans ce projet :** source complémentaire de métadonnées de fact-checking. Le verdict est conservé tel quel dans `source_label_raw`, sans le convertir automatiquement en vrai/faux.

### 5.6 RSS et pages HTML — PolitiFact ou autre média autorisé

Un flux RSS fournit une liste structurée de publications récentes. Il contient souvent le titre, la date, le résumé et le lien de l’article. Si l’image n’est pas présente dans le flux, la page HTML peut être consultée pour lire sa balise Open Graph `og:image`.

**Avantages :** format léger, souvent sans authentification, adapté à une collecte périodique.  
**Limites :** contenu parfois incomplet ; structure HTML susceptible de changer ; il faut respecter les règles du site.

**Usage dans ce projet :** démonstration pédagogique de `Feedparser`, puis `Requests` et `Beautiful Soup` sur un petit nombre de pages.

## 6. Outils d’extraction et cas d’utilisation

| Outil | Rôle | Source adaptée dans le projet | Quand l’utiliser |
|---|---|---|---|
| `Requests` | Envoyer des requêtes HTTP et télécharger JSON, HTML ou images | NewsData.io, Google Fact Check API, NewsAPI | Une API ou une URL directe est disponible |
| `Feedparser` | Lire et convertir un flux RSS/Atom | RSS de PolitiFact ou d’un média | Le site publie un flux structuré |
| `Beautiful Soup` | Extraire quelques champs d’une page HTML | Article obtenu depuis un RSS | Le HTML est déjà reçu avec `Requests` et peu de pages sont parcourues |
| `Scrapy` | Explorer beaucoup de pages avec files d’attente, règles et pipelines | Archives publiques d’un site de fact-checking | Plusieurs dizaines ou centaines de pages doivent être parcourues régulièrement |
| `Selenium` | Piloter un navigateur et exécuter JavaScript | Démonstration sur une page dynamique sans API équivalente | Le contenu apparaît seulement après interaction ou exécution JavaScript |
| `pandas` | Lire, filtrer et convertir CSV/TSV/JSON | Fakeddit et FakeNewsNet | Un dataset est déjà disponible sous forme de fichiers |

### Choix pédagogique par source

- **NewsData.io → Requests** : apprendre l’appel d’API, la clé, les paramètres et la pagination.
- **PolitiFact RSS → Feedparser** : apprendre à lire un flux XML sans scraper tout le site.
- **Page d’article → Requests + Beautiful Soup** : récupérer `og:image`, le texte et la date manquants.
- **Archive de fact-checking → Scrapy** : comprendre un crawler structuré et limité.
- **Page dynamique → Selenium** : montrer le dernier recours lorsque le HTML initial ne contient pas les données.

Selenium est plus lent et plus fragile. Une API, un dataset officiel ou un RSS doit être préféré lorsqu’il existe.

## 7. Comment savoir comment interroger une source ?

Pour chaque nouvelle source, la vérification suit le même ordre :

1. rechercher une documentation API officielle ;
2. chercher un dataset ou un script de téléchargement officiel ;
3. rechercher un flux RSS/Atom dans le site ou son en-tête HTML ;
4. consulter les conditions d’utilisation et le fichier `robots.txt` ;
5. observer une page HTML avec les outils de développement du navigateur ;
6. utiliser Selenium uniquement si les données sont générées par JavaScript et qu’aucun accès plus direct n’existe.

### Exemples de requêtes API

Les clés ne doivent pas être écrites directement dans le code. Elles sont placées dans un fichier `.env` exclu de Git, puis lues avec `os.getenv()`.

#### NewsData.io

```http
GET https://newsdata.io/api/1/latest?apikey=VOTRE_CLE&language=fr&image=1&q=politique
```

Paramètres utiles : `language`, `q`, `country`, `category`, `image` et `page`. La pagination utilise le jeton `nextPage` renvoyé dans la réponse. La documentation annonce actuellement un crédit par requête et un quota dépendant de l’abonnement ; le code doit donc lire les réponses `429` et ne pas supposer un quota permanent.

#### Google Fact Check Tools API

```http
GET https://factchecktools.googleapis.com/v1alpha1/claims:search?query=climat&languageCode=fr&key=VOTRE_CLE
```

L’accès utilise une clé Google API. Les paramètres principaux sont `query`, `languageCode`, `pageSize` et `pageToken`. Le quota applicable est visible dans la console Google Cloud du projet.

#### NewsAPI

```http
GET https://newsapi.org/v2/everything?q=climat&language=fr&pageSize=20&page=1
X-Api-Key: VOTRE_CLE
```

Le plan Developer annonce actuellement 100 requêtes par jour et un usage limité au développement.

### Exemple de requête Python robuste

```python
import os
import requests

response = requests.get(
    "https://newsdata.io/api/1/latest",
    params={
        "apikey": os.getenv("NEWSDATA_API_KEY"),
        "language": "fr",
        "image": 1,
    },
    timeout=20,
)
response.raise_for_status()
payload = response.json()
```

Le pipeline doit aussi gérer les délais d’attente, les erreurs temporaires, la pagination et les réponses `429 Too Many Requests`.

## 8. Scraping : vérifications simples

Le scraping n’est pas automatiquement autorisé ou interdit dans tous les cas. Il dépend notamment du contenu collecté, des conditions du site, du droit d’auteur, des droits sur les bases de données et des données personnelles. La [CNIL recommande une analyse au cas par cas](https://www.cnil.fr/fr/focus-interet-legitime-collecte-par-moissonnage-web-scraping).

Pour ce projet étudiant, les règles simples suivantes sont retenues :

- préférer une API officielle, un téléchargement officiel ou un RSS ;
- lire les conditions d’utilisation et `https://domaine/robots.txt` ;
- limiter la fréquence des requêtes et identifier le script si nécessaire ;
- ne pas contourner un compte, un paywall, un CAPTCHA ou une interdiction technique ;
- ne collecter que les champs utiles au projet ;
- conserver les URLs et la provenance ;
- ne pas redistribuer les images si leur licence ne le permet pas.

Une autorisation dans `robots.txt` ne constitue pas à elle seule une licence juridique. À l’inverse, son absence ne signifie pas que toute extraction est libre. En cas de doute, la source est écartée au profit d’une API ou d’un dataset documenté.

## 9. Format de sortie proposé

### 9.1 Organisation des fichiers

```text
data/
├── raw/
│   ├── newsdata/2026-08-26.jsonl
│   ├── rss/2026-08-26.xml
│   └── datasets/
├── images/
│   └── <publication_id>.jpg
├── processed/
│   └── publications.parquet
└── rejected/
    └── invalid_records.jsonl
```

- **JSONL brut** : conserve la réponse d’origine, une publication par ligne.
- **Parquet normalisé** : compact, typé et efficace pour l’analyse.
- **Dossier images** : évite de dépendre uniquement d’URLs susceptibles de disparaître.
- **Rejets JSONL** : conserve les entrées incomplètes avec la raison du rejet.

CSV reste possible pour une vérification manuelle, mais il gère moins bien les textes longs, les listes et les champs imbriqués.

### 9.2 Schéma commun d’une publication

| Champ | Règle |
|---|---|
| `publication_id` | Identifiant stable et unique, préfixé par la source |
| `source_name` | Nom de la source d’acquisition |
| `source_domain` | Domaine de la publication, sans `www.` |
| `source_url` | URL de la publication, pas celle de l’API |
| `title` | Titre de la publication |
| `text` | Contenu, résumé ou affirmation examinée |
| `image_url` | URL de l’image associée à cette publication |
| `image_path` | Chemin local après téléchargement réussi |
| `published_at` | Date fournie par la source, normalisée en UTC |
| `language` | Code ISO comme `fr` ou `en` |
| `author` | Chaîne ou `null` |
| `source_label_raw` | Label original, sans modification |
| `source_label_scheme` | Système de labels utilisé |
| `label_provenance` | Organisation ou méthode ayant produit le label |
| `collected_at` | Date UTC de l’extraction |

Règles importantes
- source_url désigne l’article ou le post, jamais https://newsdata.io/api/....
- image_path reste null jusqu’au téléchargement réussi.
- published_at et collected_at ne doivent pas être confondus.
- Les champs de labels existent toujours, même lorsqu’ils valent null.
- Un extracteur ne doit jamais inventer un label manquant.
- Utilise null dans JSON, mais None dans Python.

```json
{
  "publication_id": "newsdata_12345",
  "source_name": "NewsData.io",
  "source_domain": "example.org",
  "source_url": "https://example.org/article",
  "title": "Titre de la publication",
  "text": "Texte ou résumé disponible",
  "image_url": "https://example.org/image.jpg",
  "image_path": "data/images/newsdata_12345.jpg",
  "published_at": "2026-08-26T08:00:00Z",
  "language": "fr",
  "author": null,
  "source_label_raw": null,
  "source_label_scheme": null,
  "label_provenance": null,
  "collected_at": "2026-08-26T09:00:00Z"
}
```


Pour un dataset labellisé, `source_label_raw` conserve la valeur originale, par exemple `mostly-false` ou `out-of-context`. Le pipeline ne la transforme pas silencieusement en `fake`.

## 10. Workflow ETL proposé

```text
Sources
  ↓
Extracteurs dédiés (API, RSS, HTML, fichiers)
  ↓
Données brutes JSONL/XML + images
  ↓
Normalisation vers le schéma commun
  ↓
Contrôles qualité et dédoublonnage
  ↓
Parquet final + journal des rejets
```

### Extract

- appeler les APIs avec `Requests` ;
- parcourir le RSS avec `Feedparser` ;
- compléter quelques pages avec `Beautiful Soup` ;
- importer les CSV, TSV et JSON des datasets ;
- télécharger l’image et mémoriser son URL d’origine.

### Transform

- uniformiser les dates en UTC et la langue en code ISO ;
- nettoyer les espaces sans altérer le texte ;
- générer un identifiant stable à partir de la source et de l’URL ;
- conserver les labels et leur provenance dans des champs séparés ;
- calculer un hash de l’URL ou de l’image pour détecter les doublons.

### Load

- écrire les données brutes sans les écraser ;
- enregistrer les images valides ;
- produire le fichier Parquet normalisé ;
- isoler les publications invalides dans le journal des rejets.

### Contrôles de qualité minimaux

Une publication est acceptée si :

- son titre ou son texte n’est pas vide ;
- son URL de publication est valide ;
- son image est rattachée à la même entrée et a pu être téléchargée ;
- son type MIME commence par `image/` ;
- sa date et sa source sont conservées ;
- le même identifiant n’existe pas déjà.

Le workflow doit être relançable sans créer de doublons. Il doit utiliser des timeouts, quelques nouvelles tentatives sur les erreurs temporaires, un journal d’exécution et un point de reprise pour la pagination.

## 11. Recommandation finale

Pour rester simple tout en montrant plusieurs méthodes d’acquisition, nous suivrons la combinaison suivante :

1. **Source principale : NewsData.io avec Requests**  
   Elle fournit simplement des actualités récentes, multilingues, avec texte, métadonnées et souvent une image. Elle convient au pipeline automatisé principal.

2. **Source complémentaire : flux RSS de PolitiFact avec Feedparser**  
   Il permet de manipuler des données structurées différentes d’une API et d’observer des verdicts de fact-checking.

3. **Enrichissement HTML : Beautiful Soup**  
   Il récupère l’image Open Graph ou quelques champs absents du RSS, sur un nombre limité de pages.

4. **Démonstration pédagogique : Scrapy sur une archive publique**  
   Un petit spider peut parcourir plusieurs pages en respectant le débit autorisé. Selenium peut être présenté sur une page dynamique, mais il n’est pas nécessaire au pipeline final.

5. **Jeux de données de référence : Fakeddit, FakeNewsNet et NewsCLIPpings**  
   Ils montrent différents formats et différentes définitions des labels. Ils peuvent être importés en batch pour valider le schéma ETL, sans entraîner de modèle dans le périmètre actuel.

La sortie recommandée est **JSONL pour les données brutes**, **Parquet pour les publications normalisées** et un **dossier local pour les images**. Cette solution reste claire, modulaire, relançable sans intervention et adaptée à un projet étudiant.

## 12. Conclusion

Les sources étudiées répondent à des besoins différents : les APIs et RSS fournissent des données récentes, tandis que les datasets apportent des exemples multimodaux déjà annotés. La qualité d’un label dépend de sa provenance : un verdict de fact-checker est généralement plus fiable qu’un flair communautaire, et un label de cohérence image-texte ne doit pas être confondu avec un verdict vrai/faux.

Le projet CheckIt.AI retiendra donc un **ETL multi-source centré sur l’acquisition, la normalisation, la traçabilité et la qualité des couples texte-image**. La construction d’un détecteur et l’entraînement d’un modèle restent hors périmètre de cette étape et du workflow à réaliser.

## Références principales

- [Multimodal Fake News Detection: A Survey](https://www.ijci.zu.edu.eg/index.php/ijci/article/view/102/86)
- [Fakeddit — dépôt officiel](https://github.com/entitize/Fakeddit)
- [FakeNewsNet — dépôt officiel](https://github.com/KaiDMML/FakeNewsNet)
- [NewsCLIPpings — dépôt officiel](https://github.com/g-luo/news_clippings)
- [COSMOS — dépôt officiel](https://github.com/shivangi-aneja/COSMOS)
- [MuMiN — site du dataset](https://mumin-dataset.github.io/)
- [NewsData.io — documentation](https://newsdata.io/documentation)
- [Google Fact Check Tools API — documentation](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search)
- [NewsAPI — documentation](https://newsapi.org/docs)
- [CNIL — collecte par moissonnage web](https://www.cnil.fr/fr/focus-interet-legitime-collecte-par-moissonnage-web-scraping)
