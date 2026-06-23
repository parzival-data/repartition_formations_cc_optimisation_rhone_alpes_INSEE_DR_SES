"""Chargement et validation de la configuration YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Erreur de configuration explicite et actionnable."""


@dataclass(frozen=True)
class FormationBudgets:
    """Budgets de formations du modele."""

    B: int
    f: int
    k: int


@dataclass(frozen=True)
class CcCountRule:
    """Regle de calcul du nombre de CC a former."""

    threshold_population: int
    below_or_equal: int
    above: int


@dataclass(frozen=True)
class PivotSlots:
    """Nombre maximal de formations par pivot selon sa categorie."""

    M_PC: int
    M_TPC: int


@dataclass(frozen=True)
class ObjectiveWeights:
    """Poids de la fonction objectif."""

    w_t: int
    w_e: int
    w_m: int


@dataclass(frozen=True)
class EligibilityBand:
    """Bande de population pour les couts d'eligibilite."""

    min: int
    max: int | None
    e_PC: int
    e_TPC: int


@dataclass(frozen=True)
class EligibilityCosts:
    """Couts d'eligibilite des pivots."""

    infinity: int
    population_bands: tuple[EligibilityBand, ...]


@dataclass(frozen=True)
class ModelParameters:
    """Parametres metier suivant les notations de la modelisation."""

    T: int
    Q: int
    L: int
    formation_budgets: FormationBudgets
    cc_count: CcCountRule
    pivot_slots: PivotSlots
    objective_weights: ObjectiveWeights
    eligibility_costs: EligibilityCosts


@dataclass(frozen=True)
class InputPaths:
    """Chemins des donnees d'entree."""

    communes_path: Path
    travel_times_path: Path
    compatibility_path: Path | None
    missing_travel_time_policy: str


@dataclass(frozen=True)
class OptimizerConfig:
    """Configuration complete de l'optimiseur."""

    metadata: dict[str, Any]
    inputs: InputPaths
    columns: dict[str, str]
    parameters: ModelParameters
    solver: dict[str, Any]
    relaxation: dict[str, Any]
    exports: dict[str, Any]
    raw: dict[str, Any]


def load_config(path: str | Path) -> OptimizerConfig:
    """Charge et valide un fichier YAML de configuration."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    if not isinstance(raw, dict):
        raise ConfigError(f"La configuration {config_path} doit contenir un objet YAML racine.")

    config = _parse_config(raw)
    validate_config(config)
    return config


def config_from_dict(raw: dict[str, Any]) -> OptimizerConfig:
    """Construit et valide une configuration depuis un dictionnaire."""

    config = _parse_config(raw)
    validate_config(config)
    return config


def validate_config(config: OptimizerConfig) -> None:
    """Valide les invariants metier imposes par le modele."""

    params = config.parameters
    budgets = params.formation_budgets

    if params.T <= 0:
        raise ConfigError("Le parametre T doit etre strictement positif.")
    if params.Q <= 0:
        raise ConfigError("Le parametre Q doit etre strictement positif.")
    if not 0 < params.L <= params.Q:
        raise ConfigError("Les parametres doivent verifier 0 < L <= Q.")
    if budgets.B != budgets.f + budgets.k:
        raise ConfigError(
            f"Le modele impose B = f + k, mais B={budgets.B}, f={budgets.f}, k={budgets.k}."
        )
    if budgets.f < 0 or budgets.k < 0 or budgets.B < 0:
        raise ConfigError("Les budgets de formations B, f et k doivent etre positifs ou nuls.")
    if params.cc_count.threshold_population != 5000:
        raise ConfigError("Le seuil de population pour 2 CC doit etre 5000.")
    if params.cc_count.below_or_equal != 1 or params.cc_count.above != 2:
        raise ConfigError("La regle q_i doit etre 1 si population <= 5000 et 2 sinon.")
    if params.pivot_slots.M_PC != 3:
        raise ConfigError("Le modele impose M_PC = 3.")
    if params.pivot_slots.M_TPC != 1:
        raise ConfigError("Le modele impose M_TPC = 1.")
    if params.objective_weights.w_t <= 0:
        raise ConfigError("Le poids w_t doit etre strictement positif.")
    if params.objective_weights.w_e <= 0:
        raise ConfigError("Le poids w_e doit etre strictement positif.")
    if params.objective_weights.w_m <= 0:
        raise ConfigError("Le poids w_m doit etre strictement positif.")
    if params.eligibility_costs.infinity <= 0:
        raise ConfigError("Le cout infinity doit etre strictement positif.")
    if not params.eligibility_costs.population_bands:
        raise ConfigError("Au moins une bande de cout d'eligibilite est requise.")


def _parse_config(raw: dict[str, Any]) -> OptimizerConfig:
    _require_sections(raw, ["metadata", "inputs", "columns", "parameters"])
    parameters = _parse_parameters(_require_mapping(raw, "parameters"))
    inputs_raw = _require_mapping(raw, "inputs")

    inputs = InputPaths(
        communes_path=Path(_require_value(inputs_raw, "communes_path")),
        travel_times_path=Path(_require_value(inputs_raw, "travel_times_path")),
        compatibility_path=_optional_path(inputs_raw.get("compatibility_path")),
        missing_travel_time_policy=str(_require_value(inputs_raw, "missing_travel_time_policy")),
    )

    return OptimizerConfig(
        metadata=dict(_require_mapping(raw, "metadata")),
        inputs=inputs,
        columns=dict(_require_mapping(raw, "columns")),
        parameters=parameters,
        solver=dict(raw.get("solver", {})),
        relaxation=dict(raw.get("relaxation", {})),
        exports=dict(raw.get("exports", {})),
        raw=raw,
    )


def _parse_parameters(raw: dict[str, Any]) -> ModelParameters:
    budgets_raw = _require_mapping(raw, "formation_budgets")
    cc_count_raw = _require_mapping(raw, "cc_count")
    slots_raw = _require_mapping(raw, "pivot_slots")
    weights_raw = _require_mapping(raw, "objective_weights")
    costs_raw = _require_mapping(raw, "eligibility_costs")

    bands = tuple(_parse_eligibility_band(item) for item in _require_list(costs_raw, "population_bands"))

    return ModelParameters(
        T=_require_int(raw, "T"),
        Q=_require_int(raw, "Q"),
        L=_require_int(raw, "L"),
        formation_budgets=FormationBudgets(
            B=_require_int(budgets_raw, "B"),
            f=_require_int(budgets_raw, "f"),
            k=_require_int(budgets_raw, "k"),
        ),
        cc_count=CcCountRule(
            threshold_population=_require_int(cc_count_raw, "threshold_population"),
            below_or_equal=_require_int(cc_count_raw, "below_or_equal"),
            above=_require_int(cc_count_raw, "above"),
        ),
        pivot_slots=PivotSlots(
            M_PC=_require_int(slots_raw, "M_PC"),
            M_TPC=_require_int(slots_raw, "M_TPC"),
        ),
        objective_weights=ObjectiveWeights(
            w_t=_require_int(weights_raw, "w_t"),
            w_e=_require_int(weights_raw, "w_e"),
            w_m=_require_int(weights_raw, "w_m"),
        ),
        eligibility_costs=EligibilityCosts(
            infinity=_require_int(costs_raw, "infinity"),
            population_bands=bands,
        ),
    )


def _parse_eligibility_band(raw: Any) -> EligibilityBand:
    if not isinstance(raw, dict):
        raise ConfigError("Chaque bande de cout d'eligibilite doit etre un objet YAML.")
    max_value = raw.get("max")
    if max_value is not None and not isinstance(max_value, int):
        raise ConfigError("Le champ max d'une bande d'eligibilite doit etre un entier ou null.")
    return EligibilityBand(
        min=_require_int(raw, "min"),
        max=max_value,
        e_PC=_require_int(raw, "e_PC"),
        e_TPC=_require_int(raw, "e_TPC"),
    )


def _require_sections(raw: dict[str, Any], names: list[str]) -> None:
    for name in names:
        if name not in raw:
            raise ConfigError(f"Section obligatoire manquante: {name}.")


def _require_mapping(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = _require_value(raw, name)
    if not isinstance(value, dict):
        raise ConfigError(f"La section {name} doit etre un objet YAML.")
    return value


def _require_list(raw: dict[str, Any], name: str) -> list[Any]:
    value = _require_value(raw, name)
    if not isinstance(value, list):
        raise ConfigError(f"Le champ {name} doit etre une liste.")
    return value


def _require_int(raw: dict[str, Any], name: str) -> int:
    value = _require_value(raw, name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"Le champ {name} doit etre un entier.")
    return value


def _require_value(raw: dict[str, Any], name: str) -> Any:
    if name not in raw:
        raise ConfigError(f"Champ obligatoire manquant: {name}.")
    return raw[name]


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value))
