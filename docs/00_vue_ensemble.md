# Vue d'ensemble

Le projet vise a organiser les sessions de formation des coordonnateurs communaux (CC) des communes PC/TPC pour l'EAR 2027.

Le flux cible est :

1. charger les communes, les temps de trajet et les compatibilites ;
2. construire les parametres du modele ;
3. executer un diagnostic pre-resolution ;
4. generer un modele OR-Tools CP-SAT ;
5. resoudre le probleme ;
6. valider automatiquement la solution ;
7. exporter des resultats lisibles et reproductibles.

Cette premiere version du depot met en place la structure, la configuration et les validations de configuration. Elle ne contient pas encore le solveur CP-SAT complet.
