#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from datetime import datetime
from gi.repository import Adw  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Pango  # type: ignore
from gi.repository import Vte  # type: ignore
from typing import Optional
import pulse_ssh.data.HistoryEntry as _history_entry
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.Utils as _utils

class VteTerminal(Vte.Terminal):
    def __init__(self, app_window, **kwargs):
        super().__init__()
        self.app_window = app_window

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_scrollback_lines(_globals.app_config.scrollback_lines)
        self.set_scroll_on_output(_globals.app_config.scroll_on_output)
        self.set_scroll_on_keystroke(_globals.app_config.scroll_on_keystroke)
        self.set_scroll_on_insert(_globals.app_config.scroll_on_insert)

        self.apply_theme()

        self.set_margin_top(1)
        self.set_margin_bottom(1)
        self.set_margin_start(1)
        self.set_margin_end(1)

    def add_toast(self, toast: Adw.Toast):
        ancestor = self.get_ancestor(Gtk.ApplicationWindow)
        if ancestor and ancestor.toast_overlay:
            ancestor.toast_overlay.add_toast(toast)

    def add_history_item(self, conn_uuid: str, substituted_cmd: str, stdout: str, stderr: str, ok: bool):
        history_item = _history_entry.HistoryEntry(substituted_cmd, stdout, stderr, ok, datetime.now())

        if conn_uuid not in _gui_globals.command_history:
            _gui_globals.command_history[conn_uuid] = []
        _gui_globals.command_history[conn_uuid].append(history_item)
        self.app_window.history_view.populate_tree()
        self.add_toast(Adw.Toast.new(GLib.markup_escape_text(f"'{substituted_cmd}' finished!")))

    def on_terminal_child_exited(self, terminal, exit_code):
        self.connected = False

        notebook, page = self.get_ancestor_page()
        if not notebook or not page:
            return

        self.app_window.updatePageTitle(page)

        behavior = _globals.app_config.on_disconnect_behavior

        timestamp = GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S")

        connection = self.pulse_conn
        cluster_id = self.pulse_cluster_id
        cluster_name = self.pulse_cluster_name

        def wait_for_key_behavior():
            message = (
                f"\r\n"
                f"\r\n{_utils.color_iyellow} --- SSH connection closed at {timestamp}.{_utils.color_reset}"
                f"\r\n{_utils.color_iyellow} --- Press Enter to restart.{_utils.color_reset}"
                f"\r\n{_utils.color_iyellow} --- Press Esc to close terminal.{_utils.color_reset}"
                f"\r\n"
            )
            self.feed(message.encode('utf-8'))

            evk = Gtk.EventControllerKey()
            def on_key_pressed(controller, keyval, keycode, state):
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    self.remove_controller(evk)
                    _gui_globals.layout_manager.replace_terminal(self, _gui_globals.layout_manager.create_terminal(connection, cluster_id, cluster_name))
                    return True
                if keyval == Gdk.KEY_Escape:
                    self.remove_controller(evk)
                    _gui_globals.layout_manager.close_terminal(None, None, self)
                    return True
                return False
            evk.connect("key-pressed", on_key_pressed)
            self.add_controller(evk)

        if behavior == "close":
            _gui_globals.layout_manager.close_terminal(None, None, self)
        elif behavior == "restart":
            connect_duration = GLib.get_monotonic_time() - self.connect_time
            if connect_duration < 5 * 1_000_000:
                self.add_toast(Adw.Toast.new(GLib.markup_escape_text(f"Restart loop detected for '{connection.name}'. Pausing auto-restart.")))
                wait_for_key_behavior()
            else:
                _gui_globals.layout_manager.replace_terminal(self, _gui_globals.layout_manager.create_terminal(connection, cluster_id, cluster_name))
        elif behavior == "wait_for_key":
            wait_for_key_behavior()

    def _create_split_submenu(self, action_group, orientation, source_page):
        submenu = Gio.Menu()

        action_name = f"split_new_{'h' if orientation == Gtk.Orientation.HORIZONTAL else 'v'}"
        split_new_action = Gio.SimpleAction.new(action_name, None)
        split_new_action.connect("activate", _gui_globals.layout_manager.split_terminal_or_tab, self, source_page, orientation, None, None)
        action_group.add_action(split_new_action)
        submenu.append("New Terminal (Same Host)", f"term.{action_name}")
        submenu.append_section(None, Gio.Menu())

        for target_notebook in _gui_globals.all_notebooks:
            for target_page_idx in range(target_notebook.get_n_pages()):
                target_page = target_notebook.get_nth_page(target_page_idx)
                if target_page == source_page: continue
                label_text = target_page.get_title()

                action_name = f"split_tab_{target_page_idx}_{'h' if orientation == Gtk.Orientation.HORIZONTAL else 'v'}"
                split_tab_action = Gio.SimpleAction.new(action_name, None)
                split_tab_action.connect("activate", _gui_globals.layout_manager.split_terminal_or_tab, self, source_page, orientation, target_page, target_notebook)
                action_group.add_action(split_tab_action)
                submenu.append(f"Tab: {label_text}", f"term.{action_name}")

        return submenu

    def _create_new_cluster(self, terminal):
        def on_name_received(cluster_id, cluster_name):
            if cluster_id and cluster_name:
                _gui_globals.cluster_manager.join_cluster(terminal, cluster_id, cluster_name)

        _gui_globals.ask_for_cluster_name(self.get_ancestor(Gtk.ApplicationWindow), on_name_received)

    def _create_new_page_cluster(self, terminal):
        def on_name_received(cluster_id, cluster_name):
            if cluster_id and cluster_name:
                notebook, page = terminal.get_ancestor_page()
                if not notebook or not page:
                    return
                terminals = self.app_window._find_all_terminals_in_widget(page)
                for t in terminals:
                    _gui_globals.cluster_manager.join_cluster(t, cluster_id, cluster_name)

        _gui_globals.ask_for_cluster_name(self.get_ancestor(Gtk.ApplicationWindow), on_name_received)

    def _create_cluster_submenu(self, terminal, action_group):
        submenu = Gio.Menu()

        create_action = Gio.SimpleAction.new("create_new_cluster", None)
        create_action.connect("activate", lambda a, p, t=terminal: self._create_new_cluster(t))
        action_group.add_action(create_action)
        submenu.append("Create New Cluster", "term.create_new_cluster")

        if _gui_globals.active_clusters:
            submenu.append_section(None, Gio.Menu())
            join_menu = Gio.Menu()
            for cluster_id, cluster in _gui_globals.active_clusters.items():
                join_action = Gio.SimpleAction.new(f"join_cluster_{cluster_id}", None)
                join_action.connect("activate", lambda a, p, t=terminal, cid=cluster_id, cna=cluster.name: _gui_globals.cluster_manager.join_cluster(t, cid, cna))
                action_group.add_action(join_action)
                join_menu.append(cluster.name, f"term.join_cluster_{cluster_id}")
            submenu.append_submenu("Join Existing Cluster", join_menu)

        if terminal.pulse_cluster_id:
            submenu.append_section(None, Gio.Menu())
            leave_action = Gio.SimpleAction.new("leave_cluster", None)
            leave_action.connect("activate", lambda a, p, t=terminal: _gui_globals.cluster_manager.leave_cluster(t))
            action_group.add_action(leave_action)
            submenu.append("Leave Cluster", "term.leave_cluster")

        return submenu

    def _create_page_cluster_submenu(self, terminal, action_group):
        submenu = Gio.Menu()

        create_action = Gio.SimpleAction.new("create_new_page_cluster", None)
        create_action.connect("activate", lambda a, p, t=terminal: self._create_new_page_cluster(t))
        action_group.add_action(create_action)
        submenu.append("Create New Cluster", "term.create_new_page_cluster")

        if _gui_globals.active_clusters:
            submenu.append_section(None, Gio.Menu())
            join_menu = Gio.Menu()
            for cluster_id, cluster in _gui_globals.active_clusters.items():
                join_action = Gio.SimpleAction.new(f"join_page_cluster_{cluster_id}", None)
                join_action.connect("activate", lambda a, p, t=terminal, cid=cluster_id, cna=cluster.name: _gui_globals.cluster_manager.join_page_cluster(t, cid, cna))
                action_group.add_action(join_action)
                join_menu.append(cluster.name, f"term.join_page_cluster_{cluster_id}")
            submenu.append_submenu("Join Existing Cluster", join_menu)

        if terminal.pulse_cluster_id:
            submenu.append_section(None, Gio.Menu())
            leave_action = Gio.SimpleAction.new("leave_page_cluster", None)
            leave_action.connect("activate", lambda a, p, t=terminal: _gui_globals.cluster_manager.leave_page_cluster(t))
            action_group.add_action(leave_action)
            submenu.append("Leave Cluster", "term.leave_page_cluster")

        return submenu

    def paste_clipboard(self):
        if self.pulse_cluster_id and self.pulse_cluster_id in _gui_globals.active_clusters:
            for terminal in _gui_globals.active_clusters[self.pulse_cluster_id].terminals:
                if terminal != self:
                    super(VteTerminal, terminal).paste_clipboard()
        super().paste_clipboard()

    def on_middle_click_paste(self, gesture, n_press, x, y):
        self.paste_primary()

    def paste_primary(self):
        if self.pulse_cluster_id and self.pulse_cluster_id in _gui_globals.active_clusters:
            for terminal in _gui_globals.active_clusters[self.pulse_cluster_id].terminals:
                if terminal != self:
                    super(VteTerminal, terminal).paste_primary()

    def key_pressed_callback(self, controller, keyval, keycode, state):
        if not hasattr(self, 'pulse_cluster_id') or self.pulse_cluster_id is None:
            return False

        cluster_id = self.pulse_cluster_id
        if cluster_id not in _gui_globals.active_clusters:
            self.remove_controller(controller)
            self.pulse_cluster_id = None
            return False

        key_bytes = b''
        unichar = Gdk.keyval_to_unicode(keyval)
        is_ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if not is_ctrl and unichar > 0 and GLib.unichar_isprint(chr(unichar)):
             key_bytes = chr(unichar).encode('utf-8')
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            key_bytes = b'\r'
        elif keyval == Gdk.KEY_BackSpace:
            key_bytes = b'\x08'
        elif keyval == Gdk.KEY_Tab or keyval == Gdk.KEY_ISO_Left_Tab:
            key_bytes = b'\t'
        elif keyval == Gdk.KEY_Escape:
            key_bytes = b'\x1b'
        elif keyval == Gdk.KEY_Up:
            key_bytes = b'\x1b[A'
        elif keyval == Gdk.KEY_Down:
            key_bytes = b'\x1b[B'
        elif keyval == Gdk.KEY_Right:
            key_bytes = b'\x1b[C'
        elif keyval == Gdk.KEY_Left:
            key_bytes = b'\x1b[D'
        elif is_ctrl and Gdk.KEY_a <= keyval <= Gdk.KEY_z:
            key_bytes = bytes([keyval - Gdk.KEY_a + 1])

        if key_bytes:
            for t in _gui_globals.active_clusters[cluster_id].terminals:
                if t != self:
                    t.feed_child(key_bytes)
            return False

        return False

    def apply_theme(self):
        self.set_audible_bell(_globals.app_config.audible_bell)

        font_desc = Pango.FontDescription.from_string(f"{_globals.app_config.font_family} {_globals.app_config.font_size}")
        self.set_font(font_desc)

        cursor_shape_map = {
            "block": Vte.CursorShape.BLOCK,
            "ibeam": Vte.CursorShape.IBEAM,
            "underline": Vte.CursorShape.UNDERLINE,
        }
        self.set_cursor_shape(cursor_shape_map.get(_globals.app_config.cursor_shape, Vte.CursorShape.BLOCK))

        def hex_to_rgba(hex_color):
            rgba = Gdk.RGBA()
            rgba.parse(hex_color)
            return rgba

        themes = _utils.load_themes()

        theme_name = _globals.app_config.theme

        theme_data = themes.get(theme_name)

        if theme_data:
            fg = hex_to_rgba(theme_data.get("foreground"))
            bg = hex_to_rgba(theme_data.get("background"))
            palette = [hex_to_rgba(theme_data.get(f"color_{i:02d}")) for i in range(1, 17)]

            if fg and bg and palette:
                self.set_colors(fg, bg, palette)

            cursor = hex_to_rgba(theme_data.get("cursor"))
            if cursor:
                self.set_color_cursor(cursor)

    def get_ancestor_page(self) -> tuple[Optional[Adw.TabView], Optional[Adw.TabPage]]:
        widget = self
        while parent := widget.get_parent():
            if isinstance(parent.get_parent().get_parent(), Adw.TabView):
                notebook = parent.get_parent().get_parent()
                return notebook, notebook.get_page(parent)
            widget = parent
        return None, None

    def get_last_line(self) -> str:
        col, row = self.get_cursor_position()
        line, _ = self.get_text_range_format(Vte.Format.TEXT, (row - 1 if col == 0 else row), 0, row, col)
        return line.strip()
