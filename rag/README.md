# rag/ — Ollama Document RAG Pipeline

A local, offline document retrieval-augmented generation pipeline built on Ollama.
Uses CARD (Category-Adaptive Recall Depth) for query classification, sqlite-vec + FTS5
for hybrid search, and Reciprocal Rank Fusion for result ranking.

Ported from `arko-sanyal-loci/loci-memory-engine-1` [legacy] (consolidated Nov 2026).

## Dependencies

Requires [Ollama](https://ollama.com) running locally:
```bash
ollama pull nomic-embed-text   # embeddings
ollama pull llama3.2            # generation (compact lane)
ollama serve
```

Install:
```bash
pip install -e '.[rag]'
```

## Usage

```bash
# Ingest .pdf / .txt / .md files
python -m rag ingest --data-dir ./data

# Query (CARD auto-selects recall depth)
python -m rag query "What does paper 04 say about recall depth?"
python -m rag query "What changed recently?" --top-k 3
```

## Configuration

All settings are environment-overridable via `rag/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `RAG_OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server URL |
| `RAG_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `RAG_LLM_MODEL` | `llama3.2` | Compact-lane generation model |
| `RAG_EXPAND_HOST` / `RAG_EXPAND_MODEL` | unset | Expand-lane (high-param) model |
| `RAG_CHROMA_DB_PATH` | `./chroma_db` | sqlite-vec+FTS5 store path |
| `RAG_DATA_DIR` | `./data` | Document ingestion directory |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `500` / `50` | Chunking parameters |

## Modules

| Module | Purpose |
|---|---|
| `card.py` | CARD query classification → recall depth + ranking strategy |
| `chunker.py` | LangChain recursive text splitter |
| `embeddings.py` | Ollama embedding client |
| `llm.py` | Ollama generation client (compact/expand lanes) |
| `loader.py` | PDF / TXT / MD document loader |
| `pipeline.py` | End-to-end ingest + query pipeline |
| `cli.py` | `rag ingest` / `rag query` CLI |
| `config.py` | Environment-based configuration |
