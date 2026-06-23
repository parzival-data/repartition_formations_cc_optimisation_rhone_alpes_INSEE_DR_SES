# Vue d'ensemble

Le projet vise a organiser les sessions de formation des coordonnateurs communaux (CC) des communes PC/TPC pour l'EAR 2027.

Le flux complet est :

1. preparer ou charger les donnees propres ;
2. construire les parametres du modele ;
3. executer un diagnostic pre-resolution ;
4. generer un modele OR-Tools CP-SAT ;
5. resoudre le probleme, avec assouplissement hierarchique si demande ;
6. extraire la solution metier ;
7. valider automatiquement la solution ;
8. exporter des resultats lisibles et reproductibles ;
9. produire une carte HTML de visualisation.

Le depot contient le solveur CP-SAT, les controles de validation, les exports et la cartographie HTML. La formulation detaillee est decrite dans [Modelisation algorithmique complete](09_modelisation_algorithmique_complete.md).
