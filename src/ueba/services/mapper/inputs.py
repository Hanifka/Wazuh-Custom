from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, Optional


class AlertInputSource:
    def __iter__(self) -> Iterator[Dict]:  # pragma: no cover - interface
        raise NotImplementedError


class StdInSource(AlertInputSource):
    def __iter__(self) -> Iterator[Dict]:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


class FileTailSource(AlertInputSource):
    def __init__(self, path: Path, follow: bool = False, poll_interval: float = 0.5) -> None:
        self.path = path
        self.follow = follow
        self.poll_interval = poll_interval

    def __iter__(self) -> Iterator[Dict]:
        with self.path.open("r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if not line:
                    if not self.follow:
                        break
                    time.sleep(self.poll_interval)
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


class MessageQueueStubSource(AlertInputSource):
    def __init__(self, messages: Optional[list]) -> None:
        self.messages = messages or []

    def __iter__(self) -> Iterator[Dict]:
        for msg in self.messages:
            if isinstance(msg, dict):
                yield msg
            else:
                try:
                    yield json.loads(msg)
                except json.JSONDecodeError:
                    continue
