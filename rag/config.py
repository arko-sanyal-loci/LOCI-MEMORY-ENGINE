import os

OLLAMA_HOST = os.environ.get("RAG_OLLAMA_HOST", "http://127.0.0.1:11434")
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.environ.get("RAG_LLM_MODEL", "llama3.2")
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(
    os.environ.get("RAG_OLLAMA_CONNECT_TIMEOUT_SECONDS", "10")
)
# Separate from the connect timeout above: a real model's cold load + generation can take far
# longer than a healthy connection should take to establish (a 14B model's first request loads
# it into VRAM before generating a single token; a 30B+ expand-lane model longer still).
GENERATE_TIMEOUT_SECONDS = float(
    os.environ.get("RAG_GENERATE_TIMEOUT_SECONDS", "120")
)
CHROMA_DB_PATH = os.environ.get("RAG_CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = os.environ.get("RAG_COLLECTION_NAME", "documents")
DATA_DIR = os.environ.get("RAG_DATA_DIR", "./data")
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "50"))

# Per-role model lanes (docs/dual-gpu-coding-intelligence-blueprint.md, Phase 3.1).
# Compact and embedding default to the existing single Ollama instance (RTX 5060 Ti,
# already proven); expand has no default host, since it depends on the expand-lane
# server (llama-server/SYCL on the Arc B70) actually being up.
COMPACT_HOST = os.environ.get("RAG_COMPACT_HOST", OLLAMA_HOST)
COMPACT_MODEL = os.environ.get("RAG_COMPACT_MODEL", LLM_MODEL)
EMBEDDING_HOST = os.environ.get("RAG_EMBEDDING_HOST", OLLAMA_HOST)
EXPAND_HOST = os.environ.get("RAG_EXPAND_HOST")
EXPAND_MODEL = os.environ.get("RAG_EXPAND_MODEL")
