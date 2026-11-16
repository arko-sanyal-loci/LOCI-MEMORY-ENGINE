#!/usr/bin/env python3
"""
loci_engine/session_ingester.py
================================
Session Ingestion Pipeline — connects the live conversation feed to the
StorageEngine and CardRouter so CARD actually mediates recall.

WHAT THIS FILE SOLVES
---------------------
Before this file, CardRouter existed as a spec but had no connection to
the live LLM conversation.  StorageEngine had no session feed.  The result:
CARD could not retrieve facts mentioned earlier because there was no
earlier-in-session storage — only offline facts inserted via
memory_ingest_fact.

This file closes that gap:

  SessionIngester.ingest_turn()      — writes each message turn to
                                       memory_item, tagged with the calling
                                       agent's identity (source_actor)
  SessionIngester.recall_for_query() — loads active items, routes through
                                       CardRouter, returns top-K results
  SessionIngester.heat_decay_tick()  — recomputes stored heat via A1/A2
                                       so old items don't outrank fresh ones

ACTOR MODEL
-----------
Every session belongs to a primary actor (the human or agent driving it).
That identity propagates to every turn written via ingest_turn().  Agents
sharing a node can each create their own SessionIngester with their own
actor_id; recall_for_query() can then filter by actor_id so each agent sees
only its own context, or omit the filter to see the whole shared pool.

CARD ARCHETYPE ROUTING
----------------------
  information_extraction   K=5,  heat-descending   "what is X?"
  knowledge_update         K=3,  newest-first       "what's the latest on X?"
  multi_session_reasoning  K=10, gradient           "why / how across sessions"
  temporal_reasoning       K=7,  chronological      "earlier you said…"

author_ids: CLAUDE (implementation), ARKO (architecture direction)
"""

import uuid
from typing import Any, Dict, List, Optional

from loci_engine.storage import StorageEngine
from loci_engine.card_router import CardRouter


class SessionIngester:
    """Live session feed → StorageEngine pipeline.

    Parameters
    ----------
    storage         : StorageEngine — the shared storage instance
    session_id      : str           — unique ID for this session; auto-generated
                                      when not supplied
    actor_id        : str           — identity of the primary agent driving this
                                      session (e.g. 'arko', 'claude', 'arc').
                                      Written as source_actor on every turn.
                                      Defaults to 'unknown'; callers should
                                      always supply a real value.
    decay_on_init   : bool          — when True, run heat_decay_tick() on
                                      construction so stored heat reflects
                                      elapsed time before the first query
    decay_tau_days  : float         — τ for the init decay tick (days)
    """

    def __init__(
        self,
        storage: StorageEngine,
        session_id: Optional[str] = None,
        actor_id: str = "unknown",
        decay_on_init: bool = True,
        decay_tau_days: float = 3.0,
    ):
        self.storage    = storage
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.actor_id   = actor_id
        self.turn_count = 0

        if decay_on_init:
            self.heat_decay_tick(tau_days=decay_tau_days)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ingest_turn(
        self,
        role: str,
        content: str,
        heat: Optional[float] = None,
        namespace: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> str:
        """Write one conversation turn to cold storage.

        Each turn gets a deterministic ID: ``<session_id>_turn_<n:04d>``.
        Re-ingesting the same turn_id raises a SQLite UNIQUE constraint —
        a turn should be written exactly once.

        Parameters
        ----------
        role      : str        — 'user' or 'assistant'
        content   : str        — raw text of the turn
        heat      : float|None — override default heat
                                 (user=0.75, assistant=0.60)
        namespace : str|None   — override namespace (default: 'session')
        actor_id  : str|None   — override this session's actor_id for this
                                 turn only; useful when relaying another
                                 agent's message verbatim

        Returns
        -------
        str — the stored turn_id
        """
        self.turn_count += 1
        turn_id = f"{self.session_id}_turn_{self.turn_count:04d}"

        effective_heat  = heat     if heat     is not None else (0.75 if role == "user" else 0.60)
        effective_ns    = namespace if namespace is not None else "session"
        effective_actor = actor_id  if actor_id  is not None else self.actor_id

        self.storage.ingest_session_turn(
            turn_id=turn_id,
            role=role,
            content=content,
            namespace=effective_ns,
            heat=effective_heat,
            era="near",
            source_actor=effective_actor,
        )
        return turn_id

    def recall_for_query(
        self,
        query: str,
        namespace: Optional[str] = None,
        source_actor: Optional[str] = None,
        limit: int = 50,
        active_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """CARD-mediated recall for the current query.

        1. Loads active items from storage (filtered by namespace and/or actor
           when supplied).
        2. Routes them through CardRouter.execute_card_retrieval() — this
           classifies the query, ranks by effective heat (with lexical relevance
           boost when no embedding is present), enforces the token budget, and
           applies archetype-specific ordering.
        3. Returns the full CARD result dict.

        Parameters
        ----------
        query            : str           — the question or statement
        namespace        : str|None      — restrict pool to this namespace
        source_actor     : str|None      — restrict pool to this actor; pass
                                           self.actor_id to scope recall to the
                                           current session's agent only
        limit            : int           — max candidates to load (default 50)
        active_embedding : List[float]   — semantic vector; enables thermal
                                           gradient conduction in CardRouter

        Returns
        -------
        dict — CardRouter result:
               query, archetype, depth_k, token_budget, selected_items
        """
        candidates = self.storage.fetch_active_items(
            namespace=namespace,
            source_actor=source_actor,
            limit=limit,
        )
        return CardRouter.execute_card_retrieval(
            query=query,
            candidates=candidates,
            active_embedding=active_embedding,
        )

    def heat_decay_tick(
        self,
        tau_days: float = 3.0,
        alpha: float = 0.05,
    ) -> int:
        """Recompute and persist heat for all active items via A1/A2 decay.

        Should be called once at session start, or periodically, so that
        items written in previous sessions have decayed appropriately before
        CARD ranks them against fresh items.

        Parameters
        ----------
        tau_days : float — decay half-life in days
        alpha    : float — Constant of Hope floor

        Returns
        -------
        int — number of rows updated
        """
        return self.storage.decay_stored_heat(tau_days=tau_days, alpha=alpha)
