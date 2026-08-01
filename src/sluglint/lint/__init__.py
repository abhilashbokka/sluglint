"""Lint tiers.

Importing this package registers every tier-1 and tier-2 detector, so
`run_rules` can resolve any `detect:` key in the rulebook. Tier 3 needs no
registration, because its rules carry no code at all.
"""
from . import (  # noqa: F401
    tier1_format,
    tier1_metrics,
    tier2_consistency,
    tier2_production,
    tier3_llm,
)
from .registry import registered_keys, run_rules, unimplemented

__all__ = [
    "registered_keys", "run_rules", "unimplemented",
    "tier1_format", "tier1_metrics", "tier2_consistency", "tier2_production", "tier3_llm",
]
