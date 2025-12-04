#!/usr/bin/env python

from dataclasses import dataclass
from dataclasses import field
from typing import List
import uuid

@dataclass
class Cluster:
    name: str
    connection_uuids: List[str] = field(default_factory=list)
    open_mode: str = "split"
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
