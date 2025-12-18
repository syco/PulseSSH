#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Vte  # type: ignore
from typing import Optional
import os
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.VteTerminal as _vte_terminal

class VteTerminalLOCAL(_vte_terminal.VteTerminal):
    def __init__(self, app_window, connection: _connection.Connection, cluster_id: Optional[str] = None, cluster_name: Optional[str] = None, **kwargs):
        super().__init__(app_window, **kwargs)

        args  = [_globals.app_config.shell_program]

        self.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.environ['HOME'],
            args,
            [],
            GLib.SpawnFlags.SEARCH_PATH,
            None, None, -1, None, None, None
        )

        handler_id = [None]
        def on_prompt_detected(terminal):
            last_line = terminal.get_last_line()
            if last_line and last_line.rstrip().endswith(('$', '#', '>', '%')):
                if handler_id[0]:
                    terminal.disconnect(handler_id[0])
                    handler_id[0] = None
                terminal.grab_focus()
                self.app_window.connections_view.select_connection_from_terminal(terminal)

                return True
            return False

        handler_id[0] = self.connect("contents-changed", on_prompt_detected)

        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(Gdk.BUTTON_SECONDARY)
        click_gesture.connect("pressed", self.build_menu)
        self.add_controller(click_gesture)

        middle_click_gesture = Gtk.GestureClick()
        middle_click_gesture.set_button(Gdk.BUTTON_MIDDLE)
        middle_click_gesture.connect("pressed", self.on_middle_click_paste)
        self.add_controller(middle_click_gesture)

        self.connect("child-exited", self.on_terminal_child_exited)

        self.pulse_conn = connection
        self.pulse_cluster_id = cluster_id
        self.pulse_cluster_name = cluster_name

        self.connect_time = GLib.get_monotonic_time()
        self.cluster_key_controller = Gtk.EventControllerKey()

        if cluster_id and cluster_name:
            _gui_globals.cluster_manager.join_cluster(self, cluster_id, cluster_name)

        self.connected = True

    def build_menu(self, gesture, n_press, x, y):
        notebook, page = self.get_ancestor_page()
        if not notebook or not page:
            return

        menu_model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        self.insert_action_group("term", action_group)

        copy_action = Gio.SimpleAction.new("copy", None)
        copy_action.connect("activate", lambda a, p, t=self: t.copy_clipboard())
        copy_action.set_enabled(self.get_has_selection())
        action_group.add_action(copy_action)
        menu_model.append("Copy", "term.copy")

        paste_action = Gio.SimpleAction.new("paste", None)
        paste_action.connect("activate", lambda a, p, t=self: t.paste_clipboard())
        action_group.add_action(paste_action)
        menu_model.append("Paste", "term.paste")

        menu_model.append_section(None, Gio.Menu())

        split_h_submenu = self._create_split_submenu(action_group, Gtk.Orientation.HORIZONTAL, page)
        menu_model.append_submenu("Split Horizontal", split_h_submenu)

        split_v_submenu = self._create_split_submenu(action_group, Gtk.Orientation.VERTICAL, page)
        menu_model.append_submenu("Split Vertical", split_v_submenu)

        cluster_submenu = self._create_cluster_submenu(self, action_group)
        menu_model.append_submenu("Cluster", cluster_submenu)

        page_cluster_submenu = self._create_page_cluster_submenu(self, action_group)
        menu_model.append_submenu("Page Cluster", page_cluster_submenu)

        menu_model.append_section(None, Gio.Menu())

        rename_action = Gio.SimpleAction.new("rename_tab", None)
        rename_action.connect("activate", self.app_window._rename_tab, self, page)
        action_group.add_action(rename_action)
        menu_model.append("Rename Tab", "term.rename_tab")

        if notebook == _gui_globals.all_notebooks[0]:
            detatch_action = Gio.SimpleAction.new("detatch", None)
            detatch_action.connect("activate", _gui_globals.layout_manager.detatch_terminal, self)
            action_group.add_action(detatch_action)
            menu_model.append("Detatch to New Window", "term.detatch")
        else:
            attach_action = Gio.SimpleAction.new("attach", None)
            attach_action.connect("activate", _gui_globals.layout_manager.attach_terminal, self)
            action_group.add_action(attach_action)
            menu_model.append("Attach to Main Window", "term.attach")

        parent = self.get_parent().get_parent()
        if isinstance(parent, Gtk.Paned):
            unsplit_action = Gio.SimpleAction.new("unsplit", None)
            unsplit_action.connect("activate", _gui_globals.layout_manager.unsplit_terminal, self)
            action_group.add_action(unsplit_action)
            menu_model.append("Move to New Tab", "term.unsplit")

        close_action = Gio.SimpleAction.new("close", None)
        close_action.connect("activate", _gui_globals.layout_manager.close_terminal, self)
        action_group.add_action(close_action)
        menu_model.append("Close", "term.close")

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(self)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()