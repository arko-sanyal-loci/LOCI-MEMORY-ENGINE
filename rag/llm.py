import httpx

from rag import config

_ROLE_ATTRS = {
    "compact": ("COMPACT_HOST", "COMPACT_MODEL"),
    "expand": ("EXPAND_HOST", "EXPAND_MODEL"),
}


def _resolve_role(role: str) -> tuple[str, str]:
    if role not in _ROLE_ATTRS:
        raise ValueError(f"Unknown model role {role!r}; expected one of {sorted(_ROLE_ATTRS)}")
    host_attr, model_attr = _ROLE_ATTRS[role]
    host = getattr(config, host_attr)
    model = getattr(config, model_attr)
    if not host or not model:
        raise ConnectionError(
            f"The {role} lane is not configured (RAG_{host_attr}/RAG_{model_attr} are unset)."
        )
    return host, model


def generate(prompt: str, role: str = "compact") -> str:
    host, model = _resolve_role(role)
    timeout = httpx.Timeout(
        connect=config.OLLAMA_CONNECT_TIMEOUT_SECONDS,
        read=config.GENERATE_TIMEOUT_SECONDS,
        write=config.OLLAMA_CONNECT_TIMEOUT_SECONDS,
        pool=config.OLLAMA_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        response = httpx.post(
            f"{host}/v1/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        if role == "compact":
            raise ConnectionError(
                f"Could not reach Ollama at {host}. "
                "Start it with `ollama serve` and make sure "
                f"`{model}` is pulled."
            ) from e
        raise ConnectionError(
            f"Could not reach the expand-lane server at {host}. "
            f"Start llama-server with `{model}` loaded."
        ) from e
