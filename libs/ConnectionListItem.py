#!/usr/bin/env python

import gi

from gi.repository import Gio  # type: ignore
from gi.repository import GObject  # type: ignore
from typing import Optional

class ConnectionListItem(GObject.Object):
    def __init__(self, name, connection_data=None, children_store: Optional[Gio.ListStore] = None, path: Optional[str] = None):
        super().__init__()
        self.name = name
        self.icon_name = ("utilities-terminal-symbolic" if connection_data else "folder-symbolic")
        self.children_store = children_store
        self.connection_data = connection_data
        self.path = path
