#!/usr/bin/env python

from dataclasses import dataclass
from datetime import datetime

@dataclass
class HistoryEntry:
    command: str
    stdout: str
    stderr: str
    ok: bool
    timestamp: datetime
