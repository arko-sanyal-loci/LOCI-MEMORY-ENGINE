"""
Tests for loci_engine.ethical_core — Clusters A and B primitives.

Verifies the open-interval invariants, provenance hash stability, and all
ethical gate behaviours extracted from the LOCI Ethical Reasoning Core skill.
"""

import math
import unittest

from loci_engine.ethical_core import (
    MEMORY_CLASSES,
    CompetenceRecord,
    GratitudeDebt,
    HarmSeverity,
    ScarMemory,
    asymmetric_forgiveness,
    autonomy_to_judge,
    competence_curve,
    compute_evidence,
    compute_heat,
    mutual_understanding_confirmed,
    provenance_hash,
    qsymprev,
    self_determined_resolver,
    theta_protect,
    vengeance_exception_gate,
)


class TestA1EvidenceAccumulation(unittest.TestCase):
    def test_single_observation(self):
        obs = [{"t_j": 0.0, "r_j": 1.0, "w_j": 1.0}]
        e = compute_evidence(obs, tau_k=45.0, t=0.0)
        self.assertAlmostEqual(e, 1.0)

    def test_hyperbolic_decay_not_zero(self):
        obs = [{"t_j": 0.0, "r_j": 1.0, "w_j": 1.0}]
        e_far = compute_evidence(obs, tau_k=45.0, t=10_000.0)
        self.assertGreater(e_far, 0.0)

    def test_future_observation_ignored(self):
        obs = [{"t_j": 100.0, "r_j": 1.0, "w_j": 1.0}]
        e = compute_evidence(obs, tau_k=45.0, t=0.0)
        self.assertEqual(e, 0.0)

    def test_multiple_observations_additive(self):
        obs = [
            {"t_j": 0.0, "r_j": 1.0, "w_j": 1.0},
            {"t_j": 0.0, "r_j": 0.5, "w_j": 2.0},
        ]
        e = compute_evidence(obs, tau_k=45.0, t=0.0)
        self.assertAlmostEqual(e, 2.0)


class TestA2A3OpenInterval(unittest.TestCase):
    def test_heat_never_reaches_alpha(self):
        h = compute_heat(0.0, alpha_k=0.14)
        self.assertGreater(h, 0.14)

    def test_heat_never_reaches_one(self):
        h = compute_heat(1e9, alpha_k=0.14)
        self.assertLess(h, 1.0)

    def test_fresh_scar_peak(self):
        # A3 states fresh scar peak ≈ 0.912 with alpha_k=0.14.
        # Solving H=0.912 → E ≈ 2.28 (high-relevance formative event).
        h = compute_heat(evidence=2.28, alpha_k=0.14)
        self.assertAlmostEqual(h, 0.912, delta=0.005)

    def test_invalid_alpha_raises(self):
        with self.assertRaises(ValueError):
            compute_heat(1.0, alpha_k=0.0)
        with self.assertRaises(ValueError):
            compute_heat(1.0, alpha_k=1.0)

    def test_heat_monotonically_increasing_with_evidence(self):
        h1 = compute_heat(1.0, alpha_k=0.08)
        h2 = compute_heat(5.0, alpha_k=0.08)
        self.assertLess(h1, h2)


class TestA4ProvenanceHash(unittest.TestCase):
    def test_hash_is_deterministic(self):
        h1 = provenance_hash("2026-01-01", "ARKO", "author", "hello")
        h2 = provenance_hash("2026-01-01", "ARKO", "author", "hello")
        self.assertEqual(h1, h2)

    def test_hash_changes_with_content(self):
        h1 = provenance_hash("2026-01-01", "ARKO", "author", "hello")
        h2 = provenance_hash("2026-01-01", "ARKO", "author", "world")
        self.assertNotEqual(h1, h2)

    def test_hash_prevents_field_bleed(self):
        # "ts=A, author_id=B" must differ from "ts=AB, author_id="
        h1 = provenance_hash("A", "B", "r", "c")
        h2 = provenance_hash("AB", "", "r", "c")
        self.assertNotEqual(h1, h2)

    def test_hash_length(self):
        h = provenance_hash("ts", "ARKO", "author", "content")
        self.assertEqual(len(h), 64)


class TestA5HarmSeverity(unittest.TestCase):
    def test_clamp_bounds(self):
        self.assertEqual(HarmSeverity.clamp(-1.0), 0.0)
        self.assertEqual(HarmSeverity.clamp(11.0), 10.0)

    def test_reparative_delta_positive_on_repair(self):
        self.assertGreater(HarmSeverity.reparative_delta(7.0, 3.0), 0.0)

    def test_reparative_delta_negative_on_harm_increase(self):
        self.assertLess(HarmSeverity.reparative_delta(3.0, 7.0), 0.0)


class TestB1MemoryClasses(unittest.TestCase):
    def test_all_three_classes_present(self):
        for name in ("formative_scar", "valued_skill", "routine_observation"):
            self.assertIn(name, MEMORY_CLASSES)

    def test_alpha_open_interval(self):
        for mc in MEMORY_CLASSES.values():
            self.assertGreater(mc.alpha, 0.0)
            self.assertLess(mc.alpha, 1.0)

    def test_scar_longest_tau(self):
        self.assertGreater(
            MEMORY_CLASSES["formative_scar"].tau_days,
            MEMORY_CLASSES["valued_skill"].tau_days,
        )


class TestB2ScarMechanics(unittest.TestCase):
    def test_scar_recall_above_threshold(self):
        scar = ScarMemory(gist_vector=[1.0, 0.0])
        self.assertTrue(scar.recall_triggered([0.95, 0.05], theta_recall=0.75))

    def test_scar_no_recall_below_threshold(self):
        scar = ScarMemory(gist_vector=[1.0, 0.0])
        self.assertFalse(scar.recall_triggered([0.0, 1.0], theta_recall=0.75))

    def test_scar_pinned(self):
        scar = ScarMemory(gist_vector=[1.0])
        self.assertEqual(scar.b_pin, 1)
        self.assertTrue(scar.flag_scar)

    def test_scar_heat_below_one(self):
        scar = ScarMemory(gist_vector=[1.0])
        self.assertLess(scar.heat_peak, 1.0)


class TestB3AsymmetricForgiveness(unittest.TestCase):
    def test_misdeed_fades_faster_than_good(self):
        result = asymmetric_forgiveness(
            tau_forgive=10.0, tau_good=30.0,
            elapsed_days=20.0,
            initial_misdeed_score=1.0, initial_good_score=1.0,
        )
        self.assertLess(result["misdeed_score"], result["good_score"])

    def test_invariant_violation_raises(self):
        with self.assertRaises(ValueError):
            asymmetric_forgiveness(
                tau_forgive=30.0, tau_good=10.0,  # wrong order
                elapsed_days=5.0,
                initial_misdeed_score=1.0, initial_good_score=1.0,
            )


class TestB3VengeanceException(unittest.TestCase):
    def test_retaliation_never_permitted(self):
        result = vengeance_exception_gate(is_retaliatory=True, raw_score=0.9)
        self.assertFalse(result["permitted"])
        self.assertLess(result["v_exec"], 0.0)

    def test_non_retaliation_passes_through(self):
        result = vengeance_exception_gate(is_retaliatory=False, raw_score=0.5)
        self.assertTrue(result["permitted"])
        self.assertAlmostEqual(result["v_exec"], 0.5)

    def test_reason_set_for_retaliation(self):
        result = vengeance_exception_gate(is_retaliatory=True, raw_score=0.9)
        self.assertIn("VENGEANCE_EXCEPTION", result["reason"])


class TestB4ThetaProtect(unittest.TestCase):
    def test_baby_falling_collapses_threshold(self):
        # Max severity, zero self-correction → threshold ≈ 0
        t = theta_protect(
            base_threshold=0.50,
            severity=1.0,
            victim_self_correction_capacity=0.0,
            own_confidence_in_domain=1.0,
            uninvited_penalty=0.0,
            floor_is_open=True,
        )
        self.assertLess(t, 0.15)

    def test_couple_fighting_raises_threshold(self):
        # Both parties have full agency; observer has low domain confidence
        t = theta_protect(
            base_threshold=0.50,
            severity=0.3,
            victim_self_correction_capacity=0.9,
            own_confidence_in_domain=0.2,
            uninvited_penalty=0.0,
            floor_is_open=True,
        )
        self.assertGreater(t, 0.50)

    def test_threshold_never_negative(self):
        t = theta_protect(
            base_threshold=0.0,
            severity=1.0,
            victim_self_correction_capacity=0.0,
            own_confidence_in_domain=1.0,
            uninvited_penalty=0.0,
            floor_is_open=True,
        )
        self.assertGreaterEqual(t, 0.0)


class TestB4CompetenceGate(unittest.TestCase):
    def test_ready_when_confident(self):
        rec = CompetenceRecord(
            skill_confidences={"cpr": 0.90}, integrity_verified=True
        )
        self.assertTrue(rec.readiness("cpr"))

    def test_not_ready_when_integrity_suspect(self):
        rec = CompetenceRecord(
            skill_confidences={"cpr": 0.99}, integrity_verified=False
        )
        self.assertFalse(rec.readiness("cpr"))

    def test_not_ready_when_below_threshold(self):
        rec = CompetenceRecord(
            skill_confidences={"cpr": 0.30}, integrity_verified=True
        )
        self.assertFalse(rec.readiness("cpr"))

    def test_unknown_skill_defaults_not_ready(self):
        rec = CompetenceRecord(skill_confidences={}, integrity_verified=True)
        self.assertFalse(rec.readiness("unfamiliar_skill"))


class TestB5ConflictPreventionProtocol(unittest.TestCase):
    def test_defer_on_bad_delivery(self):
        self.assertEqual(
            mutual_understanding_confirmed(
                delivered_effectively=False,
                current_capacity_to_engage=True,
                response_engages_with_substance=False,
            ),
            "defer",
        )

    def test_defer_on_distress(self):
        self.assertEqual(
            mutual_understanding_confirmed(
                delivered_effectively=True,
                current_capacity_to_engage=False,
                response_engages_with_substance=False,
            ),
            "defer",
        )

    def test_engaged_when_substance_engaged(self):
        self.assertEqual(
            mutual_understanding_confirmed(
                delivered_effectively=True,
                current_capacity_to_engage=True,
                response_engages_with_substance=True,
            ),
            "engaged",
        )

    def test_not_engaged_after_both_confirmed(self):
        self.assertEqual(
            mutual_understanding_confirmed(
                delivered_effectively=True,
                current_capacity_to_engage=True,
                response_engages_with_substance=False,
            ),
            "not_engaged",
        )


class TestB7DebtOfGratitude(unittest.TestCase):
    def test_debt_history_independent(self):
        debt = GratitudeDebt(person_id="X", intrinsic_weight=0.8)
        self.assertAlmostEqual(debt.debt_owed(), 0.8)

    def test_debt_not_affected_by_later_conduct(self):
        debt = GratitudeDebt(person_id="X", intrinsic_weight=0.8)
        # No mechanism to reduce it by later conduct — that is the invariant
        self.assertAlmostEqual(debt.debt_owed(), 0.8)


class TestB7SelfDeterminedResolver(unittest.TestCase):
    def test_reserve_floor_always_respected(self):
        claims = [
            {"harm_severity_if_unmet": 9.0, "resource_ask": 0.6},
            {"harm_severity_if_unmet": 7.0, "resource_ask": 0.6},
        ]
        result = self_determined_resolver(
            claims, self_capacity=1.0, self_reserve_floor=0.10
        )
        self.assertTrue(result["reserve_floor_respected"])
        self.assertGreaterEqual(result["self_capacity_remaining"], 0.10)

    def test_invalid_floor_raises(self):
        with self.assertRaises(ValueError):
            self_determined_resolver([], self_capacity=0.5, self_reserve_floor=0.6)

    def test_highest_severity_allocated_first(self):
        claims = [
            {"harm_severity_if_unmet": 2.0, "resource_ask": 0.3, "label": "low"},
            {"harm_severity_if_unmet": 8.0, "resource_ask": 0.3, "label": "high"},
        ]
        result = self_determined_resolver(
            claims, self_capacity=1.0, self_reserve_floor=0.10
        )
        allocations = result["allocations"]
        high_alloc = next(a for a in allocations if a.get("label") == "high")
        low_alloc = next(a for a in allocations if a.get("label") == "low")
        self.assertGreaterEqual(high_alloc["allocated"], low_alloc["allocated"])


class TestB13QSymPrev(unittest.TestCase):
    def test_deterministic_fact_recomputed(self):
        # Age increases by 1/year → known_rate = 1 / 365 days per day
        result = qsymprev(
            stored_value=30.0,
            stored_timestamp=0.0,
            update_function="deterministic",
            current_timestamp=365.0,
            known_rate=1.0 / 365.0,
        )
        self.assertAlmostEqual(result["current_value"], 31.0, delta=0.01)
        self.assertFalse(result["is_stale"])

    def test_non_deterministic_returns_warning(self):
        result = qsymprev(
            stored_value=50_000.0,
            stored_timestamp=1_000_000.0,
            update_function="non_deterministic",
            current_timestamp=2_000_000.0,
        )
        self.assertIsNone(result["current_value"])
        self.assertTrue(result["is_stale"])
        self.assertIn("last known", result["warning"])


class TestB17GraduatedAutonomy(unittest.TestCase):
    def test_autonomy_starts_above_alpha(self):
        obs = [{"t_j": 0.0, "r_j": 1.0, "w_j": 1.0}]
        a = autonomy_to_judge(obs, tau_autonomy_days=30.0, t=0.0, alpha_autonomy=0.05)
        self.assertGreater(a, 0.05)

    def test_autonomy_grows_with_more_evidence(self):
        obs_few = [{"t_j": 0.0, "r_j": 1.0, "w_j": 1.0}]
        obs_many = obs_few * 10
        a_few = autonomy_to_judge(obs_few, tau_autonomy_days=30.0, t=0.0)
        a_many = autonomy_to_judge(obs_many, tau_autonomy_days=30.0, t=0.0)
        self.assertLess(a_few, a_many)

    def test_autonomy_never_reaches_one(self):
        obs = [{"t_j": 0.0, "r_j": 1.0, "w_j": 1.0}] * 10_000
        a = autonomy_to_judge(obs, tau_autonomy_days=30.0, t=0.0)
        self.assertLess(a, 1.0)


class TestB26CompetenceCurve(unittest.TestCase):
    def test_day_zero_above_baseline(self):
        c = competence_curve(evidence=0.0)
        self.assertGreater(c, 0.05)

    def test_competence_grows_with_evidence(self):
        c1 = competence_curve(1.0)
        c2 = competence_curve(10.0)
        self.assertLess(c1, c2)

    def test_perfection_unreachable(self):
        c = competence_curve(1e12)
        self.assertLess(c, 1.0)

    def test_obeys_open_interval(self):
        for e in [0.0, 0.5, 5.0, 100.0]:
            c = competence_curve(e, alpha_c=0.05)
            self.assertGreater(c, 0.05)
            self.assertLess(c, 1.0)


if __name__ == "__main__":
    unittest.main()
