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
import json
import os
import pulse_ssh.Utils as utils
import pulse_ssh.data.Connection as connection

if TYPE_CHECKING:
    from pulse_ssh.gui.MainWindow import MainWindow

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

        self.subbed_orchestrator_script_path = ""
        self.proxy_port: Optional[int] = None
        self.orchestrator_process: Optional[Gio.Subprocess] = None

        args = None

        if connection.type == "local":
            args  = [self.app_window.app_config.shell_program]

        elif connection.type == "ssh":
            final_cmd, self.proxy_port = utils.build_ssh_command(self.app_window.app_config, connection)
            args = [self.app_window.app_config.shell_program, "-c", final_cmd]

        elif connection.type == "sftp":
            final_cmd = utils.build_sftp_command(self.app_window.app_config, connection)
            args = [self.app_window.app_config.shell_program, "-c", final_cmd]

        if args:
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

                    if connection.type == "ssh":
                        self.start_orchestrator_script()

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

        self.connect("child-exited", self.app_window.on_terminal_child_exited)

        self.pulse_conn = connection
        self.pulse_cluster_id = cluster_id

        self.connect_time = GLib.get_monotonic_time()
        self.cluster_key_controller = Gtk.EventControllerKey()

        if cluster_id:
            self.app_window._join_cluster(self, cluster_id)

        self.connected = True

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

        local_cmds_submenu = self.create_local_cmds_submenu(action_group)
        menu_model.append_submenu("Local Commands", local_cmds_submenu)

        remote_cmds_submenu = self.create_remote_cmds_submenu(action_group)
        menu_model.append_submenu("Remote Commands", remote_cmds_submenu)

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

    def create_local_cmds_submenu(self, action_group):
        submenu = Gio.Menu()
        all_local_cmds = {**self.app_window.app_config.local_cmds, **self.pulse_conn.local_cmds}

        if not all_local_cmds:
            no_scripts_item = Gio.MenuItem.new("No scripts defined", None)
            no_scripts_item.set_action_and_target_value("term.no_scripts", GLib.Variant.new_string(""))
            no_scripts_action = Gio.SimpleAction.new("no_scripts", None)
            no_scripts_action.set_enabled(False)
            action_group.add_action(no_scripts_action)
            return submenu

        for i, (name, command) in enumerate(all_local_cmds.items()):
            action_name = f"run_local_cmd_{i}"
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", self.run_local_cmd, command)
            action_group.add_action(action)
            submenu.append(name, f"term.{action_name}")
        return submenu

    def create_remote_cmds_submenu(self, action_group):
        submenu = Gio.Menu()
        all_remote_cmds = {**self.app_window.app_config.remote_cmds, **self.pulse_conn.remote_cmds}

        if not all_remote_cmds:
            no_scripts_item = Gio.MenuItem.new("No scripts defined", None)
            no_scripts_item.set_action_and_target_value("term.no_scripts", GLib.Variant.new_string(""))
            no_scripts_action = Gio.SimpleAction.new("no_scripts", None)
            no_scripts_action.set_enabled(False)
            action_group.add_action(no_scripts_action)
            return submenu

        for i, (name, command) in enumerate(all_remote_cmds.items()):
            action_name = f"run_remote_cmd_{i}"
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", self.run_remote_cmd, command)
            action_group.add_action(action)
            submenu.append(name, f"term.{action_name}")
        return submenu

    def run_local_cmd(self, action, param, cmd):
        substituted_cmd = utils.substitute_variables(cmd, self.pulse_conn)
        def on_finished(subprocess, result, cmd, conn_uuid):
            try:
                ok, stdout, stderr = subprocess.communicate_utf8_finish(result)
                self.app_window.add_history_item(self.pulse_conn.uuid, substituted_cmd, stdout, stderr, ok)
            except GLib.Error as e:
                self.app_window.add_history_item(self.pulse_conn.uuid, substituted_cmd, "", e.message, False)

        try:
            subprocess = Gio.Subprocess.new([self.app_window.app_config.shell_program, '-c', substituted_cmd], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            subprocess.communicate_utf8_async(None, None, on_finished, substituted_cmd, self.pulse_conn.uuid)
        except GLib.Error as e:
            self.app_window.add_history_item(self.pulse_conn.uuid, substituted_cmd, "", e.message, False)

    def run_remote_cmd(self, action, param, cmd):
        substituted_cmd = utils.substitute_variables(cmd, self.pulse_conn)
        self.feed_child(f"{substituted_cmd}\n".encode('utf-8'))

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

    def get_last_line(self) -> str:
        col, row = self.get_cursor_position()
        line, _ = self.get_text_range_format(Vte.Format.TEXT, row, 0, row, col)

        return line.rstrip()

    def start_orchestrator_script(self):
        def on_line_received(data_stream: Gio.DataInputStream, result, is_command: bool = True):
            if not self.orchestrator_process:
                try:
                    data_stream.read_line_finish(result)
                    data_stream.close_async(GLib.PRIORITY_DEFAULT, None, None, None)
                except GLib.Error as e:
                    self.app_window.add_history_item(self.pulse_conn.uuid, self.subbed_orchestrator_script_path, "", e.message, False)
                return

            try:
                line_bytes, _ = data_stream.read_line_finish(result)
                if line_bytes:
                    command_str = line_bytes.decode('utf-8').rstrip()
                    if command_str:
                        if is_command:
                            try:
                                msg = json.loads(command_str)
                                action = msg.get('action')
                                if action == 'feed-child':
                                    data = msg.get('data', '')
                                    if data:
                                        self.feed_child(f"{data}\n".encode('utf-8'))
                                elif action == 'feed':
                                    data = msg.get('data', '')
                                    if data:
                                        self.feed(f"\r\n {utils.color_igreen}--- {data}{utils.color_reset}\r\n".encode('utf-8'))
                                elif action == 'get-last-line':
                                    line = self.get_last_line()
                                    if line:
                                        self.orchestrator_stdin.write(f"{line}\n".encode('utf-8'), None)
                                        self.orchestrator_stdin.flush(None)
                                elif action == 'get-variable':
                                    variable = msg.get('data')
                                    if variable:
                                        substituted_bytes = utils.substitute_variables(variable, self.pulse_conn, self.proxy_port)
                                        self.orchestrator_stdin.write(f"{substituted_bytes}\n".encode('utf-8'), None)
                                        self.orchestrator_stdin.flush(None)

                            except json.JSONDecodeError:
                                message = f"Orchestrator script sent invalid JSON: {command_str}"
                                self.app_window.add_history_item(self.pulse_conn.uuid, command_str, "", message, False)
                        else:
                            message = f"\r\n{utils.color_ired} --- {command_str}{utils.color_reset}\r\n"
                            self.feed(message.encode('utf-8'))

                    data_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, is_command)
                else:
                    data_stream.close_async(GLib.PRIORITY_DEFAULT, None, None, None)
            except GLib.Error as e:
                self.app_window.add_history_item(self.pulse_conn.uuid, self.subbed_orchestrator_script_path, "", e.message, False)

        def on_orchestrator_exited(process, result):
            try:
                success = process.wait_finish(result)
                exit_status = process.get_exit_status()
                message = f"Orchestrator script exited with status {exit_status}"
                self.app_window.add_history_item(self.pulse_conn.uuid, self.subbed_orchestrator_script_path, message, "", success)
            except GLib.Error as e:
                self.app_window.add_history_item(self.pulse_conn.uuid, self.subbed_orchestrator_script_path, "", e.message, False)
            finally:
                self.orchestrator_process = None


        if self.pulse_conn and self.pulse_conn.orchestrator_script:
            script_path = os.path.expanduser(self.pulse_conn.orchestrator_script)
            if not os.path.exists(script_path):
                message = f"Orchestrator script '{script_path}' not found"
                self.app_window.add_history_item(self.pulse_conn.uuid, script_path, "", message, False)
                return

            self.subbed_orchestrator_script_path = utils.substitute_variables(script_path, self.pulse_conn, self.proxy_port)

            try:
                self.orchestrator_process = Gio.Subprocess.new(
                    [self.app_window.app_config.shell_program, '-c', self.subbed_orchestrator_script_path],
                    Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                )
                if self.orchestrator_process:
                    self.orchestrator_stdin = self.orchestrator_process.get_stdin_pipe()
                    orchestrator_stdout = self.orchestrator_process.get_stdout_pipe()
                    if orchestrator_stdout:
                        stdout_stream = Gio.DataInputStream.new(orchestrator_stdout)
                        stdout_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, True)
                    orchestrator_stderr = self.orchestrator_process.get_stderr_pipe()
                    if orchestrator_stderr:
                        stderr_stream = Gio.DataInputStream.new(orchestrator_stderr)
                        stderr_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, False)

                    self.orchestrator_process.wait_async(None, on_orchestrator_exited)
            except GLib.Error as e:
                self.app_window.add_history_item(self.pulse_conn.uuid, self.subbed_orchestrator_script_path, "", e.message, False)
