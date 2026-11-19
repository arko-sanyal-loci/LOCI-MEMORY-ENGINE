"""Runtime configuration for the RAG pipeline, read from environment variables.

Every setting has a working local default, so ``python -m rag ingest`` /
``python -m rag query`` work against a stock Ollama install with no setup.
See USER_GUIDE.md for the full table.
"""
import os

OLLAMA_HOST = os.environ.get("RAG_OLLAMA_HOST", "http://127.0.0.1:11434")
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.environ.get("RAG_LLM_MODEL", "llama3.2")
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(
    os.environ.get("RAG_OLLAMA_CONNECT_TIMEOUT_SECONDS", "10")
)
GENERATE_TIMEOUT_SECONDS = float(
    os.environ.get("RAG_GENERATE_TIMEOUT_SECONDS", "120")
)
# Path of the single SQLite file that holds chunks, embeddings and the FTS index
# (loci_engine.vectors.VectorStore). The old name RAG_CHROMA_DB_PATH is still
# honoured; its old default "./chroma_db" pointed at a directory left over from
# the ChromaDB era, which VectorStore rejects, so the default is now a file.
DB_PATH = os.environ.get("RAG_DB_PATH") or os.environ.get("RAG_CHROMA_DB_PATH") or "./loci_rag.db"
CHROMA_DB_PATH = DB_PATH  # deprecated alias, kept for old callers
DATA_DIR = os.environ.get("RAG_DATA_DIR", "./data")
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "50"))

# Efficiency: TF-IDF compression of the retrieved context before generation
# (loci_engine.compressor). 0 disables; e.g. 3.0 keeps about a third.
COMPRESS_RATIO = float(os.environ.get("RAG_COMPRESS_RATIO", "0"))
# Guidance: when "1", abstain instead of answering if the dynamic τ gate says
# the retrieved hits are not trustworthy (loci_engine.tau_gate).
ABSTAIN_ON_GATE = os.environ.get("RAG_ABSTAIN_ON_GATE", "0") == "1"

COMPACT_HOST = os.environ.get("RAG_COMPACT_HOST", OLLAMA_HOST)
COMPACT_MODEL = os.environ.get("RAG_COMPACT_MODEL", LLM_MODEL)
EMBEDDING_HOST = os.environ.get("RAG_EMBEDDING_HOST", OLLAMA_HOST)
EXPAND_HOST = os.environ.get("RAG_EXPAND_HOST")
EXPAND_MODEL = os.environ.get("RAG_EXPAND_MODEL")
