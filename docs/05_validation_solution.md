# Validation de solution

La validation automatique est implementee dans `validation.py`. Une solution n'est pas exploitable tant qu'elle n'a pas ete extraite puis acceptee par `validate_solution()`.

La validation verifie au minimum :

- chaque commune est affectee exactement une fois ;
- aucune affectation n'existe vers une formation fermee ;
- tous les trajets affectes respectent `T` et les compatibilites ;
- les capacites respectent `L <= charge <= Q` pour chaque formation ouverte ;
- les budgets `f`, `k` et `B = f + k` sont respectes ;
- aucune commune PC n'est affectee a une formation declaree TPC ;
- les valeurs d'objectif extraites correspondent aux affectations.

Les composantes `Obj_trajet`, `Obj_eligibilite`, `Obj_mixite` et l'objectif total sont recalculees depuis la solution extraite, puis comparees a l'objectif retourne par le solveur.

Si une contrainte echoue, `validate_solution()` leve une erreur explicite. Si tout passe, elle retourne un rapport structure indiquant le nombre de sessions, le nombre d'affectations et le nombre total de CC.

Les exports finaux sont ecrits seulement apres cette validation. Les alertes metier presentes dans les exports sont non bloquantes : elles servent au controle humain, mais ne constituent pas des violations de contraintes.
