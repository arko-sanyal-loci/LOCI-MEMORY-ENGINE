import hashlib

from rag import config
from rag.card import apply_ranking_strategy, classify_query_category, recall_depth
from rag.chunker import chunk_documents
from rag.embeddings import embed
from rag.llm import generate
from rag.loader import load_documents
from loci_engine.vectors import VectorStore


def _chunk_id(source: str, page: int, start_index: int) -> str:
    return hashlib.sha256(f"{source}::{page}::{start_index}".encode()).hexdigest()


def ingest(data_dir: str | None = None) -> int:
    data_dir = data_dir or config.DATA_DIR
    documents = load_documents(data_dir)
    chunks = chunk_documents(documents)

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

    engine = VectorStore(path=config.CHROMA_DB_PATH)
    engine.add(ids=ids, embeddings=embeddings, texts=texts, metadatas=metadatas)
    return len(chunks)


def query(question: str, top_k: int | None = None) -> dict:
    category = classify_query_category(question)
    k = top_k if top_k is not None else recall_depth(category)

    engine = VectorStore(path=config.CHROMA_DB_PATH)
    [query_embedding] = embed([question])
    results = engine.query(query_embedding, top_k=k, query_text=question)
    results = apply_ranking_strategy(category, results)

    context = "\n\n".join(f"[{i + 1}] {r['text']}" for i, r in enumerate(results))
    prompt = (
        "Answer the question using only the numbered context below. "
        "If the context doesn't contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    answer = generate(prompt)
    sources = sorted({r["metadata"]["source"] for r in results})

    return {"answer": answer, "sources": sources, "category": category, "recall_depth": k}
