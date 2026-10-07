# Guide de Contribution 

## Équipe : 
* Christian
* Guillaume
* Jérémy

---

## 1. Stratégie de Branchement

Nous utilisons une structure de branches claire pour séparer le code en production, le code en cours d'intégration et le travail en cours :

*   **`main`** : Contient uniquement le code stable. Aucune modification directe (commit) n'est autorisée. Les mises à jour se font exclusivement par Pull Request.
*   **`dev`** : Branche principale de développement et d'intégration. C'est ici que toutes les nouvelles fonctionnalités sont fusionnées et testées ensemble avant d'être envoyées sur `main`.
*   **`feat/...`** : Branches de fonctionnalité. Chaque nouvelle tâche ou fonctionnalité doit avoir sa propre branche, créée à partir de `dev`. 
    *   Exemple : `feat/extraction-donnees`, `feat/nettoyage-src`.
*   **`fix/...`** : Branches de correction de bugs, également créées à partir de `dev`.

---

## 2. Conventions des Commits

Le format d'un message de commit doit être : `<type>: <description courte et explicite>`

**Types autorisés :**
*   `feat` : Ajout d'une nouvelle fonctionnalité (ex. nouveaux scripts dans `src/`).
*   `fix` : Correction d'un bug ou d'une erreur.
*   `docs` : Modification de la documentation (`README.md`, `CONTRIBUTING.md`).

Un commit en fin de journée est nécessaire, que la feature soit fini ou non.

---

## 3. Règles des Pull Requests

En début de journée un fetch/pull est nécessaire pour se mettre à jour sur ce qui a été fait.

Toute modification du code doit passer par une Pull Request (PR) pour être intégrée à `dev`.

*   **Taille de la PR :** Les PR doivent rester **petites, concises et ciblées** sur une seule fonctionnalité. Cela facilite la relecture et évite les conflits massifs.
*   **Processus de relecture (Code Review) :**
    *   Chaque PR doit obligatoirement être relue et approuvée par **Guillaume**.
    *   Le relecteur s'assure de la clarté du code, de l'absence de données brutes dans le commit, et du respect des conventions.
    *   Le code ne peut être fusionné (merge) qu'après approbation (Approve) de la PR.

---

## 4. Gestion des Données et `.gitignore`

Notre dépôt Git est conçu pour héberger du **code source**, pas des données ou des environnements. Un fichier `.gitignore` strict est en place pour éviter de surcharger l'historique Git.

**Sont strictement interdits dans le dépôt (inclus dans le `.gitignore`) :**
*   ❌ Les données (brutes, nettoyées, bases de données). **Les données restent hors du dépôt.**
*   ❌ Les environnements virtuels (`venv`, `.env`, `__pycache__`).
*   ❌ Les notebooks de brouillon et fichiers temporaires.

**Ce qui doit être versionné :**
*   ✅ **Seuls les scripts** qui produisent, téléchargent ou traitent les données sont versionnés (rangés dans le dossier `src/`).

## 5. Rituel d'équipe

Discution de ce qui doit être fait autour d'un café OU par le biais de notre canal privé Teams si nécessaire. Récupération du contenu commit la veille.
Lors de la création d'une feature, un Excalidraw est à disposition pour marquer nos idée sur un sujet précis.