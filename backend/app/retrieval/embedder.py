from pathlib import Path
from typing import Protocol

from app.retrieval.representation import DIMENSION, MODEL_ID, MODEL_REVISION, bounded_text


class Embedder(Protocol):
    def encode(self, text: str) -> list[float]: ...


class LocalE5Embedder:
    def __init__(self, path: str) -> None:
        location = Path(path)
        if not location.is_dir() or not (location / "modules.json").exists():
            raise RuntimeError("Pinned E5 model is unavailable locally. Run the documented provision-model command first.")
        if not (location / "revision.txt").exists() or (location / "revision.txt").read_text().strip() != MODEL_REVISION:
            raise RuntimeError("Local E5 artifact does not declare the pinned revision.")
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(str(location), local_files_only=True, trust_remote_code=False, device="cpu")
        if self.model.get_sentence_embedding_dimension() != DIMENSION:
            raise RuntimeError("Local embedding model has the wrong dimension.")
        self.tokenizer = self.model.tokenizer
        if self.tokenizer.num_special_tokens_to_add(pair=False) != 2:
            raise RuntimeError("Unexpected E5 tokenizer special-token contract.")

    def encode(self, text: str) -> list[float]:
        bounded = bounded_text(text, self.tokenizer)
        value = self.model.encode([bounded], normalize_embeddings=True, convert_to_numpy=True)[0]
        if len(value) != DIMENSION:
            raise RuntimeError("Embedding dimension mismatch.")
        return [float(item) for item in value]


def default_embedder() -> LocalE5Embedder:
    from os import environ

    return LocalE5Embedder(environ.get("DENSE_MODEL_PATH", "../models/multilingual-e5-small-fd1525a"))
