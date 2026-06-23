# Configuration YAML

Tous les parametres metier sont centralises dans `config/config_ear2027.yaml`.

Les notations principales suivent directement le modele :

- `parameters.T` : temps de trajet maximal autorise.
- `parameters.Q` : capacite maximale d'une formation.
- `parameters.L` : remplissage minimal obligatoire.
- `parameters.formation_budgets.f` : budget de formations PC.
- `parameters.formation_budgets.k` : budget de formations TPC.
- `parameters.formation_budgets.B` : budget total, obligatoirement egal a `f + k`.
- `parameters.pivot_slots.M_PC` : nombre de slots pour un pivot PC, fixe a `3`.
- `parameters.pivot_slots.M_TPC` : nombre de slots pour un pivot TPC, fixe a `1`.
- `parameters.objective_weights.w_t` : poids du trajet.
- `parameters.objective_weights.w_e` : poids de l'eligibilite.
- `parameters.objective_weights.w_m` : poids de la mixite.

Le code doit refuser une configuration incoherente, notamment si `B != f + k` ou si `0 < L <= Q` n'est pas verifie.
