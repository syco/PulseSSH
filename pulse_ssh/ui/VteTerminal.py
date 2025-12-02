#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Pango  # type: ignore
from gi.repository import Vte  # type: ignore
from typing import Optional
from typing import TYPE_CHECKING
import os
import pulse_ssh.Utils as utils
import pulse_ssh.data.Connection as connection

if TYPE_CHECKING:
    from pulse_ssh.ui.MainWindow import MainWindow

class VteTerminal(Vte.Terminal):
    def __init__(self, app_window: "MainWindow", connection: connection.Connection, cluster_id: Optional[str] = None):
        super().__init__()
        self.app_window = app_window

        self.set_vexpand(True)
        self.set_scrollback_lines(self.app_window.app_config.scrollback_lines)
        self.set_scroll_on_output(self.app_window.app_config.scroll_on_output)
        self.set_scroll_on_keystroke(self.app_window.app_config.scroll_on_keystroke)
        self.set_scroll_on_insert(self.app_window.app_config.scroll_on_insert)

        self.apply_theme()

        self.set_margin_top(1)
        self.set_margin_bottom(1)
        self.set_margin_start(1)
        self.set_margin_end(1)

        if connection.type == "local":
            self.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                [self.app_window.app_config.shell_program],
                [],
                GLib.SpawnFlags.SEARCH_PATH,
                None, None, -1, None, None, None
            )

            self._wait_for_prompt_and_focus()
        elif connection.type == "ssh":
            final_cmd, all_remote_scripts, remote_script_paths, proxy_port = utils.build_ssh_command(self.app_window.app_config, connection)

            self.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                [self.app_window.app_config.shell_program, "-c", final_cmd],
                [],
                GLib.SpawnFlags.SEARCH_PATH,
                None, None, -1, None, None, None
            )

            all_post_remote_cmds = self.app_window.app_config.post_remote_cmds + connection.post_remote_cmds

            self._wait_for_prompt_and_focus(all_post_remote_cmds, all_remote_scripts, remote_script_paths, proxy_port, connection)
        elif connection.type == "sftp":
            final_cmd = utils.build_sftp_command(self.app_window.app_config, connection)

            self.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                [self.app_window.app_config.shell_program, "-c", final_cmd],
                [],
                GLib.SpawnFlags.SEARCH_PATH,
                None, None, -1, None, None, None
            )

            self._wait_for_prompt_and_focus()

        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(Gdk.BUTTON_SECONDARY)
        click_gesture.connect("pressed", self.build_menu)
        self.add_controller(click_gesture)

        middle_click_gesture = Gtk.GestureClick()
        middle_click_gesture.set_button(Gdk.BUTTON_MIDDLE)
        middle_click_gesture.connect("pressed", self.on_middle_click_paste)
        self.add_controller(middle_click_gesture)

        self.connect("child-exited", self.app_window.on_terminal_child_exited, connection)

        self.pulse_conn = connection
        self.pulse_cluster_id = cluster_id

        self.connect_time = GLib.get_monotonic_time()
        self.cluster_key_controller = Gtk.EventControllerKey()

        if cluster_id:
            self.app_window._join_cluster(self, cluster_id)

        self.connected = True

    def _wait_for_prompt_and_focus(self, all_post_remote_cmds=None, all_remote_scripts=None, remote_script_paths=None, proxy_port=None, connection=None):
        handler_id = [None]

        def on_prompt_detected(terminal):
            text = terminal.get_text_format(Vte.Format.TEXT)
            if text and text.rstrip().endswith(('$', '#', '>', '%')):
                if handler_id[0]:
                    terminal.disconnect(handler_id[0])
                    handler_id[0] = None

                if all_post_remote_cmds or all_remote_scripts:
                    commands_to_run = []

                    if remote_script_paths:
                        for remote_path in remote_script_paths:
                            commands_to_run.append(f" chmod +x {remote_path}")
                            commands_to_run.append(f" {remote_path}")
                            commands_to_run.append(f" rm {remote_path}")

                    if all_post_remote_cmds and connection:
                        commands_to_run.extend([utils.substitute_variables(cmd, connection, proxy_port) for cmd in all_post_remote_cmds])

                    if commands_to_run:
                        full_command = "\n".join(commands_to_run) + "\n"
                        terminal.feed_child(full_command.encode('utf-8'))

                terminal.grab_focus()
                return True
            return False

        handler_id[0] = self.connect("contents-changed", on_prompt_detected)

    def _create_split_submenu(self, action_group, orientation, source_page):
        submenu = Gio.Menu()

        source_page_idx = self.app_window.notebook.get_page_position(source_page)

        action_name = f"split_new_{'h' if orientation == Gtk.Orientation.HORIZONTAL else 'v'}"
        split_new_action = Gio.SimpleAction.new(action_name, None)
        split_new_action.connect("activate", self.app_window.split_terminal_or_tab, self, source_page, source_page_idx, orientation, None, -1)
        action_group.add_action(split_new_action)
        submenu.append("New Terminal (Same Host)", f"term.{action_name}")
        submenu.append_section(None, Gio.Menu())

        for target_page_idx in range(self.app_window.notebook.get_n_pages()):
            if target_page_idx == source_page_idx: continue
            target_page = self.app_window.notebook.get_nth_page(target_page_idx)
            if target_page == source_page: continue
            label_text = target_page.get_title()

            action_name = f"split_tab_{target_page_idx}_{'h' if orientation == Gtk.Orientation.HORIZONTAL else 'v'}"
            split_tab_action = Gio.SimpleAction.new(action_name, None)
            split_tab_action.connect("activate", self.app_window.split_terminal_or_tab, self, source_page, source_page_idx, orientation, target_page, target_page_idx)
            action_group.add_action(split_tab_action)
            submenu.append(f"Tab: {label_text}", f"term.{action_name}")

        return submenu

    def build_menu(self, gesture, n_press, x, y):
        source_page = self.get_ancestor_page()
        if not source_page:
            self.app_window.show_error_dialog(
                "Internal UI Error",
                "Could not find the parent tab for the disconnected terminal. The tab's status indicator may not update correctly."
            )
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

        if self.pulse_conn and self.pulse_conn.type == "ssh":
            menu_model.append_section(None, Gio.Menu())
            sftp_action = Gio.SimpleAction.new("sftp", None)
            sftp_action.connect("activate", self.open_sftp_tab)
            action_group.add_action(sftp_action)
            menu_model.append("Open SFTP", "term.sftp")

        menu_model.append_section(None, Gio.Menu())

        split_h_submenu = self._create_split_submenu(action_group, Gtk.Orientation.HORIZONTAL, source_page)
        menu_model.append_submenu("Split Horizontal", split_h_submenu)

        split_v_submenu = self._create_split_submenu(action_group, Gtk.Orientation.VERTICAL, source_page)
        menu_model.append_submenu("Split Vertical", split_v_submenu)

        parent = self.get_parent().get_parent()
        if isinstance(parent, Gtk.Paned):
            unsplit_action = Gio.SimpleAction.new("unsplit", None)
            unsplit_action.connect("activate", self.app_window.unsplit_terminal, self, source_page)
            action_group.add_action(unsplit_action)
            menu_model.append("Move to tab", "term.unsplit")

        cluster_submenu = self.app_window._create_cluster_submenu(self, action_group)
        menu_model.append_submenu("Cluster", cluster_submenu)

        menu_model.append_section(None, Gio.Menu())

        local_scripts_submenu = self.app_window._create_local_scripts_submenu(self, action_group)
        menu_model.append_submenu("Local Scripts", local_scripts_submenu)

        menu_model.append_section(None, Gio.Menu())

        rename_action = Gio.SimpleAction.new("rename_tab", None)
        rename_action.connect("activate", self.app_window._rename_tab, self, source_page)
        action_group.add_action(rename_action)
        menu_model.append("Rename Tab", "term.rename_tab")

        menu_model.append_section(None, Gio.Menu())

        close_action = Gio.SimpleAction.new("close", None)
        close_action.connect("activate", self.app_window.close_terminal, self, source_page)
        action_group.add_action(close_action)
        menu_model.append("Close", "term.close")

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(self)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def paste_clipboard(self):
        if self.pulse_cluster_id and self.pulse_cluster_id in self.app_window.active_clusters:
            for terminal in self.app_window.active_clusters[self.pulse_cluster_id]:
                super(VteTerminal, terminal).paste_clipboard()
        else:
            super().paste_clipboard()

    def on_middle_click_paste(self, gesture, n_press, x, y):
        self.paste_primary()

    def paste_primary(self):
        if self.pulse_cluster_id and self.pulse_cluster_id in self.app_window.active_clusters:
            for terminal in self.app_window.active_clusters[self.pulse_cluster_id]:
                if terminal != self:
                    super(VteTerminal, terminal).paste_primary()
        else:
            super().paste_primary()

    def open_sftp_tab(self, action, param):
        clone = self.pulse_conn.get_cloned_connection()
        clone.type = "sftp"

        self.app_window.open_connection_tab(clone)

    def key_pressed_callback(self, controller, keyval, keycode, state):
        if not hasattr(self, 'pulse_cluster_id') or self.pulse_cluster_id is None:
            return False

        cluster_id = self.pulse_cluster_id
        if cluster_id not in self.app_window.active_clusters:
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
            for t in self.app_window.active_clusters[cluster_id]:
                t.feed_child(key_bytes)
            return True

        return False

    def apply_theme(self):
        self.set_audible_bell(self.app_window.app_config.audible_bell)

        font_desc = Pango.FontDescription.from_string(f"{self.app_window.app_config.font_family} {self.app_window.app_config.font_size}")
        self.set_font(font_desc)

        cursor_shape_map = {
            "block": Vte.CursorShape.BLOCK,
            "ibeam": Vte.CursorShape.IBEAM,
            "underline": Vte.CursorShape.UNDERLINE,
        }
        self.set_cursor_shape(cursor_shape_map.get(self.app_window.app_config.cursor_shape, Vte.CursorShape.BLOCK))

        def hex_to_rgba(hex_color):
            rgba = Gdk.RGBA()
            rgba.parse(hex_color)
            return rgba

        themes = utils.load_themes()

        theme_name = self.app_window.app_config.theme

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

    def get_ancestor_page(self) -> Optional[Adw.TabPage]:
        widget = self
        while parent := widget.get_parent():
            if isinstance(parent.get_parent().get_parent(), Adw.TabView):
                return self.app_window.notebook.get_page(parent)
            widget = parent
        return None
