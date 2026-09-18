from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Chunk:
    """Фрагмент базы знаний: заголовок раздела + текст."""

    section: str
    text: str


def load_chunks(path: str, min_chars: int = 80) -> list[Chunk]:
    """Режем базу знаний на фрагменты по разделам (## заголовок) и абзацам."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"База знаний не найдена: {file_path.resolve()}")

    chunks: list[Chunk] = []
    section = "Общее"
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = " ".join(buffer).strip()
        if text:
            chunks.append(Chunk(section=section, text=text))
        buffer.clear()

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip()
            continue

        if not line:
            if sum(len(s) for s in buffer) >= min_chars:
                flush()
            continue

        buffer.append(line)
        if sum(len(s) for s in buffer) >= min_chars * 3:
            flush()

    flush()

    logger.info("knowledge_base_loaded", path=str(file_path), chunks=len(chunks))
    return chunks
