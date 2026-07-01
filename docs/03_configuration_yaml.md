# Configuration YAML

Tous les paramètres métier sont centralisés dans `config/config_ear2027.yaml`.

Les notations principales suivent directement le modèle :

- `parameters.T` : temps de trajet maximal autorisé.
- `parameters.Q` : capacité maximale d'une formation.
- `parameters.L` : remplissage minimal obligatoire.
- `parameters.formation_budgets.f` : budget de formations PC.
- `parameters.formation_budgets.k` : budget de formations TPC.
- `parameters.formation_budgets.B` : budget total, obligatoirement égal à `f + k`.
- `parameters.pivot_slots.M_PC` : nombre de slots pour un pivot PC, fixé à `3`.
- `parameters.pivot_slots.M_TPC` : nombre de slots pour un pivot TPC, fixé à `1`.
- `parameters.objective_weights.w_t` : poids du trajet.
- `parameters.objective_weights.w_e` : poids de l'éligibilité.
- `parameters.objective_weights.w_m` : poids de la mixité.

Valeurs courantes dans `config/config_ear2027.yaml` :

| Paramètre | Valeur |
| --- | ---: |
| `parameters.T` | 60 |
| `parameters.Q` | 14 |
| `parameters.L` | 6 |
| `parameters.formation_budgets.B` | 55 |
| `parameters.formation_budgets.f` | 50 |
| `parameters.formation_budgets.k` | 5 |
| `parameters.pivot_slots.M_PC` | 3 |
| `parameters.pivot_slots.M_TPC` | 1 |
| `parameters.objective_weights.w_t` | 100 |
| `parameters.objective_weights.w_e` | 1000 |
| `parameters.objective_weights.w_m` | 20 |
| `solver.time_limit_seconds` | 1200 |
| `solver.num_workers` | 8 |
| `solver.random_seed` | 1 |
| `solver.log_search_progress` | `true` |

Le code doit refuser une configuration incohérente, notamment si `B != f + k` ou si `0 < L <= Q` n'est pas vérifie.
