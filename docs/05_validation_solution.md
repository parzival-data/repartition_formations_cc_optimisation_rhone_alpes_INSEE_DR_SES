# Validation de solution

La validation automatique devra verifier au minimum :

- chaque commune est affectee exactement une fois ;
- aucune affectation n'existe vers une formation fermee ;
- tous les trajets affectes respectent `T` et les compatibilites ;
- les capacites respectent `L <= charge <= Q` pour chaque formation ouverte ;
- les budgets `f`, `k` et `B = f + k` sont respectes ;
- aucune commune PC n'est affectee a une formation declaree TPC ;
- les valeurs d'objectif exportees correspondent aux affectations.

Ces controles seront executes apres resolution et avant export.
