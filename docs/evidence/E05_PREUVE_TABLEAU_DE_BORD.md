# Preuve de fonctionnement — tableau de bord KPI

Test réalisé le 2 septembre 2026 avec le moteur de test Streamlit.

```text
Exceptions : 0
Bandeau : Pipeline opérationnel
Onglets : Qualité, Performance, Coût, Détails

Données valides             100,0 %
Texte + image complets      100,0 %
Durée du dernier run         18,8 s
Coût estimé du run           0,0005 €
Taux de succès historique   100,0 %
Volume surveillé            115,4 Mo
Stockage estimé / mois        0,0023 €
```

Les KPI ont été calculés automatiquement à partir de 1 707 occurrences brutes,
1 077 publications consolidées et trois runs Airflow réussis.

Commande de reproduction :

```bash
uv run python - <<'PY'
from streamlit.testing.v1 import AppTest

app = AppTest.from_file("dashboard/etl_kpi_dashboard.py").run(timeout=30)
print("exceptions:", len(app.exception))
print("metrics:", [(metric.label, metric.value) for metric in app.metric])
print("tabs:", [tab.label for tab in app.tabs])
PY
```

