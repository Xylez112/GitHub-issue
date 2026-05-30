import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..core.config import settings, setup_logging
from ..models.schemas import CodeSnippet

logger = setup_logging(__name__)

# 本地 embedding 模型（第一次调用时自动下载，约 80MB）
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ChromaDB persistent client
_chroma_client = chromadb.PersistentClient(
    path=settings.chroma_persist_dir,
    settings=ChromaSettings(anonymized_telemetry=False),
)


def _format_snippet(s: CodeSnippet) -> str:
    return f"# {s.file_path}:{s.name} ({s.kind})\n{s.code}"


def _embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    embeddings = model.encode(texts)
    return embeddings.tolist()


def index_snippets(
    snippets: list[CodeSnippet], collection_name: str
) -> str:
    """Embed code snippets and store in a new ChromaDB collection."""
    collection = _chroma_client.get_or_create_collection(name=collection_name)

    documents = [_format_snippet(s) for s in snippets]
    ids = [str(uuid.uuid4()) for _ in snippets]
    metadatas = [
        {
            "file_path": s.file_path,
            "name": s.name,
            "kind": s.kind,
            "line_start": s.line_start,
            "line_end": s.line_end,
        }
        for s in snippets
    ]

    # Batch embedding in chunks of 100
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]

        embeddings = _embed_texts(batch_docs)
        collection.add(
            documents=batch_docs,
            embeddings=embeddings,
            ids=batch_ids,
            metadatas=batch_meta,
        )

    return collection_name


def search_snippets(
    query: str, collection_name: str, top_k: int = 10
) -> list[tuple[CodeSnippet, float]]:
    """Search for most relevant code snippets given a query text."""
    collection = _chroma_client.get_collection(name=collection_name)

    query_embedding = _embed_texts([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    snippets = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            document = results["documents"][0][i]
            distance = results["distances"][0][i]
            # Convert distance (L2 by default) to a rough similarity score
            similarity = 1.0 / (1.0 + distance)
            logger.debug("match: %s | similarity: %.3f", metadata["name"], similarity)
            snippets.append((
                CodeSnippet(
                    file_path=metadata["file_path"],
                    name=metadata["name"],
                    line_start=metadata["line_start"],
                    line_end=metadata["line_end"],
                    code=document,
                    kind=metadata["kind"],
                ),
                similarity,
            ))

    return snippets


def delete_collection(collection_name: str):
    try:
        _chroma_client.delete_collection(name=collection_name)
    except ValueError:
        pass
