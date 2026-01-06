from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

_TOKEN_START = "{{MPP_MUTABLE:"
_TOKEN_END = "{{/MPP_MUTABLE}}"


@dataclass(frozen=True)
class MutableBlock:
    name: str
    content: str
    start: int
    end: int


def _parse_blocks(template: str) -> list[MutableBlock]:
    blocks: list[MutableBlock] = []
    pos = 0
    while True:
        start = template.find(_TOKEN_START, pos)
        if start == -1:
            break
        name_start = start + len(_TOKEN_START)
        name_end = template.find("}}", name_start)
        if name_end == -1:
            raise ValueError("Unclosed MPP_MUTABLE start token.")
        name = template[name_start:name_end].strip()
        if not name:
            raise ValueError("MPP_MUTABLE block name cannot be empty.")
        end = template.find(_TOKEN_END, name_end + 2)
        if end == -1:
            raise ValueError(f"Missing {_TOKEN_END} for block {name}.")
        content = template[name_end + 2 : end]
        blocks.append(
            MutableBlock(
                name=name,
                content=content,
                start=start,
                end=end + len(_TOKEN_END),
            )
        )
        pos = end + len(_TOKEN_END)
    return blocks


def list_mutable_blocks(template: str) -> list[str]:
    return [block.name for block in _parse_blocks(template)]


def extract_mutable_blocks(template: str) -> dict[str, str]:
    blocks = _parse_blocks(template)
    return {block.name: block.content for block in blocks}


def render_mutable_template(template: str, replacements: Mapping[str, str]) -> str:
    blocks = _parse_blocks(template)
    if not blocks:
        return template
    result = []
    pos = 0
    for block in blocks:
        result.append(template[pos : block.start])
        replacement = replacements.get(block.name, block.content)
        result.append(replacement)
        pos = block.end
    result.append(template[pos:])
    return "".join(result)
