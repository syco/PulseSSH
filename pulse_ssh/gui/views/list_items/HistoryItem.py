#!/usr/bin/env python

from gi.repository import GObject  # type: ignore

class HistoryItem(GObject.Object):
    __gtype_name__ = 'HistoryItem'

    name = GObject.Property(type=str)

    def __init__(self, name: str, uuid: str):
        super().__init__()
        self.name = name
        self.uuid = uuid
        self.icon_name = "computer-symbolic"

    def get_name(self):
        return self.get_property('name')
