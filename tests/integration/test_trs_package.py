"""The sealed TRS verification package is intact and still supports HOT = 0.70.

See docs/decisions/0001-hot-threshold-0.70.md for why these numbers matter.
"""
import hashlib
import sys
from pathlib import Path

import pytest

from loci_engine.heat import TIER_HOT_BOUNDARY, VRAM_ADMISSION_THRESHOLD, tier

PKG = Path(__file__).resolve().parents[2] / "research" / "trs_verification_package"


def _seal():
    for line in (PKG / "SHA256SUMS_SEALED").read_text().splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            yield digest, name.lstrip("*")


def test_every_present_file_matches_the_seal():
    checked = 0
    for digest, name in _seal():
        f = PKG / name
        if not f.exists():
            continue  # paper/ is intentionally not vendored
        assert hashlib.sha256(f.read_bytes()).hexdigest() == digest, name
        checked += 1
    assert checked >= 15


@pytest.fixture
def sweep(monkeypatch):
    monkeypatch.syspath_prepend(str(PKG / "benchmarks"))
    sys.modules.pop("threshold_sweep_experiment", None)
    import threshold_sweep_experiment as mod
    return mod.evaluate_threshold


def test_300_trial_sweep_supports_0_70_over_0_80(sweep):
    at_070 = sweep(theta_hot=0.70, alpha=0.050, trials=300)
    at_080 = sweep(theta_hot=0.80, alpha=0.050, trials=300)
    assert at_070["millers_law_pass"] and at_070["recall"] == 100.0
    assert at_070["mean_tokens"] <= 560
    assert not at_080["millers_law_pass"]
    assert at_080["recall"] < at_070["recall"]


def test_engine_uses_one_hot_boundary():
    assert TIER_HOT_BOUNDARY == VRAM_ADMISSION_THRESHOLD == 0.70
    assert tier(0.70) == "hot"
    assert tier(0.6999) != "hot"
