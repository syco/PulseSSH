#!/usr/bin/env python

from datetime import datetime
from gi.repository import Gio  # type: ignore
from gi.repository import GObject  # type: ignore
from typing import Optional
import uuid

class CommandHistoryItem(GObject.Object):
    def __init__(self, command: str, stdout: str, stderr: str, ok: bool, children_store: Optional[Gio.ListStore] = None):
        super().__init__()
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.ok = ok
        self.children_store = children_store
        self.timestamp = datetime.now()
        self.uuid = str(uuid.uuid4())
