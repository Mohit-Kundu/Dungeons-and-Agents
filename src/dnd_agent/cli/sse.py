"""Parse Server-Sent Events from the Turn stream."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any


def iter_sse_data(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Yield JSON payloads from SSE `data:` frames."""
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
        elif line == "" and data_lines:
            yield json.loads("\n".join(data_lines))
            data_lines = []
    if data_lines:
        yield json.loads("\n".join(data_lines))
