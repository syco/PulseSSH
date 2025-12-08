#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

import pulse_ssh.gui.Globals as _gui_globals

class ClusterManager:
    def __init__(self, app_window):
        self.app_window = app_window

    def join_cluster(self, terminal, cluster_id):
        self.leave_cluster(terminal)

        if cluster_id not in _gui_globals.active_clusters:
            _gui_globals.active_clusters[cluster_id] = []

        _gui_globals.active_clusters[cluster_id].append(terminal)
        terminal.pulse_cluster_id = cluster_id
        terminal.cluster_key_controller.connect("key-pressed", terminal.key_pressed_callback)
        terminal.add_controller(terminal.cluster_key_controller)

    def leave_cluster(self, terminal):
        if not hasattr(terminal, 'pulse_cluster_id') or terminal.pulse_cluster_id is None:
            return

        cluster_id = terminal.pulse_cluster_id
        if cluster_id in _gui_globals.active_clusters and terminal in _gui_globals.active_clusters[cluster_id]:
            _gui_globals.active_clusters[cluster_id].remove(terminal)
            terminal.cluster_key_controller.disconnect_by_func(terminal.key_pressed_callback)
            terminal.remove_controller(terminal.cluster_key_controller)
            if not _gui_globals.active_clusters[cluster_id]:
                del _gui_globals.active_clusters[cluster_id]

        terminal.pulse_cluster_id = None
