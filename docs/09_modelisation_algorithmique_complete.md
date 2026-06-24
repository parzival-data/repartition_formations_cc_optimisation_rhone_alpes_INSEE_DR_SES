# Modelisation algorithmique complete

Ce document decrit l'algorithme implemente dans le projet pour construire, resoudre, valider, exporter et visualiser une solution de repartition des formations CC EAR 2027.

Il decrit l'etat actuel du code. Les contraintes du modele sont des contraintes dures, les termes de l'objectif sont des penalites optimisees, les diagnostics sont des alertes avant resolution, et la carte est une visualisation des exports.

## Notes de coherence avec l'implementation

Deux points doivent etre lus explicitement avant d'utiliser ce document comme reference operationnelle :

- la preparation des donnees interdit un trajet absent. Elle ne cree pas automatiquement les trajets diagonaux \(i \rightarrow i\). Si ces trajets doivent etre admissibles avec un cout nul, ils doivent exister dans les donnees propres de temps de trajet ;
- l'export CSV `communes_affectees.csv` calcule `is_pivot` comme \(code\_commune = code\_pivot\), tandis que la carte identifie les pivots comme les communes qui hebergent au moins une session ouverte. Ces deux lectures peuvent differer lorsqu'une commune pivot n'est pas affectee a sa propre session.

## 1. Objectif du probleme

Le probleme consiste a organiser les sessions de formation des coordonnateurs communaux PC/TPC pour l'EAR 2027.

L'algorithme doit :

- affecter chaque commune a une seule session de formation ;
- choisir les communes pivots qui hebergent des sessions ;
- respecter les capacites minimales et maximales des sessions ;
- respecter les budgets de sessions PC et TPC ;
- interdire l'affectation d'une commune PC vers une session TPC ;
- tenir compte des temps de trajet et des compatibilites ;
- produire une solution validee, exportable et cartographiable.

La solution recherchee est donc une affectation faisable au sens des contraintes, puis la meilleure possible selon une fonction objectif ponderee.

## 2. Chaine algorithmique globale

Le pipeline complet est :

\[
\text{Donnees brutes}
\rightarrow
\text{Preparation}
\rightarrow
\text{Parametres}
\rightarrow
\text{Diagnostic}
\rightarrow
\text{Modele CP-SAT}
\rightarrow
\text{Resolution}
\rightarrow
\text{Extraction}
\rightarrow
\text{Validation}
\rightarrow
\text{Exports}
\rightarrow
\text{Carte}
\]

La preparation transforme les fichiers metier en tables propres. La construction des parametres convertit ces tables en ensembles, constantes et relations admissibles. Le diagnostic verifie les incoherences evidentes avant d'appeler le solveur. Le modele CP-SAT encode les contraintes et l'objectif. La resolution produit des valeurs de variables. L'extraction reconstruit les tables metier. La validation recalcule les contraintes independamment du solveur. Les exports et la carte restituent la solution.

```text
Algorithme principal
Entree : configuration YAML, fichiers communes, temps de trajet,
         compatibilites optionnelles
Sortie : solution validee, exports, carte

1. Charger la configuration
2. Preparer ou charger les donnees propres
3. Construire les ensembles et parametres
4. Realiser le diagnostic pre-resolution
5. Construire le modele CP-SAT
6. Resoudre
7. Si solution faisable :
      extraire la solution
      valider la solution
      exporter les resultats
   Sinon :
      eventuellement lancer l'assouplissement hierarchique
```

## 3. Donnees et ensembles

On note :

\[
C : \text{ensemble des communes}
\]

\[
P \subset C : \text{ensemble des communes PC}
\]

\[
\mathcal{T} \subset C : \text{ensemble des communes TPC}
\]

\[
C = P \cup \mathcal{T},
\qquad
P \cap \mathcal{T} = \varnothing
\]

Dans le code, l'ensemble TPC est nomme `T`. Dans ce document, il est note \(\mathcal{T}\) pour eviter la confusion avec le seuil de temps de trajet \(T\) defini dans la configuration.

Toutes les communes peuvent etre candidates pivot :

\[
F = C
\]

Les sessions candidates sont indexees par une commune pivot \(j\) et un numero de session \(m\) :

\[
S = \{(j,m) : j \in F,\ m \in \{1,\dots,M_j\}\}
\]

avec :

\[
M_j =
\begin{cases}
M_{\mathrm{PC}} = 3 & \text{si } j \in P,\\
M_{\mathrm{TPC}} = 1 & \text{si } j \in \mathcal{T}.
\end{cases}
\]

Ainsi, une commune PC peut porter jusqu'a trois sessions candidates, tandis qu'une commune TPC peut porter une seule session candidate.

## 4. Parametres metier

Le nombre de coordonnateurs communaux associe a une commune \(i\) est :

\[
q_i =
\begin{cases}
1 & \text{si } \operatorname{pop}(i) \leq 5000,\\
2 & \text{si } \operatorname{pop}(i) > 5000.
\end{cases}
\]

Le temps de trajet de \(i\) vers \(j\) est :

\[
\tau_{ij} \in \mathbb{R}_+
\]

Un couple commune-pivot est admissible si le trajet existe et ne depasse pas le seuil configure :

\[
a_{ij} =
\begin{cases}
1 & \text{si } \tau_{ij} \leq T,\\
0 & \text{sinon ou si } \tau_{ij} \text{ est absent}.
\end{cases}
\]

La compatibilite externe est :

\[
b_{ij} \in \{0,1\}
\]

Si aucun fichier de compatibilite n'est fourni, l'implementation pose par defaut :

\[
b_{ij}=1
\qquad
\forall (i,j) \in C \times F
\]

Les autres parametres metier sont :

\[
T : \text{temps maximal admissible}
\]

\[
Q : \text{capacite maximale d'une session en nombre de CC}
\]

\[
L : \text{remplissage minimal d'une session ouverte}
\]

\[
f : \text{budget maximal de sessions PC}
\]

\[
k : \text{budget maximal de sessions TPC}
\]

\[
B = f + k : \text{budget total declare de sessions}
\]

Les couts d'eligibilite d'un pivot \(j\) sont :

\[
e_j^{\mathrm{PC}} : \text{cout si } j \text{ heberge une session PC}
\]

\[
e_j^{\mathrm{TPC}} : \text{cout si } j \text{ heberge une session TPC}
\]

La fonction objectif combine trois poids :

\[
w_t : \text{poids du temps de trajet}
\]

\[
w_e : \text{poids des couts d'eligibilite}
\]

\[
w_m : \text{poids de la mixite residuelle}
\]

Ces poids ne changent pas la faisabilite. Ils changent uniquement le classement des solutions faisables.

## 5. Construction des variables

L'affectation est representee par :

\[
x_{ijm} \in \{0,1\}
\]

avec :

\[
x_{ijm}=1
\iff
\text{la commune } i \text{ est affectee a la formation } (j,m).
\]

La variable d'ouverture est :

\[
y_{jm} \in \{0,1\}
\]

avec :

\[
y_{jm}=1
\iff
\text{la formation } (j,m) \text{ est ouverte}.
\]

La variable de type TPC est :

\[
z_{jm} \in \{0,1\}
\]

avec :

\[
z_{jm}=1
\iff
\text{la formation } (j,m) \text{ est de type TPC}.
\]

La mixite residuelle est mesuree par :

\[
d_{jm} \in \mathbb{N}
\]

Les variables \(x_{ijm}\) ne sont creees que si :

\[
a_{ij}=1
\quad\text{et}\quad
b_{ij}=1.
\]

Cette restriction est importante pour la performance : les couples interdits ne sont pas seulement penalises, ils sont absents du modele.

## 6. Fonction objectif

L'objectif contient trois composantes lineaires.

Le cout de trajet est :

\[
\operatorname{Obj}_{\mathrm{trajet}}
=
\sum_{i \in C}
\sum_{(j,m)\in S}
q_i \tau_{ij} x_{ijm}
\]

Chaque temps est multiplie par le nombre de CC de la commune affectee.

Le cout d'eligibilite est :

\[
\operatorname{Obj}_{\mathrm{eligibilite}}
=
\sum_{(j,m)\in S}
\left[
e_j^{\mathrm{PC}} y_{jm}
+
\left(e_j^{\mathrm{TPC}}-e_j^{\mathrm{PC}}\right)z_{jm}
\right]
\]

Si une session est ouverte et PC, alors \(y_{jm}=1\) et \(z_{jm}=0\), donc le cout vaut \(e_j^{\mathrm{PC}}\). Si elle est TPC, alors \(y_{jm}=1\) et \(z_{jm}=1\), donc le cout vaut \(e_j^{\mathrm{TPC}}\).

La penalite de mixite residuelle est :

\[
\operatorname{Obj}_{\mathrm{mixite}}
=
\sum_{(j,m)\in S}
d_{jm}
\]

L'objectif global est :

\[
\min
\quad
w_t \operatorname{Obj}_{\mathrm{trajet}}
+
w_e \operatorname{Obj}_{\mathrm{eligibilite}}
+
w_m \operatorname{Obj}_{\mathrm{mixite}}
\]

La formulation est lineaire car chaque terme est une constante multipliee par une variable entiere ou booleenne, ou une somme de ces termes. Elle est donc compatible avec CP-SAT.

## 7. Contraintes du modele

On note \(S_i\) l'ensemble des slots pour lesquels une variable \(x_{ijm}\) existe pour la commune \(i\).

### Contrainte 1 - Affectation unique

\[
\sum_{(j,m)\in S_i} x_{ijm} = 1,
\qquad \forall i \in C
\]

Chaque commune doit etre affectee exactement une fois.

### Contrainte 2 - Pas d'affectation sans ouverture

\[
x_{ijm} \leq y_{jm},
\qquad \forall x_{ijm}
\]

Une commune ne peut etre affectee qu'a une formation ouverte.

### Contrainte 3 - Capacite et remplissage

\[
L y_{jm}
\leq
\sum_{i\in C} q_i x_{ijm}
\leq
Q y_{jm},
\qquad \forall (j,m)\in S
\]

Si la formation est fermee, la somme vaut 0. Si elle est ouverte, elle doit contenir entre \(L\) et \(Q\) CC.

### Contrainte 4 - Coherence type/ouverture

\[
z_{jm} \leq y_{jm},
\qquad \forall (j,m)\in S
\]

Une formation ne peut pas etre de type TPC si elle n'est pas ouverte.

### Contrainte 5 - Budget PC

\[
\sum_{(j,m)\in S} (y_{jm}-z_{jm}) \leq f
\]

Le nombre de sessions ouvertes non TPC, donc PC, ne doit pas depasser le budget \(f\).

### Contrainte 6 - Budget TPC

\[
\sum_{(j,m)\in S} z_{jm} \leq k
\]

Le nombre de sessions TPC ouvertes ne doit pas depasser le budget \(k\).

### Contrainte 7 - Ordre d'ouverture

\[
y_{j,m+1} \leq y_{jm},
\qquad
\forall j\in P,\quad m=1,\dots,M_j-1
\]

Pour une commune pivot PC, la deuxieme session ne peut etre ouverte que si la premiere l'est deja, et la troisieme seulement si la deuxieme l'est deja. Cette contrainte reduit les symetries.

### Contrainte 8 - Asymetrie PC vers TPC

\[
x_{ijm} \leq 1-z_{jm},
\qquad
\forall i\in P,\quad \forall (j,m)\in S_i
\]

Une commune PC ne peut pas etre affectee a une session TPC. En revanche, une commune TPC peut etre affectee a une session PC.

### Contrainte 9 - Mixite residuelle

On definit le nombre de CC TPC affectes a une session :

\[
n_{jm}^{\mathcal{T}}
=
\sum_{i\in \mathcal{T}} q_i x_{ijm}
\]

Puis :

\[
d_{jm} \geq n_{jm}^{\mathcal{T}} - Qz_{jm}
\]

\[
d_{jm} \geq 0
\]

Si la session est TPC, alors \(z_{jm}=1\), donc \(n_{jm}^{\mathcal{T}} - Qz_{jm} \leq 0\) car une session ne depasse pas \(Q\). La penalite peut donc rester nulle. Si la session est PC, alors \(z_{jm}=0\), et \(d_{jm}\) mesure le nombre de CC TPC affectes a cette session PC.

## 8. Diagnostic pre-resolution

Le diagnostic pre-resolution ne prouve pas la faisabilite, mais il detecte les problemes manifestes avant de construire ou resoudre le modele.

Il controle notamment :

- les communes orphelines, c'est-a-dire sans aucun pivot admissible ;
- les communes PC sans pivot compatible permettant une session PC ;
- le nombre total de CC ;
- une borne minimale du nombre de formations :

\[
B_{\min}
=
\left\lceil
\frac{\sum_{i\in C}q_i}{Q}
\right\rceil
\]

- la coherence du budget :

\[
B \geq B_{\min}
\]

- la coherence declarative :

\[
B=f+k
\]

- le nombre de trajets admissibles ;
- le nombre de slots candidats ;
- la disponibilite des coordonnees pour la carte.

Ces controles sont des alertes. Une absence d'alerte ne garantit pas que CP-SAT trouvera une solution dans le temps imparti.

## 9. Resolution CP-SAT

Le modele est transmis a OR-Tools CP-SAT. Le solveur cherche une solution entiere respectant toutes les contraintes, puis optimise l'objectif.

Les statuts principaux sont :

- `OPTIMAL` : une solution optimale est trouvee et prouvee ;
- `FEASIBLE` : une solution faisable est trouvee, mais l'optimalite n'est pas prouvee ;
- `INFEASIBLE` : le solveur prouve qu'aucune solution ne respecte les contraintes ;
- `UNKNOWN` : aucune conclusion exploitable n'est disponible dans les limites donnees.

On a donc :

\[
\text{FEASIBLE} \neq \text{OPTIMAL}
\]

Un statut `FEASIBLE` signifie que les contraintes sont respectees. Il ne signifie pas que le cout est minimal.

La configuration controle :

- le temps limite de resolution ;
- le nombre de workers CP-SAT ;
- l'activation des logs ;
- le `random_seed`.

Le parallelisme peut accelerer la recherche, mais il ne change pas le modele. Le `random_seed` aide a rendre les recherches plus reproductibles. L'objectif indique la valeur de la meilleure solution trouvee. La borne indique ce que le solveur sait prouver sur le meilleur optimum possible.

## 10. Extraction de solution

L'extraction n'est lancee que pour les statuts `OPTIMAL` ou `FEASIBLE`.

L'ensemble des sessions ouvertes est :

\[
\mathcal{S}^{\mathrm{open}}
=
\{(j,m)\in S : y_{jm}=1\}
\]

Pour chaque session ouverte, l'extracteur calcule :

- le code et le nom du pivot ;
- le numero de slot ;
- le type PC ou TPC ;
- le nombre de communes affectees ;
- le nombre total de CC ;
- le temps moyen ;
- le temps maximum ;
- la population minimale et maximale ;
- le nombre de CC PC et TPC ;
- la mixite residuelle ;
- le cout d'eligibilite ;
- les composantes d'objectif associees.

Pour chaque commune, l'extracteur calcule :

- la session affectee ;
- le pivot ;
- le temps de trajet ;
- la categorie PC/TPC ;
- le nombre de CC ;
- la population ;
- les coordonnees si disponibles.

Ces tables sont des objets metier reconstruits a partir des valeurs des variables CP-SAT.

## 11. Validation post-solution

La solution extraite est revalidee independamment du solveur. Cette validation ne repose pas seulement sur la confiance dans CP-SAT ; elle recalcule les contraintes et l'objectif a partir de la solution extraite.

En implementation, cette validation porte sur l'objet `ExtractedSolution` en
memoire, avant toute ecriture de fichier. Les exports sont produits seulement
apres validation. Ils peuvent ensuite etre relus pour analyse ou pour
regenerer la carte, mais ils ne sont pas la base de la validation initiale.

Les controles portent sur :

- l'affectation unique ;
- l'existence des sessions referencees ;
- les capacites minimale et maximale ;
- les budgets PC et TPC ;
- l'asymetrie PC vers TPC ;
- les temps de trajet admissibles ;
- les compatibilites ;
- la coherence de \(d_{jm}\) ;
- l'objectif recalcule.

La condition operationnelle est :

\[
\text{solution exploitable}
\iff
\text{solution extraite}
+
\text{validation OK}
\]

Une solution non validee ne doit pas etre consideree comme source de verite metier.

## 12. Assouplissement hierarchique

L'assouplissement hierarchique tente plusieurs configurations de plus en plus permissives ou moins penalisees. Chaque niveau reconstruit le modele, relance le solveur, extrait et valide la solution.

```text
Pour chaque niveau d'assouplissement :
    creer une copie de la configuration
    modifier uniquement les parametres autorises
    reconstruire le modele
    resoudre
    extraire
    valider
    journaliser
    si validation OK :
        arreter
```

Les niveaux implementes sont :

0. configuration initiale ;
1. modification de \(w_m\) ;
2. reduction des couts TPC ;
3. augmentation de \(T\) ;
4. reduction de \(L\) ;
5. augmentation de \(Q\) ;
6. augmentation coherente de \(f\), \(k\) et \(B\) ;
7. remplacement des couts tres eleves si cette option est explicitement autorisee.

La contrainte d'asymetrie PC vers TPC n'est pas relachee automatiquement :

\[
\text{contrainte PC} \rightarrow \text{TPC non relachee}
\]

L'assouplissement agit donc sur certains parametres de faisabilite ou sur certains couts, mais il ne change pas la structure fondamentale du modele.

## 13. Exports et carte

Les exports principaux sont :

- `sessions.csv` ;
- `communes_affectees.csv` ;
- `rapport_solution.md` ;
- `statistiques_solution.json` ;
- `config_utilisee.yaml` ;
- `solution_map.html`.

Les fichiers CSV et JSON de solution sont les supports de controle et de restitution. Le rapport Markdown donne une lecture synthetique. La carte HTML affiche les communes, pivots, sessions, filtres et diagnostics cartographiques.

La carte n'est pas la source de verite. Elle peut aider a comprendre la solution, mais les decisions metier doivent s'appuyer sur les exports valides.

\[
\text{source de verite}
=
\text{exports valides}
+
\text{configuration utilisee}
\]

Les coordonnees n'interviennent pas dans le modele CP-SAT actuel. Elles servent a la visualisation cartographique.

## 14. Complexite et performance

La taille du modele depend surtout du nombre de variables d'affectation \(x\).

\[
|\mathcal{X}|
=
\sum_{i\in C}
\sum_{j\in F}
M_j
\mathbf{1}_{a_{ij}=1}
\mathbf{1}_{b_{ij}=1}
\]

Cette formule montre que les variables augmentent avec :

- le nombre de communes ;
- le nombre de pivots candidats ;
- le nombre de slots par pivot ;
- le nombre de trajets admissibles ;
- le nombre de compatibilites autorisees.

Reduire le seuil \(T\) diminue le nombre de couples admissibles, donc reduit fortement la taille du modele, mais peut rendre le probleme infaisable. Augmenter \(T\) a l'effet inverse. Augmenter \(M_j\), \(Q\), ou les budgets peut faciliter la faisabilite, mais augmente souvent l'espace de recherche.

Le nombre de workers influence la recherche du solveur. Il ne modifie pas les contraintes. Trouver une solution faisable peut etre rapide alors que prouver son optimalite peut demander beaucoup plus de temps.

## 15. Correspondance code / mathematiques

| Element mathematique | Role | Fichier Python |
| --- | --- | --- |
| \(C,P,\mathcal{T},F,S\) | ensembles | `parameters.py` |
| \(q_i\) | nombre de CC | `parameters.py` |
| \(a_{ij}\) | admissibilite trajet | `parameters.py` |
| \(b_{ij}\) | compatibilite | `parameters.py` |
| \(\tau_{ij}\) | temps de trajet | `parameters.py` |
| \(x,y,z,d\) | variables | `model_builder.py` |
| objectif | optimisation | `model_builder.py` |
| contraintes | modele CP-SAT | `model_builder.py` |
| diagnostic | controles pre-resolution | `diagnostics.py` |
| solveur | appel OR-Tools CP-SAT | `solver.py` |
| extraction | tables metier | `solution_extractor.py` |
| validation | controle solution | `validation.py` |
| assouplissement | scenarios hierarchiques | `relaxation.py` |
| exports | restitution | `export.py` |
| carte | visualisation | `map_export.py` |

## 16. Limites du modele

Les limites actuelles sont :

- l'optimalite peut ne pas etre prouvee dans le temps limite ;
- les poids d'objectif doivent etre calibres avec prudence ;
- les couts tres eleves doivent etre interpretes comme des penalites, pas comme des interdictions sauf si le modele les interdit explicitement ;
- les trajets absents sont interdits ;
- les trajets diagonaux \(i \rightarrow i\) ne sont pas generes automatiquement par la preparation ;
- les coordonnees servent seulement a la carte ;
- le modele ne force pas actuellement une commune pivot ouverte a etre affectee a sa propre formation ;
- les superviseurs et disponibilites ne sont pas optimises par le modele si aucune variable ou contrainte dediee ne les encode ;
- une validation metier reste necessaire apres la validation algorithmique.

Le modele separe donc clairement :

- les contraintes dures, qui definissent la faisabilite ;
- les penalites, qui orientent l'optimisation ;
- les diagnostics, qui alertent avant resolution ;
- la visualisation, qui aide a inspecter la solution mais ne la definit pas.

La documentation de maintenance doit decrire l'etat reel du code. Toute
extension non implementee doit etre marquee comme limite ou perspective, jamais
comme fonctionnalite existante.
