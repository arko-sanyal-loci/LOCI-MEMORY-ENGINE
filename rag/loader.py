from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader


def _load_pdf(file_path: str) -> list[Document]:
    """Load PDF file and return list of Document objects."""
    reader = PdfReader(file_path)
    documents = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        documents.append(
            Document(page_content=text, metadata={"source": file_path, "page": page_num})
        )
    return documents


def _load_text(file_path: str) -> list[Document]:
    """Load text file (.txt or .md) and return list of Document objects."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return [Document(page_content=content, metadata={"source": file_path})]


_LOADERS = {".pdf": _load_pdf, ".txt": _load_text, ".md": _load_text}


def load_documents(data_dir: str) -> list[Document]:
    path = Path(data_dir)
    files = (
        [f for f in path.iterdir() if f.suffix.lower() in _LOADERS]
        if path.is_dir()
        else []
    )

    if not files:
        raise FileNotFoundError(
            f"No documents found in {data_dir}. Add .txt, .md, or .pdf files to ingest."
        )

    documents = []
    for file in sorted(files):
        documents.extend(_LOADERS[file.suffix.lower()](str(file)))
    return documents
