import re
from typing import Iterable, List

from langchain_core.documents import Document


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")
_EXCESSIVE_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.replace("\ufeff", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = cleaned.replace("\u3000", " ")
    cleaned = _TRAILING_SPACE_RE.sub("\n", cleaned)
    cleaned = _EXCESSIVE_BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def clean_document(document: Document) -> Document:
    metadata = dict(getattr(document, "metadata", {}) or {})
    return Document(page_content=clean_text(document.page_content), metadata=metadata)


def clean_documents(documents: Iterable[Document]) -> List[Document]:
    return [clean_document(document) for document in documents if clean_text(document.page_content)]
