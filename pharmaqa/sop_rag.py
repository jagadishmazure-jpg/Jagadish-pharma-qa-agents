"""TF-IDF retrieval over the 4 QA SOP documents.

Every answer cites `file §section`; when nothing scores above the floor the
retriever says so explicitly instead of inventing content.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_FLOOR = 0.08


@dataclass
class Chunk:
    file: str
    section: str
    text: str


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def load_chunks(sop_dir: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(sop_dir).glob("*.md")):
        section, buf = "", []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if buf and section:
                    chunks.append(Chunk(path.name, section, "\n".join(buf)))
                elif buf:
                    # skip title-only intro chunks: they inflate scores on
                    # single shared words (learned the hard way)
                    pass
                section, buf = line[3:].strip(), []
            else:
                buf.append(line)
        if buf and section:
            chunks.append(Chunk(path.name, section, "\n".join(buf)))
    return chunks


class SopRetriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        df: dict[str, int] = {}
        self._tf: list[dict[str, int]] = []
        for c in chunks:
            toks = _tokens(c.text)
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        n = len(chunks)
        self._idf = {t: math.log((n + 1) / (f + 1)) + 1.0 for t, f in df.items()}

    def _score(self, i: int, qtoks: list[str]) -> float:
        tf = self._tf[i]
        return sum(tf.get(t, 0) * self._idf.get(t, 0.0) for t in set(qtoks))

    def retrieve(self, question: str, k: int = 2) -> list[Chunk]:
        qtoks = _tokens(question)
        scored = sorted(
            ((self._score(i, qtoks), c) for i, c in enumerate(self.chunks)),
            key=lambda p: -p[0],
        )
        return [c for s, c in scored[:k] if s >= _FLOOR]

    def answer(self, question: str) -> str:
        hits = self.retrieve(question)
        if not hits:
            return ("No SOP section covers this question. I cannot answer from "
                    "the controlled documents.")
        cites = " ".join(f"[{c.file} §{c.section}]" for c in hits)
        excerpts = " ".join(" ".join(c.text.split()[:60]) for c in hits)
        return f"{cites} {excerpts}…"
