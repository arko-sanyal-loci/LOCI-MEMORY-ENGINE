#!/usr/bin/env python3
"""Objective → plan → research → execute → dream → reflect → remember.

Research and semantic dream generation go through adapters. If the adapter
is missing or raises, the stage says so and no result is invented.

Dream scores are quarantined candidates. Only `record_observed_outcome`
writes crystallized lessons, and only for the task key that was measured.
The next run of a similar task reads those lessons and will not repeat a
known-failed option. A different task key does not inherit that ban.

Papers used as design references, not as copied corpus: Reflection-on-Action
(TD Commons 11090), thought crystallization (11091), CARD (10856), and the
consolidated dream score (11666). CARD depth stays in CardRouter. Permission
to act stays in application_policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from loci_engine.application_policy import assess_application
from loci_engine.card_router import CardRouter
from loci_engine.learning_store import LearningStore
from loci_engine.numeric_dream import stream_evaluate


class MissingResearchAdapter:
    """Explicit empty adapter. This is not a search result."""

    name = "none"

    def search(self, query: str) -> Dict[str, Any]:
        return {
            "status": "missing_capability",
            "service": "web_search",
            "query": query,
            "hits": [],
            "fabricated": False,
            "detail": "No research adapter is configured. No web search was performed.",
        }


@dataclass
class TaskRequest:
    task_key: str
    objective: str
    options: List[str]
    query: str
    action_name: str = "local_numeric_choice"
    consent: Optional[bool] = True
    intent: float = 0.8
    application_point: str = "routine_administrative_task"
    knowledge: str = ""
    dream_scores: Dict[str, float] = field(default_factory=dict)
    is_retaliatory: bool = False
    numeric_dream_count: int = 0
    numeric_score: Optional[Callable[[int], float]] = None


def choose_option(
    options: List[str],
    dream_scores: Dict[str, float],
    lessons: List[Dict[str, Any]],
) -> Dict[str, Any]:
    negative = sorted({row["option_key"] for row in lessons if row["polarity"] == "negative"})
    positive = [row for row in lessons if row["polarity"] == "positive"]
    allowed = [option for option in options if option not in negative]
    if not allowed:
        return {
            "choice": None,
            "reason": "no_allowed_option",
            "allowed": allowed,
            "avoided": negative,
        }
    positive.sort(key=lambda row: (-row["support_count"], -row["heat"], row["option_key"]))
    for row in positive:
        if row["option_key"] in allowed:
            return {
                "choice": row["option_key"],
                "reason": "crystallized_positive",
                "allowed": allowed,
                "avoided": negative,
                "lesson_id": row["id"],
                "lesson_heat": row["heat"],
                "lesson_confidence": row["confidence"],
            }
    ordered = sorted(allowed, key=lambda option: (-float(dream_scores.get(option, 0.0)), option))
    return {
        "choice": ordered[0],
        "reason": "dream_ranking_among_allowed",
        "allowed": allowed,
        "avoided": negative,
        "dream_score": float(dream_scores.get(ordered[0], 0.0)),
    }


class LearningCycle:
    def __init__(self, db_path: str, research: Any = None, now_day: float = 0.0):
        self.store = LearningStore(db_path)
        self.research = research if research is not None else MissingResearchAdapter()
        self.now_day = float(now_day)

    def run(self, task: TaskRequest) -> Dict[str, Any]:
        stages: List[Dict[str, Any]] = []
        objective_id = self.store.note("goal_context", task.objective)
        stages.append(
            {
                "stage": "objective",
                "status": "completed",
                "detail": task.objective,
                "memory_id": objective_id,
            }
        )

        lessons = self.store.active_lessons(task.task_key, self.now_day)
        card = CardRouter.execute_card_retrieval(
            task.query,
            [
                {
                    "id": row["id"],
                    "entity_id": f"{row['task_key']}:{row['option_key']}",
                    "heat": row["heat"],
                    "timestamp": row["support_count"],
                    "statement": row["statement"],
                }
                for row in lessons
            ],
        )
        lexical = self.store.lexical_hits(task.query, limit=card["depth_k"])
        plan = {
            "options": list(task.options),
            "applicability_lessons": [
                {
                    "id": row["id"],
                    "option_key": row["option_key"],
                    "polarity": row["polarity"],
                    "heat": row["heat"],
                    "confidence": row["confidence"],
                    "support_count": row["support_count"],
                    "scope": row["scope"],
                }
                for row in lessons
            ],
            "card": {
                "archetype": card["archetype"],
                "depth_k": card["depth_k"],
                "selected_ids": [item["id"] for item in card["selected_items"]],
                "note": "CARD sets recall depth and order. It is not an ethics score.",
            },
            "lexical": lexical,
        }
        plan_id = self.store.note(
            "decision",
            f"Plan for task {task.task_key}: options {', '.join(task.options) or '(none)'}",
        )
        stages.append(
            {
                "stage": "plan",
                "status": "completed",
                "detail": "recalled crystallized lessons for this task key only",
                "memory_id": plan_id,
                "output": plan,
            }
        )

        research_output = self._research(task.query)
        stages.append(
            {
                "stage": "research",
                "status": research_output["status"],
                "detail": research_output.get("detail", ""),
                "output": research_output,
            }
        )

        policy = assess_application(
            action_name=task.action_name,
            knowledge=task.knowledge or task.objective,
            application_point=task.application_point,
            intent=task.intent,
            consent=task.consent,
            is_retaliatory=task.is_retaliatory,
        )
        stages.append(
            {
                "stage": "policy",
                "status": "completed",
                "detail": "application policy is separate from CARD",
                "output": policy,
            }
        )

        product = None
        if not policy["allow_execution"]:
            if policy["knowledge_may_be_retained"]:
                self.store.remember_candidate(
                    task_key=task.task_key,
                    option_key="*",
                    statement=(
                        f"Action {task.action_name} was not executed. "
                        f"Constraints: {', '.join(policy['hard_constraints']) or 'gate review'}."
                    ),
                    score=0.0,
                    source="reflection",
                )
            stages.append(
                {
                    "stage": "execute",
                    "status": "denied",
                    "detail": "no product was produced",
                    "output": {"product": None},
                }
            )
        else:
            decision = choose_option(task.options, task.dream_scores, lessons)
            if decision["choice"] is None:
                stages.append(
                    {
                        "stage": "execute",
                        "status": "completed",
                        "detail": decision["reason"],
                        "output": decision,
                    }
                )
            else:
                product = {
                    "task_key": task.task_key,
                    "choice": decision["choice"],
                    "reason": decision["reason"],
                    "avoided": decision["avoided"],
                    "label": "offline_product",
                    "research_hits_used": 0,
                }
                stages.append(
                    {
                        "stage": "execute",
                        "status": "completed",
                        "detail": decision["reason"],
                        "output": {**decision, "product": product},
                    }
                )

        dream = self._dream(task)
        for winner in dream["discrete_candidates"]:
            self.store.remember_candidate(
                task_key=task.task_key,
                option_key=str(winner["id"]),
                statement=(
                    f"Simulated candidate {winner['id']} for task {task.task_key} "
                    f"scored {winner['score']}. Quarantined; not an observed outcome."
                ),
                score=float(winner["score"]),
                source="simulated_candidate",
            )
        stages.append({"stage": "dream", "status": "completed", "detail": dream["label"], "output": dream})

        reflection = self._reflect(task, product, dream)
        self.store.remember_candidate(
            task_key=task.task_key,
            option_key=str((product or {}).get("choice") or "*"),
            statement=reflection["statement"],
            score=0.0,
            source="reflection",
        )
        stages.append(
            {"stage": "reflect", "status": "completed", "detail": reflection["statement"], "output": reflection}
        )

        stages.append(
            {
                "stage": "remember",
                "status": "completed",
                "detail": (
                    "Dream output stayed quarantined. Crystallized memory changes "
                    "only in record_observed_outcome."
                ),
                "output": {"crystallized": []},
            }
        )
        return {
            "task_key": task.task_key,
            "stages": stages,
            "product": product,
            "policy": policy,
            "recall": plan,
        }

    def record_observed_outcome(
        self,
        *,
        task_key: str,
        measurements: Dict[str, float],
        outcome_id: str,
        scope_request: str = "task",
        expires_on_day: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Lower measurement is a better observed loss. Best and worst are recorded.

        This is the only promotion path. The caller supplies the outcome id;
        the cycle does not invent a reward from repetition or from dream scores.
        """
        if not measurements:
            raise ValueError("measurements are required")
        best = min(measurements, key=lambda key: (measurements[key], key))
        worst = max(measurements, key=lambda key: (measurements[key], key))
        written = []
        if best != worst:
            written.append(
                self.store.record_observed(
                    task_key=task_key,
                    option_key=best,
                    polarity="positive",
                    outcome_id=outcome_id,
                    statement=(
                        f"For task {task_key} option {best} had the better observed "
                        f"external loss {measurements[best]} on outcome {outcome_id}. "
                        "Task-scoped lesson, not a universal fact."
                    ),
                    now_day=self.now_day,
                    scope_request=scope_request,
                    expires_on_day=expires_on_day,
                )
            )
            written.append(
                self.store.record_observed(
                    task_key=task_key,
                    option_key=worst,
                    polarity="negative",
                    outcome_id=outcome_id,
                    statement=(
                        f"For task {task_key} avoid option {worst}. Observed external "
                        f"loss {measurements[worst]} on outcome {outcome_id} was worse. "
                        "This negative evidence applies only to this task, not as a universal fact."
                    ),
                    now_day=self.now_day,
                    scope_request=scope_request,
                    expires_on_day=expires_on_day,
                )
            )
        reflection = self.store.remember_candidate(
            task_key=task_key,
            option_key=worst,
            statement=(
                f"Reflection for task {task_key}: observed outcome {outcome_id} "
                f"favored {best} and not {worst}. Dream scores were not used as the outcome."
            ),
            score=0.0,
            source="reflection",
        )
        return {"lessons": written, "reflection_id": reflection["id"], "best": best, "worst": worst}

    def _research(self, query: str) -> Dict[str, Any]:
        try:
            result = self.research.search(query)
        except Exception as exc:
            return {
                "status": "missing_capability",
                "service": getattr(self.research, "name", "research_adapter"),
                "query": query,
                "hits": [],
                "fabricated": False,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        if not isinstance(result, dict):
            return {
                "status": "missing_capability",
                "hits": [],
                "fabricated": False,
                "detail": "Research adapter returned a non-object. Discarded.",
            }
        hits = result.get("hits") or []
        if result.get("fabricated") is True:
            hits = []
            result = {
                **result,
                "hits": [],
                "status": "rejected_fabricated_payload",
                "detail": "A fabricated hit list was discarded.",
            }
        else:
            result = {**result, "hits": list(hits)}
        result.setdefault("status", "completed")
        result.setdefault("fabricated", False)
        return result

    def _dream(self, task: TaskRequest) -> Dict[str, Any]:
        discrete = []
        for option in task.options:
            discrete.append(
                {
                    "id": option,
                    "score": float(task.dream_scores.get(option, 0.0)),
                    "epistemic_confidence": 0.0,
                    "stream_quarantine": "DSymPrev",
                    "provenance_kind": "simulated_candidate",
                    "epistemic_status": "candidate",
                }
            )
        discrete.sort(key=lambda row: (-row["score"], row["id"]))
        if task.numeric_dream_count and task.numeric_score is not None:
            def _eval(index: int) -> tuple:
                return (f"n{index}", float(task.numeric_score(index)))

            numeric = stream_evaluate(task.numeric_dream_count, _eval, keep=2)
        else:
            numeric = {
                "label": "NUMERICAL_DEMO",
                "evaluated": 0,
                "retained": 0,
                "winners": [],
                "not_verified_facts": True,
                "semantic_generation": {
                    "status": "missing_capability",
                    "service": "embedding_or_language_model",
                    "detail": "Numeric stream not requested for this call.",
                },
            }
        return {
            "label": "NUMERICAL_DEMO" if numeric["evaluated"] else "discrete_surrogate_only",
            "discrete_candidates": discrete,
            "numeric": numeric,
            "not_verified_facts": True,
        }

    @staticmethod
    def _reflect(task: TaskRequest, product: Optional[Dict[str, Any]], dream: Dict[str, Any]) -> Dict[str, Any]:
        top = dream["discrete_candidates"][0]["id"] if dream["discrete_candidates"] else None
        choice = None if product is None else product.get("choice")
        if choice is None:
            text = (
                f"No product for task {task.task_key}. "
                "Simulated leader {top} was not promoted.".format(top=top)
            )
        elif choice == top:
            text = (
                f"Product {choice} matched the simulated leader for task {task.task_key}. "
                "That agreement is not an observed outcome."
            )
        else:
            text = (
                f"Product {choice} differed from simulated leader {top} for task {task.task_key}. "
                "The simulated leader was kept as a candidate only."
            )
        return {"statement": text, "simulated_leader": top, "product_choice": choice}


def run_offline_demo(db_path: str, *, numeric_dream_count: int = 0) -> Dict[str, Any]:
    """Controlled offline task. Not a real-world validation.

    The dream surrogate prefers w08. The held-out loss prefers w05 and marks
    w08 as worse. After the outcome is stored, a new process object on the
    same file avoids w08.
    """
    options = ["w02", "w05", "w08"]
    dream_scores = {"w02": 0.2, "w05": 0.5, "w08": 0.8}
    task = TaskRequest(
        task_key="mixweight",
        objective="Choose a mixing weight using only offline arithmetic and stored lessons.",
        options=options,
        query="mixweight observed option",
        dream_scores=dream_scores,
        numeric_dream_count=numeric_dream_count,
        numeric_score=(lambda index: -((index / max(numeric_dream_count - 1, 1)) - 0.37) ** 2)
        if numeric_dream_count
        else None,
    )
    first = LearningCycle(db_path)
    before = first.run(task)
    before_hits = first.store.lexical_hits("mixweight avoid option w08", limit=5)
    outcome = first.record_observed_outcome(
        task_key="mixweight",
        measurements={"w02": 0.35, "w05": 0.05, "w08": 0.55},
        outcome_id="heldout-1",
    )
    after_hits = first.store.lexical_hits("mixweight avoid option w08", limit=5)
    second = LearningCycle(db_path)
    after = second.run(task)
    other = second.run(
        TaskRequest(
            task_key="paintmix",
            objective="Choose a mixing weight for a different task key.",
            options=options,
            query="paintmix option",
            dream_scores=dream_scores,
        )
    )
    return {
        "label": "controlled_offline_demo_not_real_world_validation",
        "before_choice": None if before["product"] is None else before["product"]["choice"],
        "before_reason": None if before["product"] is None else before["product"]["reason"],
        "after_choice": None if after["product"] is None else after["product"]["choice"],
        "after_reason": None if after["product"] is None else after["product"]["reason"],
        "after_avoided": None if after["product"] is None else after["product"]["avoided"],
        "other_task_choice": None if other["product"] is None else other["product"]["choice"],
        "lexical_before": before_hits,
        "lexical_after": after_hits,
        "outcome": {
            "best": outcome["best"],
            "worst": outcome["worst"],
            "lessons": [
                {
                    "id": row["id"],
                    "option_key": row["option_key"],
                    "polarity": row["polarity"],
                    "heat": row["heat"],
                    "confidence": row["confidence"],
                    "scope": row["scope"],
                    "support_count": row["support_count"],
                }
                for row in outcome["lessons"]
            ],
        },
        "numeric": before["stages"][-3]["output"]["numeric"] if numeric_dream_count else None,
        "exponential_learning": False,
    }


def demo_json(db_path: str, numeric_dream_count: int = 0) -> str:
    return json.dumps(run_offline_demo(db_path, numeric_dream_count=numeric_dream_count), indent=2)
