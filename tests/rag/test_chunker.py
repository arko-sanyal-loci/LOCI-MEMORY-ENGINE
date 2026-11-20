from langchain_core.documents import Document

from rag.chunker import chunk_documents


def test_chunk_documents_splits_long_text_into_multiple_chunks():
    long_text = "word " * 300  # well over the 500-char default chunk size
    doc = Document(page_content=long_text, metadata={"source": "long.txt"})

    chunks = chunk_documents([doc])

    assert len(chunks) > 1


def test_chunk_documents_preserves_source_metadata():
    long_text = "word " * 300
    doc = Document(page_content=long_text, metadata={"source": "long.txt"})

    chunks = chunk_documents([doc])

    assert all(chunk.metadata["source"] == "long.txt" for chunk in chunks)


def test_chunk_documents_does_not_split_short_text():
    doc = Document(page_content="a short document", metadata={"source": "short.txt"})

    chunks = chunk_documents([doc])

    assert len(chunks) == 1
    assert chunks[0].page_content == "a short document"


def test_chunk_documents_tags_each_chunk_with_a_distinct_position():
    long_text = "word " * 300
    doc = Document(page_content=long_text, metadata={"source": "long.txt"})

    chunks = chunk_documents([doc])
    positions = [chunk.metadata["start_index"] for chunk in chunks]

    assert len(set(positions)) == len(chunks)
