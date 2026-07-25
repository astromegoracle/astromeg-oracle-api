#!/usr/bin/env python3
"""Build Astromeg Oracle's private retrieval corpus from a dataset ZIP."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

from pypdf import PdfReader


SOURCE_PROFILES = (
    {
        "match": "reading_style",
        "category": "reading_style",
        "priority": 10,
        "keywords": [
            "reading sequence",
            "voice",
            "interpretation",
            "action plan",
            "love",
            "money",
            "career",
            "healing",
            "inner child",
            "saturn",
            "mars",
            "venus",
            "dispositor",
        ],
    },
    {
        "match": "professional_astrologer_chart_drafting",
        "category": "chart_drafting",
        "priority": 9,
        "keywords": [
            "chart drafting",
            "placements",
            "houses",
            "aspects",
            "aspect grid",
            "table",
            "professional astrologer",
            "client ready",
        ],
    },
    {
        "match": "advanced_charts",
        "category": "advanced_chart_method",
        "priority": 9,
        "keywords": [
            "advanced chart",
            "solar return",
            "progression",
            "solar arc",
            "harmonic",
            "draconic",
            "firdaria",
            "profection",
            "arabic parts",
            "fixed stars",
            "saros",
            "relationship",
            "electional",
        ],
    },
    {
        "match": "advanced_astrology",
        "category": "advanced_astrology",
        "priority": 9,
        "keywords": [
            "draconic",
            "harmonic",
            "solar return",
            "arabic parts",
            "progression",
            "profection",
            "firdaria",
            "solar arc",
            "brand chart",
            "saros",
        ],
    },
    {
        "match": "progressed_charts",
        "category": "progressed_charts",
        "priority": 9,
        "keywords": [
            "progressed chart",
            "secondary progression",
            "progressed moon",
            "progressed ascendant",
            "solar arc",
            "julian day",
        ],
    },
    {
        "match": "how_to_calculate_charts",
        "category": "chart_calculation",
        "priority": 8,
        "keywords": [
            "calculate",
            "formula",
            "chart",
            "ephemeris",
            "degree",
            "house",
            "aspect",
            "solar return",
            "transit",
        ],
    },
    {
        "match": "astrology_dataset",
        "category": "astrology_reference",
        "priority": 7,
        "keywords": [
            "astrology",
            "planet",
            "sign",
            "house",
            "aspect",
            "dignity",
            "transit",
            "synastry",
        ],
    },
    {
        "match": "great_minds_body_of_work",
        "category": "wisdom_reference",
        "priority": 5,
        "keywords": [
            "jung",
            "tesla",
            "einstein",
            "hermes",
            "ptolemy",
            "rudhyar",
            "sagan",
            "brady",
            "greene",
            "yogananda",
            "rumi",
            "mindfulness",
            "spirituality",
        ],
    },
    {
        "match": "great_minds_dataset",
        "category": "wisdom_reference",
        "priority": 4,
        "keywords": [
            "jung",
            "tesla",
            "einstein",
            "hermes",
            "ptolemy",
            "rudhyar",
            "spirituality",
        ],
    },
)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def source_profile(name: str) -> dict:
    source_slug = slug(name)
    for profile in SOURCE_PROFILES:
        if profile["match"] in source_slug:
            return profile
    return {
        "category": "astrology_reference",
        "priority": 5,
        "keywords": ["astrology", "reading", "interpretation"],
    }


def extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[Page {index}]\n{text.strip()}")
    return "\n\n".join(pages)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) <= 1:
        lines = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", block)
            if sentence.strip()
        ]
    parts: list[str] = []
    current: list[str] = []
    current_chars = 0
    for line in lines:
        if current and current_chars + len(line) + 1 > max_chars:
            parts.append("\n".join(current))
            current = []
            current_chars = 0
        if len(line) > max_chars:
            for start in range(0, len(line), max_chars):
                piece = line[start : start + max_chars].strip()
                if piece:
                    parts.append(piece)
            continue
        current.append(line)
        current_chars += len(line) + 1
    if current:
        parts.append("\n".join(current))
    return parts


def chunk_text(text: str, max_chars: int) -> list[str]:
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", normalize_text(text)):
        block = block.strip()
        if not block:
            continue
        blocks.extend(split_long_block(block, max_chars))

    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    for block in blocks:
        block_chars = len(block) + 2
        if current and current_chars + block_chars > max_chars:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_chars = 0
        current.append(block)
        current_chars += block_chars
    if current:
        chunks.append("\n\n".join(current).strip())
    return chunks


def real_archive_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [
        info
        for info in archive.infolist()
        if not info.is_dir()
        and "__MACOSX" not in info.filename
        and not Path(info.filename).name.startswith("._")
    ]


def build_corpus(input_zip: Path, output: Path, max_chars: int) -> dict:
    sources = []
    chunks = []
    with tempfile.TemporaryDirectory(prefix="astromeg-knowledge-") as temp_dir:
        temp_path = Path(temp_dir)
        with zipfile.ZipFile(input_zip) as archive:
            members = real_archive_members(archive)
            archive.extractall(temp_path, members=members)

        paths = sorted(path for path in temp_path.rglob("*") if path.is_file())
        for path in paths:
            suffix = path.suffix.casefold()
            if path.name.casefold() == "astromeg_oracle_prompt.md":
                continue
            if suffix == ".pdf":
                text = extract_pdf(path)
            elif suffix in {".md", ".txt"}:
                text = path.read_text(encoding="utf-8")
            else:
                continue

            text = normalize_text(text)
            profile = source_profile(path.stem)
            source_id = slug(path.stem)
            source_chunks = chunk_text(text, max_chars)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            sources.append(
                {
                    "id": source_id,
                    "name": path.name,
                    "category": profile["category"],
                    "priority": profile["priority"],
                    "sha256": digest,
                    "characters": len(text),
                    "chunks": len(source_chunks),
                }
            )
            for index, chunk in enumerate(source_chunks, start=1):
                chunks.append(
                    {
                        "id": f"{source_id}:{index}",
                        "source_id": source_id,
                        "category": profile["category"],
                        "priority": profile["priority"],
                        "keywords": profile["keywords"],
                        "text": chunk,
                    }
                )

    corpus = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_archive_sha256": hashlib.sha256(input_zip.read_bytes()).hexdigest(),
        "sources": sources,
        "chunks": chunks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(corpus, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return corpus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-chars", type=int, default=1800)
    args = parser.parse_args()

    corpus = build_corpus(args.input_zip, args.output, args.chunk_chars)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sources": len(corpus["sources"]),
                "chunks": len(corpus["chunks"]),
                "characters": sum(source["characters"] for source in corpus["sources"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
