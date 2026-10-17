"""Parser for narration scripts (.txt and .docx)."""

from __future__ import annotations

from pathlib import Path

from docx import Document


def parse_script_file(file_path: str | Path) -> str:
    """Read narration text from a .txt or .docx file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Script file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    elif suffix == ".docx":
        doc = Document(str(path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Supported: .txt, .docx")

    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"Script file '{path}' is empty.")
    return cleaned
