# Vue d'ensemble

Le projet vise à organiser les sessions de formation des coordonnateurs communaux (CC) des communes PC/TPC pour l'EAR 2027.

Le flux complet est :

1. préparer ou chargér les données propres ;
2. construire les paramètres du modèle ;
3. exécuter un diagnostic pré-résolution ;
4. générer un modèle OR-Tools CP-SAT ;
5. résoudre le problème, avec assouplissement hiérarchique si demandé ;
6. extraire la solution métier ;
7. valider automatiquement la solution ;
8. exporter des résultats lisibles et reproductibles ;
9. produire une carte HTML de visualisation.

Le dépôt contient le solveur CP-SAT, les contrôles de validation, les exports et la cartographie HTML. La formulation détaillée est décrite dans [Modélisation algorithmique complète](09_modelisation_algorithmique_complete.md). Le document LaTeX consolidé [rapport_technique_complet.tex](rapport_technique_complet.tex) regroupe aussi l'annexe de production des matrices de temps.

## Execution guidee

Pour un lancement accompagne, la commande suivante guide l'utilisateur dans les
etapes du pipeline sans lancer les etapes longues sans confirmation :

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml
```

Voir [Execution guidee](12_execution_guidee.md).
