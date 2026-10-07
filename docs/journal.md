# TP1 - Démarrage
<hr>

## Choix du format
<hr>

Nous avons choisi le format .parquet, c'est le format le plus léger entre le CSV de 9Go et celui-ci de 7.2Go. <br>

Nous l'avons choisi pour sa capacité à lire les colonnes séparémment. Sa réputation sur ses performance nous a confirmé dans cette direction.

# TP2 - PRofiling & périmètre

Renseigné les valeurs vides sur la majorité des colonnes dans le perimetre.
Il faudra vérifier les colonnes s'approchant des 0% de valeur nulles, ceci est surement dû au fait que la colonnes ont un formattage pré-établi, il faudra éclater la structure et récupérer les valeurs nulles présentes sur les différents éléments de la structure.

## 