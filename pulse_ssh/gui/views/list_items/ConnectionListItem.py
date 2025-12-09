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
    def __init__(self, name, conn_uuid: Optional[str] = None):
        super().__init__()
        self.name = name
        self.conn_uuid = conn_uuid
        self.children_store = None if conn_uuid else Gio.ListStore.new(ConnectionListItem)
        self.icon_name = ("utilities-terminal-symbolic" if conn_uuid else "folder-symbolic")
