"""Small deterministic BM25-style retrieval for the honest offline demo."""

import math
import re
from collections import Counter

from .documents import Chunk

ENGLISH_STOP = set("a an and are as at be by can do for from how i in is it its me my of on or our please that the their them there these this to was we what when where which who will with you your".split())
CHINESE_STOP = set("的了是在有和我你它这那吗呢请问如何怎么什么以可为与或")


def tokenize(text: str) -> list[str]:
    tokens = []
    for value in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", text.lower()):
        if value.isascii():
            if value not in ENGLISH_STOP:
                tokens.append(value)
        else:
            tokens.extend(c for c in value if c not in CHINESE_STOP)
            tokens.extend(value[i:i + 2] for i in range(len(value) - 1) if not set(value[i:i + 2]) <= CHINESE_STOP)
    return tokens


class LexicalIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = list(chunks)
        self.terms = [Counter(tokenize(chunk.text)) for chunk in self.chunks]
        self.lengths = [sum(terms.values()) for terms in self.terms]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1)
        self.document_frequency = Counter(term for terms in self.terms for term in terms)

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        if not self.chunks or top_k <= 0:
            return []
        terms = set(tokenize(query))
        ranked = []
        count = len(self.chunks)
        for i, frequencies in enumerate(self.terms):
            score = 0.0
            for term in terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                df = self.document_frequency[term]
                inverse_frequency = math.log(1 + (count - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.5 * (0.25 + 0.75 * self.lengths[i] / max(self.average_length, 1))
                score += inverse_frequency * frequency * 2.5 / denominator
            if score > 0:
                ranked.append((score, self.chunks[i]))
        ranked.sort(key=lambda item: (-item[0], item[1].source, item[1].start))
        return [chunk.citation(score) for score, chunk in ranked[:top_k]]
