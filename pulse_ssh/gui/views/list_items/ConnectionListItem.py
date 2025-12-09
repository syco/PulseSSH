#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Gio  # type: ignore
from gi.repository import GObject  # type: ignore
from typing import Optional

class ConnectionListItem(GObject.Object):
    __gtype_name__ = 'ConnectionListItem'

    @GObject.Property(type=str)
    def sort_key(self):
        return self._sort_key

    def __init__(self, name, parent_store: Gio.ListStore, conn_uuid: Optional[str] = None):
        super().__init__()
        self.name = name
        self.parent_store = parent_store
        self.is_folder = False if conn_uuid else True
        self.conn_uuid = conn_uuid
        self.children_store = None if conn_uuid else Gio.ListStore.new(ConnectionListItem)
        self.icon_name = ("utilities-terminal-symbolic" if conn_uuid else "folder-symbolic")
        self._sort_key = f"{'0' if self.conn_uuid else '1'}-{self.name.lower()}"
