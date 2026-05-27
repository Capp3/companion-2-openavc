"""YAML suitability gate (M1 bootstrap; full catalogue in M3)."""

from c2o.suitability.blockers import Blocker, BlockerCode
from c2o.suitability.gate import GateResult, assess_module

__all__ = ["Blocker", "BlockerCode", "GateResult", "assess_module"]
