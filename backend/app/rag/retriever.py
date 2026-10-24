"""High-level retrieval helpers used by the teaching engine."""
from __future__ import annotations

from . import store


def retrieve_context(material_id: str | None, query_text: str, k: int = 5) -> str:
    """Return a grounded context block for the given query, or ''.

    The teaching engine passes this into prompts so explanations are
    grounded in the uploaded material (RAG) and hallucination is reduced.
    """
    if not material_id:
        return ""
    hits = store.query(material_id, query_text, k=k)
    if not hits:
        return ""
    blocks = []
    for i, h in enumerate(hits, 1):
        src = h["meta"].get("source", "material")
        blocks.append(f"[Excerpt {i} | {src} | relevance {h['score']:.2f}]\n{h['text']}")
    return "\n\n".join(blocks)