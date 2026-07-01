"""Construction des parametres derives du modele."""

from __future__ import annotations

from dataclasses import dataclass

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import Compatibility, Commune, FormationSlot, TravelTime


@dataclass(frozen=True)
class DerivedParameters:
    """Ensembles et parametres derives directement utilises par le modele.

    Attributes
    ----------
    C : tuple[str, ...]
        Ensemble des communes a affecter.
    P : tuple[str, ...]
        Sous-ensemble des communes de categorie PC.
    T : tuple[str, ...]
        Sous-ensemble des communes de categorie TPC.
    F : tuple[str, ...]
        Ensemble des communes candidates comme pivots.
    q_i : dict[str, int]
        Nombre de CC a former pour chaque commune.
    M_j : dict[str, int]
        Nombre de slots disponibles par pivot.
    S : tuple[FormationSlot, ...]
        Ensemble des slots potentiels ``(pivot, rang)``.
    tau_ij : dict[tuple[str, str], int]
        Temps de trajet connus entre commune et pivot.
    a_ij : dict[tuple[str, str], int]
        Indicateur de trajet admissible au regard du seuil ``T``.
    b_ij : dict[tuple[str, str], int]
        Indicateur de compatibilite metier entre commune et pivot.
    e_j_PC : dict[str, int]
        Cout d'eligibilite de chaque pivot pour une session PC.
    e_j_TPC : dict[str, int]
        Cout d'eligibilite de chaque pivot pour une session TPC.
    """

    C: tuple[str, ...]
    P: tuple[str, ...]
    T: tuple[str, ...]
    F: tuple[str, ...]
    q_i: dict[str, int]
    M_j: dict[str, int]
    S: tuple[FormationSlot, ...]
    tau_ij: dict[tuple[str, str], int]
    a_ij: dict[tuple[str, str], int]
    b_ij: dict[tuple[str, str], int]
    e_j_PC: dict[str, int]
    e_j_TPC: dict[str, int]


def cc_count_for_population(population: int, config: OptimizerConfig) -> int:
    """Retourne ``q_i`` selon la population d'une commune.

    Parameters
    ----------
    population : int
        Population de la commune.
    config : OptimizerConfig
        Configuration contenant la regle de calcul des CC.

    Returns
    -------
    int
        Nombre de CC associe a la commune.
    """

    rule = config.parameters.cc_count
    if population <= rule.threshold_population:
        return rule.below_or_equal
    return rule.above


def slots_for_commune(commune: Commune, config: OptimizerConfig) -> list[FormationSlot]:
    """Construit les slots potentiels d'une commune pivot.

    Parameters
    ----------
    commune : Commune
        Commune candidate comme pivot.
    config : OptimizerConfig
        Configuration contenant les nombres de slots PC et TPC.

    Returns
    -------
    list[FormationSlot]
        Slots disponibles pour ce pivot.

    Raises
    ------
    ValueError
        Si la categorie de la commune n'est ni ``PC`` ni ``TPC``.
    """

    slots = config.parameters.pivot_slots
    if commune.category == "PC":
        max_slots = slots.M_PC
    elif commune.category == "TPC":
        max_slots = slots.M_TPC
    else:
        raise ValueError(f"Categorie de commune inconnue: {commune.category}")
    return [FormationSlot(commune.commune_id, index) for index in range(1, max_slots + 1)]


def build_derived_parameters(
    communes: list[Commune],
    travel_times: list[TravelTime],
    compatibilities: list[Compatibility],
    config: OptimizerConfig,
) -> DerivedParameters:
    """Construit les ensembles et parametres derives du modele.

    Les trajets absents de `travel_times` sont interdits par defaut dans
    `a_ij`. Les compatibilites absentes valent `1` par defaut dans `b_ij`.

    Parameters
    ----------
    communes : list[Commune]
        Communes a affecter et pivots candidats.
    travel_times : list[TravelTime]
        Temps de trajet orientes connus.
    compatibilities : list[Compatibility]
        Compatibilites metier explicites.
    config : OptimizerConfig
        Configuration du modele.

    Returns
    -------
    DerivedParameters
        Parametres ``C, P, T, F, S, q_i, a_ij, b_ij`` et couts de pivots.

    Raises
    ------
    ValueError
        Si une commune est dupliquee, si une categorie est inconnue ou si un
        trajet/une compatibilite reference une commune inconnue.
    """

    commune_by_id = _index_communes(communes)
    C = tuple(commune.commune_id for commune in communes)
    P = tuple(commune.commune_id for commune in communes if commune.category == "PC")
    T_set = tuple(commune.commune_id for commune in communes if commune.category == "TPC")
    F = C

    q_i = {commune.commune_id: cc_count_for_population(commune.population, config) for commune in communes}
    M_j = {commune.commune_id: len(slots_for_commune(commune, config)) for commune in communes}
    S = tuple(slot for commune in communes for slot in slots_for_commune(commune, config))

    tau_ij = _build_tau(travel_times, commune_by_id)
    a_ij = _build_admissibility(C, F, tau_ij, config)
    b_ij = _build_compatibility(C, F, compatibilities, commune_by_id)
    e_j_PC, e_j_TPC = _build_eligibility_costs(communes, config)

    return DerivedParameters(
        C=C,
        P=P,
        T=T_set,
        F=F,
        q_i=q_i,
        M_j=M_j,
        S=S,
        tau_ij=tau_ij,
        a_ij=a_ij,
        b_ij=b_ij,
        e_j_PC=e_j_PC,
        e_j_TPC=e_j_TPC,
    )


def eligibility_costs_for_population(population: int, config: OptimizerConfig) -> tuple[int, int]:
    """Retourne ``(e_j_PC, e_j_TPC)`` selon les bandes configurees.

    Parameters
    ----------
    population : int
        Population du pivot.
    config : OptimizerConfig
        Configuration contenant les bandes de cout d'eligibilite.

    Returns
    -------
    tuple[int, int]
        Couts d'eligibilite du pivot pour une session PC puis TPC.

    Raises
    ------
    ValueError
        Si aucune bande de population ne couvre la valeur fournie.
    """

    for band in config.parameters.eligibility_costs.population_bands:
        upper_ok = band.max is None or population <= band.max
        if population >= band.min and upper_ok:
            return band.e_PC, band.e_TPC
    raise ValueError(f"Aucune bande de cout d'eligibilite ne couvre la population {population}.")


def _index_communes(communes: list[Commune]) -> dict[str, Commune]:
    commune_by_id: dict[str, Commune] = {}
    for commune in communes:
        if commune.commune_id in commune_by_id:
            raise ValueError(f"Commune dupliquee: {commune.commune_id}.")
        if commune.category not in {"PC", "TPC"}:
            raise ValueError(f"Categorie de commune inconnue pour {commune.commune_id}: {commune.category}.")
        commune_by_id[commune.commune_id] = commune
    return commune_by_id


def _build_tau(travel_times: list[TravelTime], commune_by_id: dict[str, Commune]) -> dict[tuple[str, str], int]:
    tau_ij: dict[tuple[str, str], int] = {}
    for travel_time in travel_times:
        if travel_time.origin_id not in commune_by_id:
            raise ValueError(f"Origine de trajet inconnue: {travel_time.origin_id}.")
        if travel_time.destination_id not in commune_by_id:
            raise ValueError(f"Destination de trajet inconnue: {travel_time.destination_id}.")
        key = (travel_time.origin_id, travel_time.destination_id)
        if key in tau_ij:
            raise ValueError(f"Trajet duplique: {travel_time.origin_id} -> {travel_time.destination_id}.")
        tau_ij[key] = travel_time.minutes
    return tau_ij


def _build_admissibility(
    C: tuple[str, ...],
    F: tuple[str, ...],
    tau_ij: dict[tuple[str, str], int],
    config: OptimizerConfig,
) -> dict[tuple[str, str], int]:
    return {
        (commune_id, pivot_id): int(
            (commune_id, pivot_id) in tau_ij and tau_ij[(commune_id, pivot_id)] <= config.parameters.T
        )
        for commune_id in C
        for pivot_id in F
    }


def _build_compatibility(
    C: tuple[str, ...],
    F: tuple[str, ...],
    compatibilities: list[Compatibility],
    commune_by_id: dict[str, Commune],
) -> dict[tuple[str, str], int]:
    b_ij = {(commune_id, pivot_id): 1 for commune_id in C for pivot_id in F}
    for compatibility in compatibilities:
        if compatibility.origin_id not in commune_by_id:
            raise ValueError(f"Origine de compatibilite inconnue: {compatibility.origin_id}.")
        if compatibility.destination_id not in commune_by_id:
            raise ValueError(f"Destination de compatibilite inconnue: {compatibility.destination_id}.")
        b_ij[(compatibility.origin_id, compatibility.destination_id)] = compatibility.allowed
    return b_ij


def _build_eligibility_costs(
    communes: list[Commune],
    config: OptimizerConfig,
) -> tuple[dict[str, int], dict[str, int]]:
    e_j_PC: dict[str, int] = {}
    e_j_TPC: dict[str, int] = {}
    for commune in communes:
        pc_cost, tpc_cost = eligibility_costs_for_population(commune.population, config)
        e_j_PC[commune.commune_id] = pc_cost
        e_j_TPC[commune.commune_id] = tpc_cost
    return e_j_PC, e_j_TPC
