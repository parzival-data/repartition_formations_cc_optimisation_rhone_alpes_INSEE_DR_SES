# Modélisation algorithmique complète

## 1. Finalite du document

Ce document décrit l'algorithme complet utilisé par l'outil d'optimisation des
sessions de formation des coordonnateurs communaux PC/TPC pour l'EAR 2027. Il
sert de référence pour comprendre le lien entre les données d'entrée, la
construction du modèle CP-SAT, la résolution, la validation et les exports.

Le texte décrit l'état reel du code. Une règle, une contrainte ou un workflow
n'est présente comme existant que s'il est effectivement implémenté. Les
extensions non codees sont signalees comme limites ou perspectives.

Trois niveaux doivent être distingues pendant toute la lecture :

- les contraintes dures, qui definissent la faisabilité mathématique ;
- les pénalités de l'objectif, qui orientent le choix entre solutions faisables ;
- les contrôles de diagnostic, de validation, d'export et de carte, qui aident à
  qualifier une solution mais ne remplacent pas l'expertise métier.

## 2. Vue d'ensemble du pipeline

Le pipeline applique par le projet suit une chaîne volontairement séparée en
étapes. Chaque étape produit des objets ou fichiers réutilisables par l'étape
suivante, ce qui rend le calcul plus contrôlable et facilite l'audit.

```text
Donnees brutes
-> donnees preparees
-> parametres derives
-> diagnostic pre-resolution
-> modele CP-SAT
-> resolution
-> extraction de solution
-> validation
-> exports
-> carte HTML
```

En pratique, la séquence opérationnelle est la suivante :

```text
1. Charger la configuration YAML.
2. Préparer les donnees brutes si necessaire.
3. Charger les CSV propres.
4. Construire les ensembles, couts et relations admissibles.
5. Executer les diagnostics pre-resolution.
6. Construire le modele CP-SAT.
7. Resoudre le modele.
8. Si le solveur trouve une solution :
      extraire la solution metier ;
      valider la solution extraite ;
      produire les exports et, si demandé, la carte.
   Sinon :
      analyser le statut solveur ou utiliser le workflow d'assouplissement.
```

Cette séparation est importante : le solveur manipule des variables CP-SAT,
tandis que les exports manipulent une solution métier reconstruite et validée.
Les fichiers de restitution ne sont donc pas la source initiale de validation ;
ils sont produits après la validation.

## 3. Données d'entrée et préparation

Le solveur ne lit pas directement les fichiers bruts. Les données réelles sont
d'abord préparées par la commande `prepare-data`, qui transforme les fichiers
source en tables propres exploitees par les modules de chargément.

Le fichier des communes fournit les identifiants INSEE, les noms, la population,
la catégorie `PC` ou `TPC`, et des champs optionnels comme le territoire EAR, le
nombre de logements, la latitude et la longitude. Ces données permettent de
calculér le nombre de coordonnateurs communaux à former et de connaître la
catégorie métier de chaque commune.

Le fichier des temps de trajet fournit des temps orientes entre une commune
origine et une commune candidate pivot. Un trajet absent est traité comme
interdit : il ne cree pas de variable d'affectation. La préparation ne complété
pas automatiquement les trajets diagonaux `i -> i`; si un trajet diagonal doit
être admissible avec un temps nul, il doit être présent dans les données propres.

Le fichier de coordonnées est optionnel pour l'optimisation. Lorsqu'il est
présent, ses latitudes et longitudes sont jointes aux communes et servent à la
carte HTML. Une commune sans coordonnées peut tout de même être affectée et
apparaitre dans les exports non cartographiques.

Le fichier de compatibilités est également optionnel. S'il est absent, le code
considere que toutes les compatibilités métier valent `1` par défaut. S'il est
présent, il permet d'interdire certains couples commune-pivot avant même la
creation des variables d'affectation.

Les principales sorties de préparation sont :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` si une source de compatibilités est
  disponible.

## 4. Ensembles du modèle

On note d'abord l'ensemble des communes à affecter :

$$
C = \text{ensemble des communes à affecter}
$$

Cet ensemble contient toutes les communes chargées depuis le fichier propre des
communes.

Les communes PC et TPC forment deux sous-ensembles de `C` :

$$
P \subset C
$$

$$
T \subset C
$$

Le code suppose que chaque commune appartient à une seule catégorie :

$$
C = P \cup T
\qquad
P \cap T = \varnothing
$$

Ici, `T` designe l'ensemble des communes TPC. Il ne faut pas le confondre avec
le paramètre de temps maximal, également noté `T` dans la configuration. Le
contexte indique toujours s'il s'agit d'un ensemble ou du seuil de trajet.

Toutes les communes sont candidates pivot :

$$
F = C
$$

Cela signifie que le modèle autorise toute commune chargée à héberger une
session potentielle, sous reserve des autres contraintes et pénalités. Cette
égalite ne signifie pas qu'une commune pivot ouverte est automatiquement membre
de sa propre session : le modèle actuel ne force pas cette auto-affectation.

Les sessions candidates sont indexees par une commune pivot `j` et un rang de
slot `m` :

$$
S = \{(j,m) : j \in F, m \in \{1,\dots,M_j\}\}
$$

Le nombre de slots depend de la catégorie de la commune pivot :

$$
M_j =
\begin{cases}
3 & \text{si } j \in P,\\
1 & \text{si } j \in T.
\end{cases}
$$

Une commune PC peut donc porter jusqu'à trois sessions candidates, tandis qu'une
commune TPC ne peut porter qu'une session candidate. Ces slots sont seulement
des possibilites : une session candidate devient reelle uniquement si sa
variable d'ouverture vaut `1`.

## 5. Paramètres métier

On note `p_i` la population de la commune `i`. Le nombre de coordonnateurs
communaux à former depend de cette population :

$$
q_i =
\begin{cases}
1 & \text{si } p_i \leq 5000,\\
2 & \text{si } p_i > 5000.
\end{cases}
$$

Cette règle est codee dans `parameters.py` et validée par la configuration. Elle
permet de raisonner en chargé de formation, pas seulement en nombre de communes.

Le temps de trajet de la commune `i` vers le pivot `j` est noté :

$$
\tau_{ij} \geq 0
$$

Les temps sont orientes : un trajet `i -> j` et un trajet `j -> i` sont deux
entrées distinctes si les données les fournissent.

Le seuil maximal de trajet configuré est note `T`. Un couple commune-pivot est
admissible seulement si le trajet existe et respecte ce seuil :

$$
a_{ij} =
\begin{cases}
1 & \text{si le trajet } i \to j \text{ existe et } \tau_{ij} \leq T,\\
0 & \text{sinon.}
\end{cases}
$$

Un trajet absent donne donc `a_ij = 0`. Il ne s'agit pas d'une forte pénalité :
le couple est retire du modèle d'affectation.

La compatibilité métier externe est notee :

$$
b_{ij} \in \{0,1\}
$$

Si aucun fichier de compatibilité n'est fourni, l'implementation pose :

$$
b_{ij}=1
\qquad
\forall i \in C,\ \forall j \in F
$$

Toutes les compatibilités sont alors autorisées par défaut. Si un fichier est
fourni, une valeur `0` interdit le couple correspondant.

Les autres paramètres métier structurants sont :

| Paramêtre | Signification |
| --- | --- |
| `T` | temps maximal admissible pour une affectation commune-pivot |
| `Q` | capacité maximale d'une session, en nombre de CC |
| `L` | remplissage minimal d'une session ouverte |
| `f` | budget maximal de sessions PC |
| `k` | budget maximal de sessions TPC |
| `B` | budget total déclaré, avec `B = f + k` |
| `w_t` | poids du temps de trajet dans l'objectif |
| `w_e` | poids des coûts d'éligibilité dans l'objectif |
| `w_m` | poids de la mixité résiduelle dans l'objectif |
| `e_j^{PC}` | coût d'éligibilité si le pivot `j` heberge une session PC |
| `e_j^{TPC}` | coût d'éligibilité si le pivot `j` heberge une session TPC |

Les coûts d'éligibilité sont des pénalités de l'objectif. Meme lorsqu'une valeur
est très élevée, elle n'interdit pas à elle seule une session ; elle rend
simplement cette option très defavorable, sauf si le couple est interdit par une
contrainte ou par l'absence de variable.

## 6. Variables de décision

La variable d'affectation indique si une commune est rattachée à une session
candidate :

$$
x_{ijm} \in \{0,1\}
$$

$$
x_{ijm}=1
\quad \Longleftrightarrow \quad
\text{la commune } i \text{ est affectée à la session } (j,m).
$$

Cette variable n'existe pas pour tous les triplets possibles. Elle est creee
uniquement pour les couples commune-pivot admissibles et compatibles.

La variable d'ouverture indique si une session candidate est effectivement
ouverte :

$$
y_{jm} \in \{0,1\}
$$

$$
y_{jm}=1
\quad \Longleftrightarrow \quad
\text{la session } (j,m) \text{ est ouverte.}
$$

La variable de type distingue les sessions PC et TPC :

$$
z_{jm} \in \{0,1\}
$$

$$
z_{jm}=1
\quad \Longleftrightarrow \quad
\text{la session } (j,m) \text{ est de type TPC.}
$$

Lorsque `z_jm = 0` et que la session est ouverte, elle est interprétée comme une
session PC.

La variable de mixité résiduelle est entière :

$$
d_{jm} \in \mathbb{N}
$$

Elle mesure le nombre de CC TPC affectés à une session PC. Pour une session TPC,
elle peut rester nulle, car la présence de communes TPC y est naturelle.

La condition de creation des variables d'affectation est :

$$
a_{ij}=1
\quad \text{et} \quad
b_{ij}=1.
$$

Cette restriction est decisive pour la taille du modèle : un couple interdit ne
devient pas une variable pénalisée, il n'existe tout simplement pas dans le
modèle CP-SAT.

## 7. Fonction objectif

Le modèle minimise une somme pondérée de trois composantes : le coût de trajet,
le coût d'éligibilité des pivots et la mixité résiduelle.

La composante de trajet est :

$$
O_{\text{trajet}}
=
\sum_{i \in C}
\sum_{(j,m)\in S}
q_i \tau_{ij} x_{ijm}
$$

Chaque temps de trajet est multiplie par le nombre de CC de la commune. Une
commune de plus de 5000 habitants pèse donc deux fois plus qu'une commune à un
seul CC.

La composante d'éligibilité est :

$$
O_{\text{éligibilité}}
=
\sum_{(j,m)\in S}
\left[
e_j^{PC} y_{jm}
+
\left(e_j^{TPC}-e_j^{PC}\right) z_{jm}
\right]
$$

Si la session est ouverte et PC, alors `y_jm = 1` et `z_jm = 0`, donc le coût
vaut `e_j^{PC}`. Si elle est TPC, alors `z_jm = 1`, et l'expression vaut
`e_j^{TPC}`. Cette écriture evite tout produit entre variables.

La composante de mixité est :

$$
O_{\text{mixité}}
=
\sum_{(j,m)\in S}
d_{jm}
$$

Elle penalise la présence de CC TPC dans des sessions PC, sans l'interdire.

L'objectif global est :

$$
\min
\quad
w_t O_{\text{trajet}}
+
w_e O_{\text{éligibilité}}
+
w_m O_{\text{mixité}}
$$

La formulation est linéaire : chaque terme est une constante multipliee par une
variable booleenne ou entière, ou une somme de tels termes. Le modèle reste donc
compatible avec CP-SAT et ne contient pas de produit entre variables.

## 8. Contraintes

Les contraintes ci-dessous sont les contraintes dures du modèle. Une solution
qui en viole une n'est pas faisable, quel que soit son coût objectif.

### 8.1 Affectation unique

Pour chaque commune, exactement une variable d'affectation doit être active :

$$
\sum_{(j,m)\in S_i} x_{ijm} = 1
\qquad
\forall i \in C
$$

`S_i` designe les sessions candidates pour lesquelles une variable `x_ijm`
existe pour la commune `i`. Cette contrainte garantit qu'aucune commune n'est
oubliee et qu'aucune commune n'est affectée deux fois.

### 8.2 Pas d'affectation sans ouverture

Une commune ne peut être affectée qu'à une session ouverte :

$$
x_{ijm} \leq y_{jm}
\qquad
\forall x_{ijm}
$$

Si `y_jm = 0`, alors toutes les affectations vers cette session doivent valoir
`0`.

### 8.3 Capacité et remplissage minimal

La chargé d'une session ouverte doit rester entre `L` et `Q` :

$$
L y_{jm}
\leq
\sum_{i\in C} q_i x_{ijm}
\leq
Q y_{jm}
\qquad
\forall (j,m)\in S
$$

Si la session est fermée, `y_jm = 0` et la charge imposée est nulle. Si elle est
ouverte, elle doit respecter le remplissage minimal et la capacité maximale.

### 8.4 Cohérence entre type et ouverture

Une session fermée ne peut pas être déclarée TPC :

$$
z_{jm} \leq y_{jm}
\qquad
\forall (j,m)\in S
$$

Cette contrainte donne un sens à `z_jm` uniquement lorsque la session existe.

### 8.5 Budget PC

Le nombre de sessions PC ouvertes ne doit pas dépasser `f` :

$$
\sum_{(j,m)\in S} (y_{jm}-z_{jm}) \leq f
$$

Pour une session ouverte PC, `y_jm - z_jm = 1`. Pour une session TPC, cette
quantite vaut `0`. La contrainte compte donc les sessions PC.

### 8.6 Budget TPC

Le nombre de sessions TPC ouvertes ne doit pas dépasser `k` :

$$
\sum_{(j,m)\in S} z_{jm} \leq k
$$

Le budget total `B` est valide en configuration par l'invariant `B = f + k`.
Dans le modèle, les deux contraintes précédentes pilotent directement les
budgets par type.

### 8.7 Ordre d'ouverture des slots

Pour les pivots PC, les slots doivent être ouverts dans l'ordre :

$$
y_{j,m+1} \leq y_{jm}
\qquad
\forall j \in P,\ \forall m \in \{1,\dots,M_j-1\}
$$

Cette contrainte reduit les symetries. Elle evite par exemple d'ouvrir le slot
2 d'un pivot PC alors que le slot 1 du même pivot est ferme. Elle ne s'applique
pas aux pivots TPC, qui n'ont qu'un seul slot.

### 8.8 Interdiction des PC dans une formation TPC

Une commune PC ne peut pas être affectée à une session de type TPC :

$$
x_{ijm} \leq 1-z_{jm}
\qquad
\forall i \in P,\ \forall (j,m)\in S_i
$$

Si `z_jm = 1`, la session est TPC et toutes les affectations de communes PC vers
cette session sont forcées à `0`. En revanche, une commune TPC peut être
affectée à une session PC ; cette situation est autorisée mais pénalisée par la
mixité.

Point de vigilance : cette contrainte porte sur la catégorie des communes
affectées, pas sur la catégorie du pivot. Dans le modèle actuel, une session TPC
peut donc avoir une commune pivot PC si aucune autre contrainte ne l'interdit.
Comme le pivot n'est pas automatiquement force à appartenir à sa propre session,
cette situation n'implique pas qu'une commune PC soit affectée à une session TPC.

### 8.9 Definition de la mixité résiduelle

On note le nombre de CC TPC affectés à une session :

$$
n_{jm}^{T}
=
\sum_{i\in T} q_i x_{ijm}
$$

La variable `d_jm` doit couvrir la part TPC présente dans une session PC :

$$
d_{jm} \geq n_{jm}^{T} - Qz_{jm}
$$

$$
d_{jm} \geq 0
$$

Si la session est TPC, `z_jm = 1` et `n_{jm}^{T} - Qz_{jm}` est inferieur ou
égal à zéro grâce à la capacité maximale. `d_jm` peut donc rester nul. Si la
session est PC, `z_jm = 0` et `d_jm` mesure le nombre de CC TPC places dans une
session PC.

## 9. Diagnostic pré-résolution

Le diagnostic pré-résolution signale des problèmes structuréls avant l'appel au
solveur. Il ne prouve pas la faisabilité, mais il permet d'identifier rapidement
des causes probables d'échec.

Les contrôles actuels portent notamment sur les communes sans pivot admissible,
les communes PC sans pivot compatible permettant une session PC, le volume total
de CC, le nombre de slots candidats et le nombre de trajets admissibles.

Une borne minimale du nombre de formations est calculée à partir de la capacité
maximale :

$$
B_{\min}
=
\left\lceil
\frac{\sum_{i\in C} q_i}{Q}
\right\rceil
$$

Cette borne indique le nombre minimal de sessions nécessaires si l'on ne regarde
que le volume total de CC et la capacité `Q`. Elle ne tient pas compte des
trajets, des compatibilités, des catégories ou des budgets par type ; elle reste
donc une alerte simple, pas une preuve complété.

Le diagnostic vérifie aussi la cohérence de `B`, `f` et `k`, ainsi que la
disponibilité des coordonnées pour la carte. Il ne calculé pas explicitement des
zones TPC isolées ; ces cas sont observes indirectement via les communes
orphelines, les trajets admissibles et les résultats du solveur.

## 10. Résolution CP-SAT

Le modèle est resolu avec OR-Tools CP-SAT. Ce solveur cherche une affectation
entière qui respecte toutes les contraintes dures, puis minimise l'objectif
pondéré.

La configuration transmet au solveur les paramètres opérationnels suivants :
temps limite, nombre de workers, graine aléatoire et activation eventuelle des
logs. Le nombre de workers peut accelerer la recherche, mais il ne change pas le
modèle mathématique.

Les principaux statuts sont :

| Statut | Interprétation |
| --- | --- |
| `OPTIMAL` | une solution optimale est trouvée et prouvée |
| `FEASIBLE` | une solution faisable est trouvée, mais l'optimalité n'est pas démontrée |
| `INFEASIBLE` | le solveur prouve qu'aucune solution ne respecte les contraintes |
| `UNKNOWN` | le solveur n'a pas fourni de conclusion exploitable dans les limites données |

Une solution `FEASIBLE` respecte les contraintes. Elle ne doit pas être décrite
comme optimale : le solveur n'a pas démontré qu'aucune meilleure solution
n'existe.

## 11. Extraction et validation

Le solveur retourne des valeurs de variables. Ces valeurs ne sont pas encore un
livrable métier directement exploitable. Le module `solution_extractor.py`
reconstruit d'abord des objets lisibles : sessions ouvertes, communes affectées
et decomposition de l'objectif.

L'extraction n'est lancee que pour les statuts `OPTIMAL` et `FEASIBLE`. Pour
chaque session ouverte, elle calculé le pivot, le type de session, les chargés,
les temps de trajet, les populations et la mixité résiduelle. Pour chaque
commune, elle reconstruit la session retenue, le pivot, le temps de trajet, la
catégorie, la population et le nombre de CC.

Le module `validation.py` recontrôle ensuite la solution extraite en mémoire,
avant tout export. La validation vérifie notamment l'affectation unique,
l'existence des sessions référencées, les capacités, les budgets, l'interdiction
des PC dans les sessions TPC, les temps de trajet, les compatibilités, la
cohérence de `d_jm` et l'objectif recalculé.

La condition opérationnelle est :

$$
\text{solution exploitable}
\Longleftrightarrow
\text{solution extraite}
+
\text{validation OK}
$$

Les exports sont produits seulement après cette validation. Relire des exports
peut servir à l'analyse ou à la régénération de la carte, mais les exports ne
sont pas la base de la validation initiale.

## 12. Assouplissement hiérarchique

Le workflow `solve-relaxed` applique une hiérarchie de tentatives. Il commence
toujours par la configuration initiale. Si aucune solution validée n'est obtenue,
il cree des copies indépendantes de la configuration et modifie uniquement des
paramètres explicitement autorisés par le protocole.

Les niveaux implémentés sont :

1. configuration initiale ;
2. ajustement du poids `w_m` ;
3. reduction des coûts d'éligibilité TPC ;
4. augmentation du seuil de trajet `T` ;
5. reduction du remplissage minimal `L` ;
6. augmentation de la capacité `Q` ;
7. augmentation coherente de `f`, `k` et `B` ;
8. remplacement final des coûts très élevés par une pénalité finie, si cette
   option est autorisée.

À chaque tentative, toute la chaîne est relancée : paramètres dérivés, modèle
CP-SAT, solveur, extraction et validation. Le workflow s'arrête à la première
solution validée et journalise les tentatives exécutées.

La contrainte interdisant les communes PC dans une session TPC n'est jamais
relâchée automatiquement. Si cette contrainte bloque une zone, il s'agit d'une
décision métier à examiner explicitement, pas d'un assouplissement standard du
code.

## 13. Exports et visualisation

Une solution validée peut être restituee sous plusieurs formes :

| Fichier | Rôle |
| --- | --- |
| `sessions.csv` | détail des sessions ouvertes, chargés, types, alertes et indicateurs |
| `communes_affectees.csv` | affectation de chaque commune à une session et à un pivot |
| `rapport_solution.md` | synthèse lisible de la solution et des contrôles |
| `statistiques_solution.json` | statistiques structurées pour analyse ou reutilisation |
| `config_utilisee.yaml` | copie de la configuration ayant produit la solution |
| `solution_map.html` | carte HTML autonome de contrôle visuel |

La source de vérité opérationnelle est :

$$
\text{source de vérité}
=
\text{exports valides}
+
\text{configuration utilisée}
$$

La carte est une visualisation de contrôle. Elle aide à inspecter les pivots,
les affectations, les temps de trajet proches du seuil et les alertes, mais elle
ne remplace pas les CSV, le rapport, le JSON de statistiques et la configuration
utilisée.

Les coordonnées n'interviennent pas dans le modèle CP-SAT. Elles servent
uniquement à positionner les points sur la carte. Les communes sans coordonnées
restent dans la solution et dans les exports.

## 14. Performance et taille du modèle

La taille du modèle depend surtout du nombre de variables d'affectation `x`.
Ces variables sont creees pour les couples commune-pivot admissibles,
compatibles, puis dupliquees sur les slots du pivot.

$$
\left|X\right|
=
\sum_{i\in C}
\sum_{j\in F}
M_j
I_{a_{ij}=1}
I_{b_{ij}=1}
$$

Cette formule explique pourquoi le seuil de trajet `T` à un effet important.
Dans cette notation, `I_condition` vaut `1` si la condition est vraie et `0`
sinon.
Augmenter `T` augmente souvent le nombre de couples admissibles et donc le
nombre de variables. Le problème peut devenir plus facile à rendre faisable,
mais plus difficile à optimiser. Reduire `T` à l'effet inverse : le modèle est
plus petit, mais le risque d'infaisabilité augmente.

Le nombre de pivots candidats et les valeurs `M_j` jouent aussi un rôle direct.
Comme `F = C`, chaque commune est candidate pivot. Les communes PC générént
jusqu'à trois slots, alors que les communes TPC n'en générént qu'un.

Il faut enfin distinguer trouver une solution faisable et prouver son
optimalité. CP-SAT peut trouver rapidement une solution respectant les
contraintes, puis avoir besoin de beaucoup plus de temps pour prouver qu'elle
est optimale. Le parallelisme peut ameliorer la recherche, mais il ne change ni
les contraintes ni la fonction objectif.

## 15. Correspondance code / mathématiques

| Element | Signification | Fichier |
| --- | --- | --- |
| `C`, `P`, `T`, `F`, `S` | ensembles | `parameters.py` |
| `q_i` | nombre de CC | `parameters.py` |
| `tau_ij` | temps de trajet | `parameters.py` |
| `a_ij` | admissibilite trajet | `parameters.py` |
| `b_ij` | compatibilité métier | `parameters.py` |
| `e_j_PC`, `e_j_TPC` | coûts d'éligibilité | `parameters.py` |
| `x`, `y`, `z`, `d` | variables CP-SAT | `model_builder.py` |
| objectif | fonction à minimiser | `model_builder.py` |
| contraintes | modèle CP-SAT | `model_builder.py` |
| extraction | solution métier | `solution_extractor.py` |
| validation | contrôle post-solution | `validation.py` |
| assouplissement | scenarios hiérarchiques | `relaxation.py` |
| exports | restitution | `export.py` |
| carte | visualisation | `map_export.py` |

## 16. Limites et points de vigilance

Le modèle actuel est volontairement centre sur l'affectation des communes aux
sessions. Les limites suivantes doivent être connues avant toute utilisation
métier :

- un statut `FEASIBLE` ne garantit pas l'optimalité ;
- les poids `w_t`, `w_e` et `w_m` doivent être calibres avec prudence ;
- les coûts très élevés sont des pénalités, pas des interdictions ;
- les trajets absents sont interdits car aucune variable n'est creee ;
- les trajets diagonaux `i -> i` ne sont pas générés automatiquement ;
- les coordonnées servent uniquement à la carte ;
- une commune pivot ouverte n'est pas forcement affectée à sa propre session ;
- une session TPC peut avoir un pivot PC si le pivot n'est pas contraint à être
  membre de sa session ;
- les superviseurs, disponibilités et contraintes calendaires ne sont pas
  optimises si aucune variable ou contrainte dédiée ne les encode ;
- une validation métier finale reste nécessaire après la validation
  algorithmique.

Ces limites ne sont pas des erreurs d'exécution. Elles delimitent le perimêtre
exact du modèle implémenté et les points à discuter avant toute extension.

## 17. Conclusion

L'outil produit une solution d'affectation en combinant une préparation de
données, une formulation CP-SAT, une résolution paramétrée, une extraction
métier et une validation indépendante. Cette chaîne permet d'obtenir des
exports contrôles et une carte de visualisation sans confondre optimisation,
validation et expertise métier.

La validation algorithmique garantit que la solution extraite respecte les
contraintes codees. Elle ne remplace pas l'analyse humaine des alertes, des
choix de pénalités, des pivots retenus et des conditions opérationnelles non
modélisées. Les exports et la carte servent donc à qualifier la solution et à
faciliter la revue métier.

Ce document constitue la référence pour comprendre comment les objets du code,
les notations mathématiques et les fichiers produits s'articulent dans
l'implementation actuelle.
