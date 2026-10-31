"""Store-policy retrieval over the internal policies PDF (PDF → BM25 index).

Design notes
------------
The policies manual is only 8 pages, but hard-coding it into the prompt would
(1) waste context on every turn and (2) not scale to a real manual. Instead we
chunk the PDF by *section* (keeping headings attached to their content) and
index the chunks with BM25 — a lexical, dependency-light ranking function that
performs very well on a corpus this small and in Portuguese, once accents are
normalized.

This is a deliberate trade-off over dense embeddings: no model download
(~500 MB+ for a multilingual MiniLM), fully deterministic, instant startup.
With a larger corpus the natural evolution is multilingual embeddings +
a vector store (see README, "Limitations").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pdfplumber
from nltk.stem.snowball import SnowballStemmer
from rank_bm25 import BM25Okapi

from .config import POLICIES_PDF

# Boilerplate repeated on every page of the PDF — noise for retrieval.
_PAGE_NOISE = [
    r"Empório da Música\s+Manual de Políticas e Procedimentos",
    r"Página \d+",
]

_SECTION_RE = re.compile(
    r"^(?P<title>\d+(?:\.\d+)*\.?\s+.+)$", re.MULTILINE
)

# Sections small enough to be kept whole; larger ones are split further.
_MAX_CHUNK_CHARS = 1100


@dataclass(frozen=True)
class PolicyChunk:
    section: str
    page: int
    text: str


def _strip_accents(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def _clean_page(raw: str) -> str:
    text = raw
    for pattern in _PAGE_NOISE:
        text = re.sub(pattern, " ", text)
    # Collapse whitespace artifacts from PDF extraction.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_sections(pages: list[str]) -> list[tuple[str, int, str]]:
    """Group page text into (section_title, page, body) pairs."""
    sections: list[tuple[str, int, str]] = []
    current_title = "Capa / Abertura"
    buffer: list[str] = []
    start_page = 1
    page_no = 0

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_title, start_page, body))
        buffer.clear()

    for page_no, page in enumerate(pages, start=1):
        clean = _clean_page(page)
        if not clean:
            continue
        # Split the page line-by-line, detecting section headings inline.
        lines = clean.split("\n")
        for line in lines:
            if re.match(r"^\d+(?:\.\d+)*\.?\s+\S", line.strip()) and len(
                line.strip()
            ) < 90:
                flush()
                current_title = line.strip()
                start_page = page_no
            else:
                buffer.append(line)
        flush_end_of_page = False  # sections may span pages; keep buffering
        _ = flush_end_of_page
    flush()
    return sections


def _split_long(section: str, page: int, body: str) -> list[PolicyChunk]:
    """Keep sections whole when possible; split long ones by paragraph."""
    if len(body) <= _MAX_CHUNK_CHARS:
        return [PolicyChunk(section, page, body)]
    chunks, buf = [], ""
    for paragraph in re.split(r"\n\s*\n", body):
        candidate = f"{buf}\n\n{paragraph}".strip()
        if len(candidate) > _MAX_CHUNK_CHARS and buf:
            chunks.append(PolicyChunk(section, page, buf))
            buf = paragraph
        else:
            buf = candidate
    if buf:
        chunks.append(PolicyChunk(section, page, buf))
    return chunks


def _merge_fragments(
    sections: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Attach numbered-list lines misdetected as sections back to their parent.

    Headings and list items share the "N. text" shape; a real section has
    substantial content, so anything with a tiny body is folded into the
    previous section instead of becoming its own chunk.
    """
    merged: list[tuple[str, int, str]] = []
    for title, page, body in sections:
        if merged and len(body.strip()) < 80:
            prev_title, prev_page, prev_body = merged[-1]
            merged[-1] = (
                prev_title,
                prev_page,
                f"{prev_body}\n{title} {body}".strip(),
            )
        else:
            merged.append((title, page, body))
    return merged


class PolicyIndex:
    """BM25 index over the chunked store policies PDF."""

    def __init__(self, pdf_path=POLICIES_PDF) -> None:
        self._stemmer = SnowballStemmer("portuguese")
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        self.chunks: list[PolicyChunk] = []
        for title, page, body in _merge_fragments(_extract_sections(pages)):
            self.chunks.extend(_split_long(title, page, body))
        corpus = [self._tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(corpus)

    def _tokenize(self, text: str) -> list[str]:
        normalized = _strip_accents(text.lower())
        return [
            self._stemmer.stem(tok)
            for tok in re.findall(r"[a-z0-9]{2,}", normalized)
        ]

    def search(self, query: str, k: int = 4) -> list[PolicyChunk]:
        """Return the k policy chunks most relevant to the query."""
        if not self.chunks:
            return []
        scores = self._bm25.get_scores(self._tokenize(query))
        ranked = sorted(
            zip(scores, self.chunks), key=lambda pair: pair[0], reverse=True
        )
        return [chunk for score, chunk in ranked[:k] if score > 0]
