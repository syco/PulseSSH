#!/usr/bin/env python

from gi.repository import GObject  # type: ignore

class HistoryItem(GObject.Object):
    def __init__(self, name: str, uuid: str):
        super().__init__()
        self.name = name
        self.uuid = uuid
        self.icon_name = "computer-symbolic"
