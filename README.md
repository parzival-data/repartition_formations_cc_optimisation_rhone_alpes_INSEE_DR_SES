# Repartition des formations CC - EAR 2027

Ce depot contient le socle Python d'un outil d'optimisation pour organiser les sessions de formation des coordonnateurs communaux (CC) des communes PC/TPC pour l'EAR 2027.

Le modele cible est celui de la specification fournie : un seul seuil de trajet `T`, une capacite `Q`, des budgets `f`, `k`, `B` avec `B = f + k`, des slots `M_PC = 3` et `M_TPC = 1`, et une separation PC -> TPC stricte traitee comme contrainte dure dans le modele futur.

## Installation

```bash
python -m pip install -e ".[dev]"
```

## Commandes

Valider la configuration principale :

```bash
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

Afficher un resume de configuration :

```bash
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Les commandes de diagnostic, construction du modele, resolution et export sont prevues dans l'architecture, mais le solveur CP-SAT complet n'est pas encore implemente a cette etape.

## Organisation

- `config/` : configuration YAML et schema documentaire.
- `data/` : donnees brutes, donnees transformees et echantillons.
- `docs/` : documentation Markdown de la modelisation et du projet.
- `src/cc_formation_optimizer/` : package Python.
- `tests/` : tests automatises et fixtures.
- `outputs/` : sorties generees par les futures executions.
