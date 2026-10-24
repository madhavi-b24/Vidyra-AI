"""Vector store built on ChromaDB with FREE local embeddings.

Embeddings default to sentence-transformers (offline). Gemini free-tier
embeddings are also supported. Each uploaded document is a Chroma
collection keyed by material_id so lessons can be grounded per-source.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

from ..config import settings
from .ingest import chunk_text, extract_text


# --------------------------------------------------------------------------
# Embedding functions (FREE)
# --------------------------------------------------------------------------
@lru_cache
def _local_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embeddings_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    provider = settings.embeddings_provider.lower()
    if provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        out = []
        for t in texts:
            r = genai.embed_content(
                model="models/text-embedding-004", content=t
            )
            out.append(r["embedding"])
        return out
    # default: local, offline, free
    model = _local_embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------
@lru_cache
def _client():
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )


def _collection(material_id: str):
    return _client().get_or_create_collection(
        name=f"mat_{material_id}", metadata={"hnsw:space": "cosine"}
    )


def make_material_id(filename: str) -> str:
    h = hashlib.sha1(filename.encode()).hexdigest()[:10]
    return h


def ingest_document(path: str, filename: str) -> dict:
    """Parse, chunk, embed and store a document. Returns summary info."""
    material_id = make_material_id(filename + str(path))
    text = extract_text(path)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No extractable text found in document.")

    coll = _collection(material_id)
    # reset any previous version
    existing = coll.get()
    if existing["ids"]:
        coll.delete(ids=existing["ids"])

    embeddings = embed_texts(chunks)
    ids = [f"{material_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": filename, "chunk": i} for i in range(len(chunks))]
    coll.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)

    return {
        "material_id": material_id,
        "filename": filename,
        "chunks": len(chunks),
        "chars": len(text),
        "preview": text[:600],
    }


def query(material_id: str, question: str, k: int = 5) -> list[dict]:
    coll = _collection(material_id)
    if coll.count() == 0:
        return []
    emb = embed_texts([question])[0]
    res = coll.query(query_embeddings=[emb], n_results=min(k, coll.count()))
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    out = []
    for d, m, dist in zip(docs, metas, dists):
        out.append({"text": d, "meta": m, "score": 1 - dist})
    return out