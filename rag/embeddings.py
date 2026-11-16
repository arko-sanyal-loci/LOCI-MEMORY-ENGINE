import httpx
import ollama

from rag import config


def embed(texts: list[str]) -> list[list[float]]:
    client = ollama.Client(
        host=config.EMBEDDING_HOST, timeout=config.OLLAMA_CONNECT_TIMEOUT_SECONDS
    )
    try:
        return [
            client.embeddings(model=config.EMBEDDING_MODEL, prompt=text)["embedding"]
            for text in texts
        ]
    except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
        raise ConnectionError(
            f"Could not reach Ollama at {config.EMBEDDING_HOST}. "
            "Start it with `ollama serve` and make sure "
            f"`{config.EMBEDDING_MODEL}` is pulled."
        ) from e
