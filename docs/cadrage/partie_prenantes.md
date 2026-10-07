# Introduction

Dans ce documents nous allons établir différents personas, une trame d'entretien et le compte-rendu de celui-ci.

<strong>Objectif</strong> : savoir pour qui on construit NutriScope et qui décide quoi.

# Carte des parties prenantes du projet

> Direction, marketing, équipe data, utilisateurs finaux, Open Food Facts (fournisseur de données), délégué à la protection des données. Pouvoir/intérêt pour chacune — le cadre
réglementaire (RGPD, AI Act) est une contrainte, pas une partie prenante.

<img src ="./asset/Carte_des_parties_prenantes_du_projet.png">

# Personas

> <strong>Trois personas utilisateurs, réalistes et différenciés</strong> : par exemple parent pressé en hypermarché, personne
diabétique, étudiant petit budget. Objectifs, freins, situation d'usage.

# Persona 1 - Philipe

<img src ="./asset/persona_1.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : il souhaiterais pouvoir avoir rapidement le nutriscore et pouvoir vérifier le nombre de calories et les nutriments en un coup d’oeil

<strong>Freins</strong> : si il scanne et qu’il ne récupère pas le nutriscore, si il faut plusieurs manip

<strong>Situation d’usage </strong>: phillipe scanne un produit et voudrais savoir si celui ci sera assez nutritif pour pouvoir l’inclure dans ce qu’il va manger a la semaine
</pre>
</details>


# Persona 2 - Clarice

<img src ="./asset/persona_2.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : elle souhaiterais pouvoir afficher rapidement les allergènes d’un produit

<strong>Freins</strong> : si les allergène ne sont pas présenté clairement ou si la fonctionnalité demande trop de manipulations

<strong>situation d’usage</strong> : clarice scanne un produit avec énormément d’ingrédients et voudr ais que les allergènes soit écrit de manière évidente sur son application
</pre>
</details>

# Persona 3 - Xavier

<img src ="./asset/persona_3.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : il souhaiterais pouvoir avoir un nutriscore calculé sur les produits qui n’en affiche pas

<strong>Freins</strong> : si le nutriscore n’est pas calculé ou prédit, si celui ci est totalement faux ou incohérent

<strong>situation d’usage</strong> : xavier scanne un produit nouveau qui n’a aucun nutriscore et voudrais pouvoir le comparer a d’autres produits
</pre>
</details>

# Trame d'entretien

> 10 questions pour valider les besoins.

## Cible

- Souhaitez-vous que l'application s'adresse uniquement aux consommateurs français pour le lancement ?

- Parmi nos différents profils cibles, lequel considérez-vous comme la priorité absolue pour notre lancement ?

- L'application doit-elle être accessible à des personnes n'ayant aucune connaissance préalable en nutrition ?

## Performance

- Quels seront les 2 ou 3 indicateurs clés de performance (KPI) qui vous prouveront que la première version est un succès ?

## Fonctionnalité

- À quel moment précis de leur journée imaginez-vous nos utilisateurs ouvrir l'application ? (Permet d'avoir des informations sur les fonctionnalités et la charge d'info à l'écran)

- La reconnaissance d'images (scanner un produit sans code-barres) est-elle perçue comme un "gadget" ou une fonctionnalité critique ?

## Organisation 

- Comment souhaitez-vous être informés de l'avancement du projet ? (Fréquence, plateforme, ...)

## Données

- Notre matière première est la base Open Food Facts. Quelle est votre tolérance face aux inévitables données manquantes ou erronées que nous allons rencontrer ? 

- Concernant les données, quel est notre périmètre de récupération ? Sur quels pays ?

- Comment fonctionne-t-on pour la priorité des produits avec un Nutriscore équivalent ? Par quel élément prioriser ?

## Budget (Bonus)

- Pour vous proposer un chiffrage adapté, avez-vous une enveloppe budgétaire en tête, même approximative ?

# Compte-rendu d'entretien

## Cible

Pas de préférence pour la MVP (Minimum Valuable Product)

Profil typique : Foyer pressé, pendant les courses

## Performance

KPI : 
- 12 mois
- 100 000 utilisateurs (inscrits)
- 30 000 actifs
- 40% de rebonds
- 4.2/5 (note)

*Bonus* :
- Compte (pas pour le lancement)
- Offre payante
- Signer 2 partenariats

## Fonctionnalité

Pas certain de cette information : Un système de panier dans l'app

Informations dispo. explication synthétique --> alternatives.

Afficher les sources et données manquantes

## Organisation

Pas de préférence --> Démonstration dans 10 semaines

## Données

**Vrai enjeu**, transparence, une certaine dépendance aux données préexistantes et ajout.

Complément d'info à l'avenir : Prix & Nutriscore (si nécessaire)

Afin de priorisé il faudra filtrer par les données existantes sur le facteur nutritionnel, le prix, les allergènes etc...

## Budget (Bonus)

120 000€ 
- Conception
- Dev
- Hébergement

# Mise à jour - après entretien

> Ce qui a été confirmé, infirmé, découvert.

## Carte des parties prenantes du projet

<img src ="./asset/Carte_des_parties_prenantes_du_projet_maj.png">

## Personas

### Persona 1 - Philipe
> 37 ans, père de 2 enfants en bas âge

<img src ="./asset/persona_1_maj.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : Pouvoir donner une "meilleure" alimentation à ses enfants et lui-même.

<strong>Freins</strong> : La vaste variété de choix/produits.

<strong>situation d’usage</strong> : En magasin accompagné de ses 2 enfants.
</pre>
</details>

### Persona 2 - Clarice
> 21 ans, célibataire, étudiante

<img src ="./asset/persona_2_maj.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : S'alimenter sainement à prix réduit

<strong>Freins</strong> : Budget

<strong>situation d’usage</strong> : Pas le temps de passer 1 heure en magasin, mémoire à faire.
</pre>
</details>

### Persona 3 - Xavier
> 27 ans, diététicien

<img src ="./asset/persona_3_maj.png">
<details>
<summary>Pas d'image ? Texte ici ...</summary>
<pre>

<strong>Objectif</strong> : Accompagner sa clientèle sur comment trouver les bons substitues. 

<strong>Freins</strong> : Différentes app disponibles, laquelle choisir ?

<strong>situation d’usage</strong> : En rendez-vous et/ou en magasin avec son client.
</pre>
</details>