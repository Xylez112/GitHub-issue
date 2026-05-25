"""BM25 keyword search for hybrid retrieval (sparse + dense)."""
import re

from rank_bm25 import BM25Okapi

from ..models.schemas import CodeSnippet


class BM25Searcher:
    """Builds a BM25 index from code snippets and provides keyword search."""

    def __init__(self, snippets: list[CodeSnippet]):
        self.snippets = snippets
        self._docs = [self._format_doc(s) for s in snippets]
        self._tokenized = [self._tokenize(d) for d in self._docs]
        self._index = BM25Okapi(self._tokenized)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase + split on word boundaries. Underscores are preserved."""
        return re.findall(r"\w+", text.lower())

    @staticmethod
    def _format_doc(s: CodeSnippet) -> str:
        """Include file path + name in the searchable text, not just code."""
        return f"{s.file_path} {s.name} {s.kind} {s.code}"

    def search(self, query: str, top_k: int = 10) -> list[tuple[CodeSnippet, float]]:
        """Search for code snippets matching the query via BM25."""
        tokens = self._tokenize(query)
        scores = self._index.get_scores(tokens)
        # Return top-k results with positive scores
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_k]:
            if score > 0:
                results.append((self.snippets[idx], float(score)))
        return results
