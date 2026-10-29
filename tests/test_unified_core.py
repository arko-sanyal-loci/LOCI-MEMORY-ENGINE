import time
import unittest
from loci_engine.unified_core import (
    DeductiveIdentityResolver,
    NonOffsettingGoodwillLedger,
    DynamicTokenCoupledSnippetEngine,
    StickPrincipleValenceGate,
)

class TestUnifiedCoreSubstrate(unittest.TestCase):
    def setUp(self):
        self.past_ts = time.time() - (365 * 86400)
        self.resolver = DeductiveIdentityResolver()
        self.principal_id = self.resolver.resolve_principal_confidence(
            local_user="arko-sanyal",
            email_binding="arko.sanyal@gmail.com",
            known_registry_ids=["TD_COMMONS_DPUBS_12179", "GITHUB_ARKO"],
            account_creation_ts=self.past_ts,
            has_visual_or_sovereign_nid=True,
        )

    def test_deductive_identity_resolution(self):
        self.assertGreaterEqual(self.principal_id["C_id"], 0.85)
        self.assertIn("HIGH_CONFIDENCE_PRINCIPAL", self.principal_id["tier"])
        self.assertGreater(self.principal_id["effective_review_width"], 0.0)

    def test_administrative_task_execution(self):
        admin_eval = StickPrincipleValenceGate.score_vexec(
            knowledge_k="systemctl restart ssh.service",
            application_point="routine_administrative_task",
            intent=0.0,
            consent=0.0,
            c_id=self.principal_id["C_id"],
        )
        self.assertTrue(admin_eval["allow_execution"])
        self.assertGreater(admin_eval["v_exec"], 0.0)

    def test_non_offsetting_goodwill_invariant(self):
        ledger = NonOffsettingGoodwillLedger()
        ledger.record_goodwill(delta=1.5, current_day=0.0)
        v_good_t0 = ledger.compute_active_v_good(current_day=0.0)
        self.assertGreater(v_good_t0, 0.90)

        bad_action_eval = StickPrincipleValenceGate.score_vexec(
            knowledge_k="rm -rf /",
            application_point="unverified_destructive_command",
            intent=-0.95,
            consent=-0.95,
            c_id=self.principal_id["C_id"],
        )
        self.assertLess(bad_action_eval["v_exec"], 0.0)

        clearance = NonOffsettingGoodwillLedger.assert_non_offsetting_clearance(
            v_exec=bad_action_eval["v_exec"],
            v_good=v_good_t0,
            effective_review_width=self.principal_id["effective_review_width"],
        )
        self.assertFalse(clearance["execution_permitted"])

    def test_goodwill_45_day_decay(self):
        ledger = NonOffsettingGoodwillLedger()
        ledger.record_goodwill(delta=1.5, current_day=0.0)
        v_good_t0 = ledger.compute_active_v_good(current_day=0.0)
        v_good_t45 = ledger.compute_active_v_good(current_day=45.0)

        self.assertLess(v_good_t45, v_good_t0)
        self.assertAlmostEqual(v_good_t45, 0.6351, delta=0.02)

    def test_snippet_budget_boundary(self):
        lean_alloc = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(
            0.95, 0.40, tokens_already_consumed=120
        )
        self.assertEqual(lean_alloc["allocated_bytes"], 60)

        expanded_alloc = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(
            0.72, 0.70, tokens_already_consumed=120
        )
        self.assertGreater(expanded_alloc["allocated_bytes"], 60)
        self.assertTrue(expanded_alloc["ceiling_preserved"])
        self.assertLessEqual(expanded_alloc["estimated_token_cost"], 560)

if __name__ == "__main__":
    unittest.main()
