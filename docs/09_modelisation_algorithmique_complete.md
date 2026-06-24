# Modelisation algorithmique complete

## 1. Finalite du document

Ce document decrit l'algorithme complet utilise par l'outil d'optimisation des
sessions de formation des coordonnateurs communaux PC/TPC pour l'EAR 2027. Il
sert de reference pour comprendre le lien entre les donnees d'entree, la
construction du modele CP-SAT, la resolution, la validation et les exports.

Le texte decrit l'etat reel du code. Une regle, une contrainte ou un workflow
n'est presente comme existant que s'il est effectivement implemente. Les
extensions non codees sont signalees comme limites ou perspectives.

Trois niveaux doivent etre distingues pendant toute la lecture :

- les contraintes dures, qui definissent la faisabilite mathematique ;
- les penalites de l'objectif, qui orientent le choix entre solutions faisables ;
- les controles de diagnostic, de validation, d'export et de carte, qui aident a
  qualifier une solution mais ne remplacent pas l'expertise metier.

## 2. Vue d'ensemble du pipeline

Le pipeline applique par le projet suit une chaine volontairement separee en
etapes. Chaque etape produit des objets ou fichiers reutilisables par l'etape
suivante, ce qui rend le calcul plus controlable et facilite l'audit.

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

En pratique, la sequence operationnelle est la suivante :

```text
1. Charger la configuration YAML.
2. Preparer les donnees brutes si necessaire.
3. Charger les CSV propres.
4. Construire les ensembles, couts et relations admissibles.
5. Executer les diagnostics pre-resolution.
6. Construire le modele CP-SAT.
7. Resoudre le modele.
8. Si le solveur trouve une solution :
      extraire la solution metier ;
      valider la solution extraite ;
      produire les exports et, si demande, la carte.
   Sinon :
      analyser le statut solveur ou utiliser le workflow d'assouplissement.
```

Cette separation est importante : le solveur manipule des variables CP-SAT,
tandis que les exports manipulent une solution metier reconstruite et validee.
Les fichiers de restitution ne sont donc pas la source initiale de validation ;
ils sont produits apres la validation.

## 3. Donnees d'entree et preparation

Le solveur ne lit pas directement les fichiers bruts. Les donnees reelles sont
d'abord preparees par la commande `prepare-data`, qui transforme les fichiers
source en tables propres exploitees par les modules de chargement.

Le fichier des communes fournit les identifiants INSEE, les noms, la population,
la categorie `PC` ou `TPC`, et des champs optionnels comme le territoire EAR, le
nombre de logements, la latitude et la longitude. Ces donnees permettent de
calculer le nombre de coordonnateurs communaux a former et de connaitre la
categorie metier de chaque commune.

Le fichier des temps de trajet fournit des temps orientes entre une commune
origine et une commune candidate pivot. Un trajet absent est traite comme
interdit : il ne cree pas de variable d'affectation. La preparation ne complete
pas automatiquement les trajets diagonaux `i -> i`; si un trajet diagonal doit
etre admissible avec un temps nul, il doit etre present dans les donnees propres.

Le fichier de coordonnees est optionnel pour l'optimisation. Lorsqu'il est
present, ses latitudes et longitudes sont jointes aux communes et servent a la
carte HTML. Une commune sans coordonnees peut tout de meme etre affectee et
apparaitre dans les exports non cartographiques.

Le fichier de compatibilites est egalement optionnel. S'il est absent, le code
considere que toutes les compatibilites metier valent `1` par defaut. S'il est
present, il permet d'interdire certains couples commune-pivot avant meme la
creation des variables d'affectation.

Les principales sorties de preparation sont :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` si une source de compatibilites est
  disponible.

## 4. Ensembles du modele

On note d'abord l'ensemble des communes a affecter :

$$
C = \text{ensemble des communes a affecter}
$$

Cet ensemble contient toutes les communes chargees depuis le fichier propre des
communes.

Les communes PC et TPC forment deux sous-ensembles de `C` :

$$
P \subset C
$$

$$
T \subset C
$$

Le code suppose que chaque commune appartient a une seule categorie :

$$
C = P \cup T
\qquad
P \cap T = \varnothing
$$

Ici, `T` designe l'ensemble des communes TPC. Il ne faut pas le confondre avec
le parametre de temps maximal, egalement note `T` dans la configuration. Le
contexte indique toujours s'il s'agit d'un ensemble ou du seuil de trajet.

Toutes les communes sont candidates pivot :

$$
F = C
$$

Cela signifie que le modele autorise toute commune chargee a heberger une
session potentielle, sous reserve des autres contraintes et penalites. Cette
egalite ne signifie pas qu'une commune pivot ouverte est automatiquement membre
de sa propre session : le modele actuel ne force pas cette auto-affectation.

Les sessions candidates sont indexees par une commune pivot `j` et un rang de
slot `m` :

$$
S = \{(j,m) : j \in F, m \in \{1,\dots,M_j\}\}
$$

Le nombre de slots depend de la categorie de la commune pivot :

$$
M_j =
\begin{cases}
3 & \text{si } j \in P,\\
1 & \text{si } j \in T.
\end{cases}
$$

Une commune PC peut donc porter jusqu'a trois sessions candidates, tandis qu'une
commune TPC ne peut porter qu'une session candidate. Ces slots sont seulement
des possibilites : une session candidate devient reelle uniquement si sa
variable d'ouverture vaut `1`.

## 5. Parametres metier

On note `p_i` la population de la commune `i`. Le nombre de coordonnateurs
communaux a former depend de cette population :

$$
q_i =
\begin{cases}
1 & \text{si } p_i \leq 5000,\\
2 & \text{si } p_i > 5000.
\end{cases}
$$

Cette regle est codee dans `parameters.py` et validee par la configuration. Elle
permet de raisonner en charge de formation, pas seulement en nombre de communes.

Le temps de trajet de la commune `i` vers le pivot `j` est note :

$$
\tau_{ij} \geq 0
$$

Les temps sont orientes : un trajet `i -> j` et un trajet `j -> i` sont deux
entrees distinctes si les donnees les fournissent.

Le seuil maximal de trajet configure est note `T`. Un couple commune-pivot est
admissible seulement si le trajet existe et respecte ce seuil :

$$
a_{ij} =
\begin{cases}
1 & \text{si le trajet } i \to j \text{ existe et } \tau_{ij} \leq T,\\
0 & \text{sinon.}
\end{cases}
$$

Un trajet absent donne donc `a_ij = 0`. Il ne s'agit pas d'une forte penalite :
le couple est retire du modele d'affectation.

La compatibilite metier externe est notee :

$$
b_{ij} \in \{0,1\}
$$

Si aucun fichier de compatibilite n'est fourni, l'implementation pose :

$$
b_{ij}=1
\qquad
\forall i \in C,\ \forall j \in F
$$

Toutes les compatibilites sont alors autorisees par defaut. Si un fichier est
fourni, une valeur `0` interdit le couple correspondant.

Les autres parametres metier structurants sont :

| Parametre | Signification |
| --- | --- |
| `T` | temps maximal admissible pour une affectation commune-pivot |
| `Q` | capacite maximale d'une session, en nombre de CC |
| `L` | remplissage minimal d'une session ouverte |
| `f` | budget maximal de sessions PC |
| `k` | budget maximal de sessions TPC |
| `B` | budget total declare, avec `B = f + k` |
| `w_t` | poids du temps de trajet dans l'objectif |
| `w_e` | poids des couts d'eligibilite dans l'objectif |
| `w_m` | poids de la mixite residuelle dans l'objectif |
| `e_j^{PC}` | cout d'eligibilite si le pivot `j` heberge une session PC |
| `e_j^{TPC}` | cout d'eligibilite si le pivot `j` heberge une session TPC |

Les couts d'eligibilite sont des penalites de l'objectif. Meme lorsqu'une valeur
est tres elevee, elle n'interdit pas a elle seule une session ; elle rend
simplement cette option tres defavorable, sauf si le couple est interdit par une
contrainte ou par l'absence de variable.

## 6. Variables de decision

La variable d'affectation indique si une commune est rattachee a une session
candidate :

$$
x_{ijm} \in \{0,1\}
$$

$$
x_{ijm}=1
\quad \Longleftrightarrow \quad
\text{la commune } i \text{ est affectee a la session } (j,m).
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

Lorsque `z_jm = 0` et que la session est ouverte, elle est interpretee comme une
session PC.

La variable de mixite residuelle est entiere :

$$
d_{jm} \in \mathbb{N}
$$

Elle mesure le nombre de CC TPC affectes a une session PC. Pour une session TPC,
elle peut rester nulle, car la presence de communes TPC y est naturelle.

La condition de creation des variables d'affectation est :

$$
a_{ij}=1
\quad \text{et} \quad
b_{ij}=1.
$$

Cette restriction est decisive pour la taille du modele : un couple interdit ne
devient pas une variable penalisee, il n'existe tout simplement pas dans le
modele CP-SAT.

## 7. Fonction objectif

Le modele minimise une somme ponderee de trois composantes : le cout de trajet,
le cout d'eligibilite des pivots et la mixite residuelle.

La composante de trajet est :

$$
O_{trajet}
=
\sum_{i \in C}
\sum_{(j,m)\in S}
q_i \tau_{ij} x_{ijm}
$$

Chaque temps de trajet est multiplie par le nombre de CC de la commune. Une
commune de plus de 5000 habitants pese donc deux fois plus qu'une commune a un
seul CC.

La composante d'eligibilite est :

$$
O_{eligibilite}
=
\sum_{(j,m)\in S}
\left[
e_j^{PC} y_{jm}
+
\left(e_j^{TPC}-e_j^{PC}\right) z_{jm}
\right]
$$

Si la session est ouverte et PC, alors `y_jm = 1` et `z_jm = 0`, donc le cout
vaut `e_j^{PC}`. Si elle est TPC, alors `z_jm = 1`, et l'expression vaut
`e_j^{TPC}`. Cette ecriture evite tout produit entre variables.

La composante de mixite est :

$$
O_{mixite}
=
\sum_{(j,m)\in S}
d_{jm}
$$

Elle penalise la presence de CC TPC dans des sessions PC, sans l'interdire.

L'objectif global est :

$$
\min
\quad
w_t O_{trajet}
+
w_e O_{eligibilite}
+
w_m O_{mixite}
$$

La formulation est lineaire : chaque terme est une constante multipliee par une
variable booleenne ou entiere, ou une somme de tels termes. Le modele reste donc
compatible avec CP-SAT et ne contient pas de produit entre variables.

## 8. Contraintes

Les contraintes ci-dessous sont les contraintes dures du modele. Une solution
qui en viole une n'est pas faisable, quel que soit son cout objectif.

### 8.1 Affectation unique

Pour chaque commune, exactement une variable d'affectation doit etre active :

$$
\sum_{(j,m)\in S_i} x_{ijm} = 1
\qquad
\forall i \in C
$$

`S_i` designe les sessions candidates pour lesquelles une variable `x_ijm`
existe pour la commune `i`. Cette contrainte garantit qu'aucune commune n'est
oubliee et qu'aucune commune n'est affectee deux fois.

### 8.2 Pas d'affectation sans ouverture

Une commune ne peut etre affectee qu'a une session ouverte :

$$
x_{ijm} \leq y_{jm}
\qquad
\forall x_{ijm}
$$

Si `y_jm = 0`, alors toutes les affectations vers cette session doivent valoir
`0`.

### 8.3 Capacite et remplissage minimal

La charge d'une session ouverte doit rester entre `L` et `Q` :

$$
L y_{jm}
\leq
\sum_{i\in C} q_i x_{ijm}
\leq
Q y_{jm}
\qquad
\forall (j,m)\in S
$$

Si la session est fermee, `y_jm = 0` et la charge imposee est nulle. Si elle est
ouverte, elle doit respecter le remplissage minimal et la capacite maximale.

### 8.4 Coherence entre type et ouverture

Une session fermee ne peut pas etre declaree TPC :

$$
z_{jm} \leq y_{jm}
\qquad
\forall (j,m)\in S
$$

Cette contrainte donne un sens a `z_jm` uniquement lorsque la session existe.

### 8.5 Budget PC

Le nombre de sessions PC ouvertes ne doit pas depasser `f` :

$$
\sum_{(j,m)\in S} (y_{jm}-z_{jm}) \leq f
$$

Pour une session ouverte PC, `y_jm - z_jm = 1`. Pour une session TPC, cette
quantite vaut `0`. La contrainte compte donc les sessions PC.

### 8.6 Budget TPC

Le nombre de sessions TPC ouvertes ne doit pas depasser `k` :

$$
\sum_{(j,m)\in S} z_{jm} \leq k
$$

Le budget total `B` est valide en configuration par l'invariant `B = f + k`.
Dans le modele, les deux contraintes precedentes pilotent directement les
budgets par type.

### 8.7 Ordre d'ouverture des slots

Pour les pivots PC, les slots doivent etre ouverts dans l'ordre :

$$
y_{j,m+1} \leq y_{jm}
\qquad
\forall j \in P,\ \forall m \in \{1,\dots,M_j-1\}
$$

Cette contrainte reduit les symetries. Elle evite par exemple d'ouvrir le slot
2 d'un pivot PC alors que le slot 1 du meme pivot est ferme. Elle ne s'applique
pas aux pivots TPC, qui n'ont qu'un seul slot.

### 8.8 Interdiction des PC dans une formation TPC

Une commune PC ne peut pas etre affectee a une session de type TPC :

$$
x_{ijm} \leq 1-z_{jm}
\qquad
\forall i \in P,\ \forall (j,m)\in S_i
$$

Si `z_jm = 1`, la session est TPC et toutes les affectations de communes PC vers
cette session sont forcees a `0`. En revanche, une commune TPC peut etre
affectee a une session PC ; cette situation est autorisee mais penalisee par la
mixite.

Point de vigilance : cette contrainte porte sur la categorie des communes
affectees, pas sur la categorie du pivot. Dans le modele actuel, une session TPC
peut donc avoir une commune pivot PC si aucune autre contrainte ne l'interdit.
Comme le pivot n'est pas automatiquement force a appartenir a sa propre session,
cette situation n'implique pas qu'une commune PC soit affectee a une session TPC.

### 8.9 Definition de la mixite residuelle

On note le nombre de CC TPC affectes a une session :

$$
n_{jm}^{T}
=
\sum_{i\in T} q_i x_{ijm}
$$

La variable `d_jm` doit couvrir la part TPC presente dans une session PC :

$$
d_{jm} \geq n_{jm}^{T} - Qz_{jm}
$$

$$
d_{jm} \geq 0
$$

Si la session est TPC, `z_jm = 1` et `n_{jm}^{T} - Qz_{jm}` est inferieur ou
egal a zero grace a la capacite maximale. `d_jm` peut donc rester nul. Si la
session est PC, `z_jm = 0` et `d_jm` mesure le nombre de CC TPC places dans une
session PC.

## 9. Diagnostic pre-resolution

Le diagnostic pre-resolution signale des problemes structurels avant l'appel au
solveur. Il ne prouve pas la faisabilite, mais il permet d'identifier rapidement
des causes probables d'echec.

Les controles actuels portent notamment sur les communes sans pivot admissible,
les communes PC sans pivot compatible permettant une session PC, le volume total
de CC, le nombre de slots candidats et le nombre de trajets admissibles.

Une borne minimale du nombre de formations est calculee a partir de la capacite
maximale :

$$
B_{\min}
=
\left\lceil
\frac{\sum_{i\in C} q_i}{Q}
\right\rceil
$$

Cette borne indique le nombre minimal de sessions necessaires si l'on ne regarde
que le volume total de CC et la capacite `Q`. Elle ne tient pas compte des
trajets, des compatibilites, des categories ou des budgets par type ; elle reste
donc une alerte simple, pas une preuve complete.

Le diagnostic verifie aussi la coherence de `B`, `f` et `k`, ainsi que la
disponibilite des coordonnees pour la carte. Il ne calcule pas explicitement des
zones TPC isolees ; ces cas sont observes indirectement via les communes
orphelines, les trajets admissibles et les resultats du solveur.

## 10. Resolution CP-SAT

Le modele est resolu avec OR-Tools CP-SAT. Ce solveur cherche une affectation
entiere qui respecte toutes les contraintes dures, puis minimise l'objectif
pondere.

La configuration transmet au solveur les parametres operationnels suivants :
temps limite, nombre de workers, graine aleatoire et activation eventuelle des
logs. Le nombre de workers peut accelerer la recherche, mais il ne change pas le
modele mathematique.

Les principaux statuts sont :

| Statut | Interpretation |
| --- | --- |
| `OPTIMAL` | une solution optimale est trouvee et prouvee |
| `FEASIBLE` | une solution faisable est trouvee, mais l'optimalite n'est pas demontree |
| `INFEASIBLE` | le solveur prouve qu'aucune solution ne respecte les contraintes |
| `UNKNOWN` | le solveur n'a pas fourni de conclusion exploitable dans les limites donnees |

Une solution `FEASIBLE` respecte les contraintes. Elle ne doit pas etre decrite
comme optimale : le solveur n'a pas demontre qu'aucune meilleure solution
n'existe.

## 11. Extraction et validation

Le solveur retourne des valeurs de variables. Ces valeurs ne sont pas encore un
livrable metier directement exploitable. Le module `solution_extractor.py`
reconstruit d'abord des objets lisibles : sessions ouvertes, communes affectees
et decomposition de l'objectif.

L'extraction n'est lancee que pour les statuts `OPTIMAL` et `FEASIBLE`. Pour
chaque session ouverte, elle calcule le pivot, le type de session, les charges,
les temps de trajet, les populations et la mixite residuelle. Pour chaque
commune, elle reconstruit la session retenue, le pivot, le temps de trajet, la
categorie, la population et le nombre de CC.

Le module `validation.py` recontrole ensuite la solution extraite en memoire,
avant tout export. La validation verifie notamment l'affectation unique,
l'existence des sessions referencees, les capacites, les budgets, l'interdiction
des PC dans les sessions TPC, les temps de trajet, les compatibilites, la
coherence de `d_jm` et l'objectif recalcule.

La condition operationnelle est :

$$
\text{solution exploitable}
\Longleftrightarrow
\text{solution extraite}
+
\text{validation OK}
$$

Les exports sont produits seulement apres cette validation. Relire des exports
peut servir a l'analyse ou a la regeneration de la carte, mais les exports ne
sont pas la base de la validation initiale.

## 12. Assouplissement hierarchique

Le workflow `solve-relaxed` applique une hierarchie de tentatives. Il commence
toujours par la configuration initiale. Si aucune solution validee n'est obtenue,
il cree des copies independantes de la configuration et modifie uniquement des
parametres explicitement autorises par le protocole.

Les niveaux implementes sont :

1. configuration initiale ;
2. ajustement du poids `w_m` ;
3. reduction des couts d'eligibilite TPC ;
4. augmentation du seuil de trajet `T` ;
5. reduction du remplissage minimal `L` ;
6. augmentation de la capacite `Q` ;
7. augmentation coherente de `f`, `k` et `B` ;
8. remplacement final des couts tres eleves par une penalite finie, si cette
   option est autorisee.

A chaque tentative, toute la chaine est relancee : parametres derives, modele
CP-SAT, solveur, extraction et validation. Le workflow s'arrete a la premiere
solution validee et journalise les tentatives executees.

La contrainte interdisant les communes PC dans une session TPC n'est jamais
relachee automatiquement. Si cette contrainte bloque une zone, il s'agit d'une
decision metier a examiner explicitement, pas d'un assouplissement standard du
code.

## 13. Exports et visualisation

Une solution validee peut etre restituee sous plusieurs formes :

| Fichier | Role |
| --- | --- |
| `sessions.csv` | detail des sessions ouvertes, charges, types, alertes et indicateurs |
| `communes_affectees.csv` | affectation de chaque commune a une session et a un pivot |
| `rapport_solution.md` | synthese lisible de la solution et des controles |
| `statistiques_solution.json` | statistiques structurees pour analyse ou reutilisation |
| `config_utilisee.yaml` | copie de la configuration ayant produit la solution |
| `solution_map.html` | carte HTML autonome de controle visuel |

La source de verite operationnelle est :

$$
\text{source de verite}
=
\text{exports valides}
+
\text{configuration utilisee}
$$

La carte est une visualisation de controle. Elle aide a inspecter les pivots,
les affectations, les temps de trajet proches du seuil et les alertes, mais elle
ne remplace pas les CSV, le rapport, le JSON de statistiques et la configuration
utilisee.

Les coordonnees n'interviennent pas dans le modele CP-SAT. Elles servent
uniquement a positionner les points sur la carte. Les communes sans coordonnees
restent dans la solution et dans les exports.

## 14. Performance et taille du modele

La taille du modele depend surtout du nombre de variables d'affectation `x`.
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

Cette formule explique pourquoi le seuil de trajet `T` a un effet important.
Dans cette notation, `I_condition` vaut `1` si la condition est vraie et `0`
sinon.
Augmenter `T` augmente souvent le nombre de couples admissibles et donc le
nombre de variables. Le probleme peut devenir plus facile a rendre faisable,
mais plus difficile a optimiser. Reduire `T` a l'effet inverse : le modele est
plus petit, mais le risque d'infaisabilite augmente.

Le nombre de pivots candidats et les valeurs `M_j` jouent aussi un role direct.
Comme `F = C`, chaque commune est candidate pivot. Les communes PC generent
jusqu'a trois slots, alors que les communes TPC n'en generent qu'un.

Il faut enfin distinguer trouver une solution faisable et prouver son
optimalite. CP-SAT peut trouver rapidement une solution respectant les
contraintes, puis avoir besoin de beaucoup plus de temps pour prouver qu'elle
est optimale. Le parallelisme peut ameliorer la recherche, mais il ne change ni
les contraintes ni la fonction objectif.

## 15. Correspondance code / mathematiques

| Element | Signification | Fichier |
| --- | --- | --- |
| `C`, `P`, `T`, `F`, `S` | ensembles | `parameters.py` |
| `q_i` | nombre de CC | `parameters.py` |
| `tau_ij` | temps de trajet | `parameters.py` |
| `a_ij` | admissibilite trajet | `parameters.py` |
| `b_ij` | compatibilite metier | `parameters.py` |
| `e_j_PC`, `e_j_TPC` | couts d'eligibilite | `parameters.py` |
| `x`, `y`, `z`, `d` | variables CP-SAT | `model_builder.py` |
| objectif | fonction a minimiser | `model_builder.py` |
| contraintes | modele CP-SAT | `model_builder.py` |
| extraction | solution metier | `solution_extractor.py` |
| validation | controle post-solution | `validation.py` |
| assouplissement | scenarios hierarchiques | `relaxation.py` |
| exports | restitution | `export.py` |
| carte | visualisation | `map_export.py` |

## 16. Limites et points de vigilance

Le modele actuel est volontairement centre sur l'affectation des communes aux
sessions. Les limites suivantes doivent etre connues avant toute utilisation
metier :

- un statut `FEASIBLE` ne garantit pas l'optimalite ;
- les poids `w_t`, `w_e` et `w_m` doivent etre calibres avec prudence ;
- les couts tres eleves sont des penalites, pas des interdictions ;
- les trajets absents sont interdits car aucune variable n'est creee ;
- les trajets diagonaux `i -> i` ne sont pas generes automatiquement ;
- les coordonnees servent uniquement a la carte ;
- une commune pivot ouverte n'est pas forcement affectee a sa propre session ;
- une session TPC peut avoir un pivot PC si le pivot n'est pas contraint a etre
  membre de sa session ;
- les superviseurs, disponibilites et contraintes calendaires ne sont pas
  optimises si aucune variable ou contrainte dediee ne les encode ;
- une validation metier finale reste necessaire apres la validation
  algorithmique.

Ces limites ne sont pas des erreurs d'execution. Elles delimitent le perimetre
exact du modele implemente et les points a discuter avant toute extension.

## 17. Conclusion

L'outil produit une solution d'affectation en combinant une preparation de
donnees, une formulation CP-SAT, une resolution parametree, une extraction
metier et une validation independante. Cette chaine permet d'obtenir des
exports controles et une carte de visualisation sans confondre optimisation,
validation et expertise metier.

La validation algorithmique garantit que la solution extraite respecte les
contraintes codees. Elle ne remplace pas l'analyse humaine des alertes, des
choix de penalites, des pivots retenus et des conditions operationnelles non
modelees. Les exports et la carte servent donc a qualifier la solution et a
faciliter la revue metier.

Ce document constitue la reference pour comprendre comment les objets du code,
les notations mathematiques et les fichiers produits s'articulent dans
l'implementation actuelle.
