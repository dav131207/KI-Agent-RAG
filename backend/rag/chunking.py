"""
Semantic text chunking strategies.

The default sliding-window chunker cuts text at fixed character boundaries,
which can split sentences and hurt retrieval quality. The semantic chunker
keeps paragraphs and sentences intact while respecting a maximum chunk size.
"""

import re
from typing import List


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs, preserving empty lines as structure hints."""
    paragraphs = [p.strip() for p in text.split("\n\n")]
    return [p for p in paragraphs if p]


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using a simple regex heuristic."""
    # Keep abbreviations like "Dr.", "e.g.", "i.e." from breaking sentences.
    text = re.sub(r"\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|e\.g|i\.e|etc)\.", r"\1<DOT>", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.replace("<DOT>", ".").strip() for s in sentences if s.strip()]


def semantic_chunk_text(
    text: str,
    max_chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """
    Chunk text by paragraphs first, then sentences, while keeping chunks
    under max_chunk_size. Overlap is applied at sentence boundaries.

    This preserves semantic coherence compared to fixed-size character chunks.
    """
    paragraphs = _split_into_paragraphs(text)
    chunks: List[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= max_chunk_size:
            chunks.append(paragraph)
            continue

        sentences = _split_into_sentences(paragraph)
        current_chunk = ""

        for sentence in sentences:
            candidate = current_chunk + (" " if current_chunk else "") + sentence
            if len(candidate) <= max_chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start the next chunk with overlap from the previous chunk.
                if current_chunk and chunk_overlap:
                    words = current_chunk.split()
                    overlap_text = ""
                    for word in reversed(words):
                        candidate_overlap = word + (" " + overlap_text if overlap_text else "")
                        if len(candidate_overlap) <= chunk_overlap:
                            overlap_text = candidate_overlap
                        else:
                            break
                    current_chunk = overlap_text.strip() + (" " if overlap_text else "") + sentence
                else:
                    current_chunk = sentence

                # If a single sentence is longer than the max chunk size, split it hard.
                if len(current_chunk) > max_chunk_size:
                    chunks.append(current_chunk[:max_chunk_size].strip())
                    current_chunk = current_chunk[max_chunk_size - chunk_overlap :].strip()

        if current_chunk:
            chunks.append(current_chunk.strip())

    return chunks


def sliding_window_chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[str]:
    """Legacy fixed-size character chunking, kept for comparison."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks
