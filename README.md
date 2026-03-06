# SISE Challenge — WebMining

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-%3E%3D2.0-lightgrey.svg)](https://flask.palletsprojects.com/)

**Bref résumé**

Application Flask pour l'exploration et l'analyse de comportements utilisateurs (boutique de démonstration). Interface web, endpoints AJAX, visualisations et composants ML (PCA, clustering, modèles supervisés).

---

## Table des matières

1. [Fonctionnalités](#fonctionnalit%C3%A9s)
2. [Prérequis](#pr%C3%A9requis)
3. [Installation locale (avec `uv`)](#installation-locale-avec-uv)
4. [Docker — Pull image depuis Docker Hub](#docker--pull)
5. [Configuration (.env)](#configuration-env)
6. [Lancer l'application](#lancer-lapplication)
7. [Présentation / Démo](#pr%C3%A9sentation--d%C3%A9mo)
8. [Structure du projet (détaillée)](#structure-du-projet-d%C3%A9taill%C3%A9e)
9. [Notes rapides](#notes-rapides)

---

## Fonctionnalités

- Interface web avec affichage de produits et analytics
- Endpoints AJAX pour chargement dynamique (ex. `/ajax/render_products`)
- Affichage de la variance expliquée par la PCA
- Modèles et artefacts ML dans `data/models`
- Prêt pour déploiement en container (Hugging Face Spaces / Docker)

---

## Prérequis

- Python 3.13+
- Docker (pour exécuter l'image si vous utilisez `docker pull`)
- `uv` pour la gestion des dépendances et de l'environnement (obligatoire)

---

## Installation locale (avec `uv`)

1. Clonez le dépôt:

```bash
git clone <repo-url>
cd SISE-Challenge-WebMining
```

2. Créez l'environnement et installez les dépendances avec `uv`:

```bash
# crée un environnement géré par uv
uv venv

# activez l'environnement (Windows exemple)
.\.venv\Scripts\activate

# installe les dépendances définies par le projet
uv sync
```

3. Copiez l'exemple d'environnement et éditez `.env`:

```bash
cp .env.example .env
# puis éditez .env pour remplir les variables nécessaires
```

---

## Docker — Pull image depuis Docker Hub

Si une image publique est disponible sur Docker Hub, vous pouvez la récupérer et lancer le conteneur :

```bash
docker pull boroto/sise-challenge-webmining:lastest

# lancer le container (expose port 7860)
docker run --rm -p 7860:7860 boroto/sise-challenge-webmining:latest
```

Remplacez `boroto/sise-challenge-webmining:latest` par votre image si nécessaire.

---

## Configuration (.env)

Copiez `.env.example` en `.env` et renseignez les variables essentielles :

- `DEBUG=1` ou `0`
- `PORT=7860`
- `DATA_PATH` (si vous déplacez le dossier `data/`)

---

## Lancer l'application

Mode développement (local):

```bash
python run.py
# ouvrez http://127.0.0.1:7860
```

Mode production (Gunicorn) :

```bash
gunicorn -c gunicorn_conf.py wsgi:app
```

---

## Présentation / Démo

Ajoutez ici une courte présentation destinée à un public non-technique et les étapes de la démo.

Points recommandés pour la présentation :

- Objectif de l'application (1 phrase)
- Scénario de démonstration pas à pas (3–5 étapes)
- Commandes rapides pour reproduire la démo localement

Exemple de script de démo rapide :

1. `python run.py`
2. Ouvrir la page principale
3. Sélectionner une catégorie → la liste des produits se charge via AJAX
4. Aller dans Analytics → afficher le scatter et lire la variance PCA

---

## Structure du projet (détaillée)

Voici la structure réelle et commentée pour vous repérer rapidement :

```
SISE-Challenge-WebMining/
├── app/
│   ├── __init__.py                # application factory, configuration
│   ├── ajax.py                    # endpoints AJAX (render_products, projection...)
│   ├── routes.py                  # HTML page routes
│   ├── behavior_model/            # comportement: feature_builder, model_manager
│   ├── input_model/               # input-specific feature_builder, model_manager
│   ├── services/                  # product_data, user_service, etc.
│   ├── static/                    # js/, css/, images/
│   └── templates/                 # jinja2 templates and elements
├── data/
│   ├── features/                  # JSONL feature files
│   └── models/                    # joblib / npy / scaler / pca
├── models/                        # optional python model wrappers
├── schemas/                       # marshmallow/pydantic schemas
├── services/                      # light service wrappers used by app
├── utility/                       # data_connector, storage, protocols
├── scripts/                       # tools (selenium_bot.py)
├── logs/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── run.py
└── README.md
```

Descriptions rapides :

- `app/behavior_model` : construction des features comportementales et gestion des modèles
- `app/input_model` : features + modèle pour le suivi des interactions d'entrée
- `app/static/js` : `layout.js`, `tracker.js`, modules pour scatter/plots
- `data/models` : contient `pca_final.joblib`, `scaler_final.joblib`, `kmeans_final.joblib`, etc.

---

## Notes rapides

- Si certaines requêtes sont bloquées côté navigateur, testez en désactivant temporairement les extensions de blocage (adblock, tracking protection).
- Sur Hugging Face Spaces, après push, forcer un rebuild si nécessaire pour assurer que les assets statiques sont mis à jour.

---

Fin du README.
