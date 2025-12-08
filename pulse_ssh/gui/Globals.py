#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from typing import Dict
from typing import List
import hashlib
import pulse_ssh.data.CacheConfig as _cache_config
import pulse_ssh.data.ClusterCache as _cluster_cache
import pulse_ssh.data.HistoryEntry as _history_entry
import pulse_ssh.gui.managers.ClusterManager as _cluster_manager
import pulse_ssh.gui.managers.LayoutManager as _layout_manager
import pulse_ssh.gui.managers.ShortcutManager as _shortcut_manager

active_clusters: Dict[str, _cluster_cache.ClusterCache] = {}
all_notebooks: List[Adw.TabView] = []
cache_config: _cache_config.CacheConfig
cluster_manager: _cluster_manager.ClusterManager
command_history: Dict[str, List[_history_entry.HistoryEntry]] = {}
layout_manager: _layout_manager.LayoutManager
shortcut_manager: _shortcut_manager.ShortcutManager

def ask_for_cluster_name(parent, callback):
    dialog = Adw.MessageDialog(
        transient_for=parent,
        modal=True,
        heading="New Cluster",
        body="Enter a name for the new cluster."
    )
    entry = Adw.EntryRow(title="Cluster Name", activates_default=True)
    dialog.set_extra_child(entry)

    dialog.add_response("cancel", "Cancel")
    dialog.add_response("create", "Create")
    dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("create")

    def on_response(d, response_id):
        if response_id == "create":
            cluster_name = entry.get_text().strip()
            cluster_id = hashlib.md5(cluster_name.encode('utf-8')).hexdigest()
            callback(cluster_id, cluster_name or f"Cluster ({cluster_id[:4]})")
        else:
            callback(None, None)

    dialog.connect("response", on_response)
    dialog.present()

def show_error_dialog(parent, title, message):
    dialog = Adw.MessageDialog(
        transient_for=parent,
        modal=True,
        heading=title,
        body=message
    )
    dialog.add_response("ok", "OK")
    dialog.set_default_response("ok")
    dialog.connect("response", lambda d, r: d.close())
    dialog.present()