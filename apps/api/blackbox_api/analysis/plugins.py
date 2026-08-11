"""Custom analysis-rule plug-ins.

Deployments can extend the engine with their own rules — no fork needed.
Set ``BLACKBOX_EXTRA_RULES`` to a comma-separated list of ``module:function``
specs; each function must have the same signature as the built-in rules
(``(IncidentFeatures, AnalysisThresholds) -> RuleResult``) and return one of
the canonical failure categories. Plug-ins compete with the built-in rules on
equal footing: highest score above the diagnosis threshold wins.

Example::

    # acme_rules.py, importable via PYTHONPATH
    def battery_sag(features, thresholds):
        return RuleResult(rule_id="acme_battery_sag", ...)

    BLACKBOX_EXTRA_RULES=acme_rules:battery_sag
"""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable
from functools import lru_cache
from typing import cast

from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.rules import ALL_RULES, RuleResult
from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.logging import log

logger = logging.getLogger("blackbox.analysis")

RuleFn = Callable[[IncidentFeatures, AnalysisThresholds], RuleResult]

ENV_VAR = "BLACKBOX_EXTRA_RULES"


class RulePluginError(RuntimeError):
    """A configured rule plug-in could not be loaded."""


def _load_spec(spec: str) -> RuleFn:
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise RulePluginError(
            f"invalid rule plug-in spec '{spec}' — expected 'module:function'"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise RulePluginError(
            f"cannot import rule plug-in module '{module_name}': {exc}"
        ) from exc
    rule = getattr(module, attr, None)
    if not callable(rule):
        raise RulePluginError(
            f"rule plug-in '{spec}' is not a callable function"
        )
    return cast(RuleFn, rule)


@lru_cache
def get_all_rules() -> tuple[RuleFn, ...]:
    """Built-in rules plus any plug-ins from BLACKBOX_EXTRA_RULES."""
    specs = [
        spec.strip()
        for spec in os.environ.get(ENV_VAR, "").split(",")
        if spec.strip()
    ]
    extras = tuple(_load_spec(spec) for spec in specs)
    if extras:
        log(
            logger, logging.INFO, "custom analysis rules loaded",
            count=len(extras), specs=specs,
        )
    return tuple(ALL_RULES) + extras


def reset_rules_cache() -> None:
    """Re-read the plug-in configuration (used by tests)."""
    get_all_rules.cache_clear()
