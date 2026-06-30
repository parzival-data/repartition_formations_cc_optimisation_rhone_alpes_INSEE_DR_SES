# Validation de solution

La validation automatique est implémentée dans `validation.py`. Une solution n'est pas exploitable tant qu'elle n'a pas été extraite puis acceptée par `validate_solution()`.

La validation vérifie au minimum :

- chaque commune est affectée exactement une fois ;
- aucune affectation n'existe vers une formation fermée ;
- tous les trajets affectés respectent `T` et les compatibilités ;
- les capacités respectent `L <= charge <= Q` pour chaque formation ouverte ;
- les budgets `f`, `k` et `B = f + k` sont respectés ;
- aucune commune PC n'est affectée à une formation déclarée TPC ;
- les valeurs d'objectif extraites correspondent aux affectations.

Les composantes `Obj_trajet`, `Obj_eligibilite`, `Obj_mixite` et l'objectif total sont recalculées depuis la solution extraite, puis comparées à l'objectif retourné par le solveur.

Si une contrainte échoue, `validate_solution()` lève une erreur explicite. Si tout passe, elle retourne un rapport structuré indiquant le nombre de sessions, le nombre d'affectations et le nombre total de CC.

Les exports finaux sont écrits seulement après cette validation. Les alertes métier présentes dans les exports sont non bloquantes : elles servent àu contrôle humain, mais ne constituent pas des violations de contraintes.
