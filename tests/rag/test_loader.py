import pytest

from rag.loader import load_documents

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 44>>
stream
BT /F1 24 Tf 10 100 Td (Hello PDF world) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF"""


def test_load_documents_raises_when_data_dir_missing(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError, match="No documents found"):
        load_documents(str(missing))


def test_load_documents_raises_when_data_dir_empty(tmp_path):
    with pytest.raises(FileNotFoundError, match="No documents found"):
        load_documents(str(tmp_path))


def test_load_documents_reads_txt_file_content_and_source(tmp_path):
    txt_file = tmp_path / "note.txt"
    txt_file.write_text("hello from a text file")

    documents = load_documents(str(tmp_path))

    assert len(documents) == 1
    assert documents[0].page_content == "hello from a text file"
    assert documents[0].metadata["source"] == str(txt_file)


def test_load_documents_reads_pdf_file_content(tmp_path):
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(MINIMAL_PDF)

    documents = load_documents(str(tmp_path))

    assert len(documents) == 1
    assert "Hello PDF world" in documents[0].page_content
