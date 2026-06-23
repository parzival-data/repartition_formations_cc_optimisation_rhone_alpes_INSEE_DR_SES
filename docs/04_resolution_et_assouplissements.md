# Resolution et assouplissements

La resolution cible suit quatre etapes.

## Diagnostic pre-resolution

Avant tout appel solveur, le projet doit identifier :

- les communes sans pivot atteignable ;
- les communes PC sans pivot atteignable pouvant porter une formation PC ;
- les zones TPC isolees qui peuvent necessiter un pivot promu.

## Construction du modele

Les variables `x_ijm` sont creees uniquement si le trajet est admissible et compatible : `a_ij = 1` et `b_ij = 1`.

## Resolution

OR-Tools CP-SAT sera utilise avec un budget de temps configure dans le YAML.

## Assouplissements

La hierarchie d'assouplissement est configuree et journalisee. La contrainte d'asymetrie stricte PC -> TPC ne fait pas partie des assouplissements automatiques.
