"""Tests for the knowledge base text chunker."""

from __future__ import annotations

import pytest

from src.adapters.knowledge.chunker import chunk_text


class TestChunkText:
    def test_basic_chunking_returns_correct_number_of_chunks(self) -> None:
        # 10 words, chunk_size=5, overlap=0 → 2 chunks
        text = "one two three four five six seven eight nine ten"
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        assert len(chunks) == 2

    def test_chunk_has_required_fields(self) -> None:
        text = "hello world foo bar baz"
        chunks = chunk_text(text, chunk_size=3, overlap=0)
        for chunk in chunks:
            assert "text" in chunk
            assert "chunk_index" in chunk

    def test_chunk_index_is_sequential(self) -> None:
        text = " ".join([f"word{i}" for i in range(20)])
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i

    def test_overlap_creates_shared_words(self) -> None:
        text = "one two three four five six seven eight"
        chunks = chunk_text(text, chunk_size=4, overlap=2)
        # First chunk: one two three four
        # Second chunk: three four five six  (overlap=2 shared words)
        assert "three" in chunks[1]["text"]
        assert "four" in chunks[1]["text"]

    def test_short_text_returns_single_chunk(self) -> None:
        text = "just a few words"
        chunks = chunk_text(text, chunk_size=512, overlap=64)
        assert len(chunks) == 1
        assert chunks[0]["text"] == text

    def test_empty_text_returns_empty_list(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_single_word_returns_single_chunk(self) -> None:
        chunks = chunk_text("hello", chunk_size=10, overlap=0)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "hello"

    def test_large_overlap_does_not_infinite_loop(self) -> None:
        # overlap >= chunk_size should not cause infinite loop
        text = " ".join([f"w{i}" for i in range(20)])
        chunks = chunk_text(text, chunk_size=5, overlap=10)  # overlap > chunk_size
        assert len(chunks) > 0
        # Verify it terminates
        assert chunks[-1]["chunk_index"] >= 0
