# Nutriscore

</hr>

## Équipe : 

</hr>

[Guillaume](https://github.com/G-code10)

#### 1- Installation
avec git bash
```bash
git clone https://github.com/G-code10/nutri_gui.git
cd nutri_gui/
py -3.12 -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
pip install -e.
```

#### 2- Téléchargement fichier parquet
TODO
Pour l'instant il n'existe pas de script de téléchargement automatique du fichier .parquet, celui ci est a téléchargé depuis https://huggingface.co/datasets/openfoodfacts/product-database/blob/main/food.parquet et a mettre dans le dossier data

```bash
mkdir -p data
```

Script de création de sample pour essais rapide et test sur donné réels
```bash
python -m scripts.make_sample_raw      # lit data/food.parquet écrit data/raw/sample_raw.parquet
```

#### 3- Lancement de la base de données

copier db.env.example en db.env, y choisir, le nom, un mot de passe, puis lancer 

```bash
cp db.env.example db.env
docker compose up -d
```

#### 4- Lancement de la pipeline

```bash
python -m nutriscope.pipeline all
```

Résultat attendu : 
La commande se termine sans ligne ÉCHEC et renvoie le code 0 (echo $? affiche 0).
L'étape parquet affiche le même nombre de produits pour la base et pour le Parquet.
data/exports/ contient features_nutriscore_<AAAAMMJJ>.parquet et son .schema.json ; l'étape export affiche environ 20 % de test pour chaque grade et l'empreinte SHA-256.
Chaque étape a une ligne "status": "ok" dans data/durations.jsonl
le programme indique que la base postest existe déja car celle ci est initialisé par le docker compose

#### 5- Lancer les tests

```bash
python -m pytest -q -rs
```

Les tests qui utilisent la base lisent TEST_DATABASE_URL (dans db.env) et visent une base de test, jamais la vraie. Le conteneur PostgreSQL doit être lancé.
Les tests sur données réelles sont ignorés si data/raw/sample_raw.parquet est absent(voir 2)