"""End-to-end RAG pipeline: ingest → chunk → embed → store → retrieve → answer.

Pillars, in pipeline order:

* **Organisation** — ``ingest()`` loads PDFs/text (``rag.loader``), splits them
  into overlapping chunks (``rag.chunker``), embeds them with Ollama
  (``rag.embeddings``) and stores text + dense vector + BM25 index in one
  SQLite file (``loci_engine.vectors.VectorStore``).
* **Guidance** — ``query()`` classifies the question (CARD, ``rag.card``) to
  choose recall depth K and a ranking strategy; retrieval reinforces the heat
  of every chunk it returns, and the dynamic τ gate
  (``loci_engine.tau_gate``) reports whether the hits look trustworthy.
* **Efficiency** — optionally compresses the retrieved context with TF-IDF
  (``loci_engine.compressor``) before it is sent to the model.

Every external call (embedding, generation) goes through ``embed`` and
``generate`` so tests can substitute offline fakes.
"""
import hashlib

from rag import config
from rag.card import apply_ranking_strategy, classify_query_category, recall_depth
from rag.chunker import chunk_documents
from rag.embeddings import embed
from rag.llm import generate
from rag.loader import load_documents
from loci_engine.compressor import TfidfCompressor
from loci_engine.tau_gate import dynamic_tau
from loci_engine.vectors import VectorStore

ABSTAIN_ANSWER = "I don't have enough reliable context to answer that."


def _chunk_id(source: str, page: int, start_index: int) -> str:
    return hashlib.sha256(f"{source}::{page}::{start_index}".encode()).hexdigest()


def ingest(data_dir: str | None = None) -> int:
    """Load, chunk, embed and store every document under ``data_dir``.

    Chunk ids are a hash of (source, page, offset), so re-ingesting the same
    files updates chunks in place instead of duplicating them. Returns the
    number of chunks written.
    """
    data_dir = data_dir or config.DATA_DIR
    documents = load_documents(data_dir)
    chunks = chunk_documents(documents)
    if not chunks:
        return 0

    texts = [chunk.page_content for chunk in chunks]
    ids = [
        _chunk_id(
            chunk.metadata["source"],
            chunk.metadata.get("page", 0),
            chunk.metadata["start_index"],
        )
        for chunk in chunks
    ]
    metadatas = [chunk.metadata for chunk in chunks]
    embeddings = embed(texts)

    engine = VectorStore(path=config.DB_PATH)
    try:
        engine.add(ids=ids, embeddings=embeddings, texts=texts, metadatas=metadatas)
    finally:
        engine.close()
    return len(chunks)


def _similarities(results: list[dict]) -> list[float]:
    """Dense L2 distance → similarity in (0, 1]; chunks found only by BM25 get 0."""
    return [1.0 / (1.0 + r["distance"]) if r.get("distance") is not None else 0.0 for r in results]


def query(question: str, top_k: int | None = None, neighborhood_window: int = 1) -> dict:
    """Answer ``question`` from the stored chunks.

    Returns ``{answer, sources, category, recall_depth, gate, compression}``.
    ``gate`` is the τ-gate decision (always computed; it only changes the
    answer when ``RAG_ABSTAIN_ON_GATE=1``). ``compression`` is ``None`` unless
    ``RAG_COMPRESS_RATIO`` > 0.
    """
    category = classify_query_category(question)
    k = top_k if top_k is not None else recall_depth(category)

    engine = VectorStore(path=config.DB_PATH)
    try:
        [query_embedding] = embed([question])
        # Fetch a wider pool for the gate's distribution-shape test, answer from top k.
        pool = engine.query(query_embedding, top_k=max(k, 8), query_text=question)
    finally:
        engine.close()

    gate = dynamic_tau(question, _similarities(pool))
    results = apply_ranking_strategy(category, pool[:k])
    # Broader relationship and timeline questions benefit from neighboring
    # chunks in the same source. Expansion is deliberately bounded and
    # provenance-preserving; it does not imply Drive/Gmail/Dropbox access.
    neighbors = []
    if category in {"multi_session_reasoning", "temporal_reasoning"} and neighborhood_window:
        engine = VectorStore(path=config.DB_PATH)
        try:
            neighbors = engine.neighbors(results, window=neighborhood_window)
        finally:
            engine.close()
    context_results = results + neighbors
    sources = sorted({r["metadata"].get("source", "?") for r in context_results})

    if config.ABSTAIN_ON_GATE and not gate.passed:
        return {"answer": ABSTAIN_ANSWER, "sources": [], "category": category,
                "recall_depth": k, "gate": gate.as_dict(), "compression": None}

    context = "\n\n".join(
        f"[{i + 1}] [source={r['metadata'].get('source', '?')}; "
        f"page={r['metadata'].get('page', 0)}; "
        f"relation={r.get('relation', 'retrieved')}] {r['text']}"
        for i, r in enumerate(context_results)
    )
    compression = None
    if config.COMPRESS_RATIO > 0 and context:
        res = TfidfCompressor().compress([r["text"] for r in context_results], question,
                                         target_ratio=config.COMPRESS_RATIO)
        context = res.text
        compression = {"ratio": round(res.ratio, 3), "original_tokens": res.original_tokens,
                       "compressed_tokens": res.compressed_tokens}

    prompt = (
        "Answer the question using only the numbered context below. "
        "If the context doesn't contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    answer = generate(prompt)

    return {"answer": answer, "sources": sources, "category": category, "recall_depth": k,
            "seed_count": len(results), "neighbor_count": len(neighbors),
            "context_count": len(context_results), "neighborhood_window": neighborhood_window,
            "gate": gate.as_dict(), "compression": compression}
