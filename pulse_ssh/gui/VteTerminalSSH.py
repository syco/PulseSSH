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
import json
import os
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.VteTerminal as _vte_terminal
import pulse_ssh.Utils as _utils

class VteTerminalSSH(_vte_terminal.VteTerminal):
    def __init__(self, app_window, connection: _connection.Connection, cluster_id: Optional[str] = None, cluster_name: Optional[str] = None, **kwargs):
        super().__init__(app_window, **kwargs)

        self.subbed_ssh_orchestrator_script_path = ""
        self.proxy_port: Optional[int] = None
        self.ssh_orchestrator_process: Optional[Gio.Subprocess] = None

        final_cmd, self.proxy_port = _utils.build_ssh_command(_globals.app_config, connection)
        args = [_globals.app_config.shell_program, "-c", final_cmd]

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

                self.start_ssh_orchestrator_script()

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
        sftp_action = Gio.SimpleAction.new("sftp", None)
        sftp_action.connect("activate", self.open_sftp_tab)
        action_group.add_action(sftp_action)
        menu_model.append("Open SFTP", "term.sftp")

        menu_model.append_section(None, Gio.Menu())
        ftp_action = Gio.SimpleAction.new("ftp", None)
        ftp_action.connect("activate", self.open_ftp_tab)
        action_group.add_action(ftp_action)
        menu_model.append("Open FTP", "term.ftp")

        menu_model.append_section(None, Gio.Menu())

        ssh_remote_cmds_submenu = self.create_ssh_remote_cmds_submenu(action_group)
        menu_model.append_submenu("Remote Commands", ssh_remote_cmds_submenu)

        ssh_local_cmds_submenu = self.create_local_cmds_submenu(action_group)
        menu_model.append_submenu("Local Commands", ssh_local_cmds_submenu)

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

    def create_local_cmds_submenu(self, action_group):
        submenu = Gio.Menu()
        all_local_cmds = {**_globals.app_config.ssh_local_cmds, **self.pulse_conn.ssh_local_cmds}

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

    def create_ssh_remote_cmds_submenu(self, action_group):
        submenu = Gio.Menu()
        all_remote_cmds = {**_globals.app_config.ssh_remote_cmds, **self.pulse_conn.ssh_remote_cmds}

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
        substituted_cmd = _utils.substitute_variables(cmd, self.pulse_conn, self.proxy_port)
        def on_finished(subprocess, result, cmd, conn_uuid):
            try:
                ok, stdout, stderr = subprocess.communicate_utf8_finish(result)
                self.add_history_item(self.pulse_conn.uuid, cmd, stdout, stderr, ok)
            except GLib.Error as e:
                self.add_history_item(self.pulse_conn.uuid, cmd, "", e.message, False)

        try:
            subprocess = Gio.Subprocess.new([_globals.app_config.shell_program, '-c', substituted_cmd], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            subprocess.communicate_utf8_async(None, None, on_finished, substituted_cmd, self.pulse_conn.uuid)
        except GLib.Error as e:
            self.add_history_item(self.pulse_conn.uuid, substituted_cmd, "", e.message, False)

    def run_remote_cmd(self, action, param, cmd):
        if self.pulse_cluster_id and self.pulse_cluster_id in _gui_globals.active_clusters:
            for terminal in _gui_globals.active_clusters[self.pulse_cluster_id].terminals:
                substituted_cmd = _utils.substitute_variables(cmd, terminal.pulse_conn, terminal.proxy_port)
                terminal.feed_child(f"{substituted_cmd}\n".encode('utf-8'))
        else:
            substituted_cmd = _utils.substitute_variables(cmd, self.pulse_conn, self.proxy_port)
            self.feed_child(f"{substituted_cmd}\n".encode('utf-8'))

    def open_sftp_tab(self, action, param):
        clone = self.pulse_conn.get_cloned_connection()
        clone.type = "sftp"
        clone.sftp_additional_options = self.pulse_conn.ssh_additional_options
        clone.sftp_compression = self.pulse_conn.ssh_compression
        clone.sftp_forward_agent = self.pulse_conn.ssh_forward_agent
        clone.sftp_verbose = self.pulse_conn.ssh_verbose

        _gui_globals.layout_manager.open_connection_tab(clone)

    def open_ftp_tab(self, action, param):
        clone = self.pulse_conn.get_cloned_connection()
        clone.type = "ftp"
        clone.port = 21
        clone.ftp_verbose = self.pulse_conn.ssh_verbose

        _gui_globals.layout_manager.open_connection_tab(clone)

    def start_ssh_orchestrator_script(self):
        def on_line_received(data_stream: Gio.DataInputStream, result, is_command: bool = True):
            if not self.ssh_orchestrator_process:
                try:
                    data_stream.read_line_finish(result)
                    data_stream.close_async(GLib.PRIORITY_DEFAULT, None, None, None)
                except GLib.Error as e:
                    self.add_history_item(self.pulse_conn.uuid, self.subbed_ssh_orchestrator_script_path, "", e.message, False)
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
                                output = None
                                if action == 'feed-child':
                                    data = msg.get('data', '')
                                    if data:
                                        self.feed_child(f"{data}\n".encode('utf-8'))
                                elif action == 'feed':
                                    data = msg.get('data', '')
                                    if data:
                                        self.feed(f"\r\n {_utils.color_igreen}--- {data}{_utils.color_reset}\r\n".encode('utf-8'))
                                elif action == 'get-last-line':
                                    output = self.get_last_line()
                                elif action == 'get-variable':
                                    variable = msg.get('data')
                                    if variable:
                                        output = _utils.substitute_variables(variable, self.pulse_conn, self.proxy_port)

                                if output:
                                    self.ssh_orchestrator_stdin.write(f"{output}\n".encode('utf-8'), None)
                                    self.ssh_orchestrator_stdin.flush(None)

                            except json.JSONDecodeError:
                                message = f"SSH orchestrator script sent invalid JSON: {command_str}"
                                self.add_history_item(self.pulse_conn.uuid, command_str, "", message, False)
                        else:
                            message = f"\r\n{_utils.color_ired} --- {command_str}{_utils.color_reset}\r\n"
                            self.feed(message.encode('utf-8'))

                    data_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, is_command)
                else:
                    data_stream.close_async(GLib.PRIORITY_DEFAULT, None, None, None)
            except GLib.Error as e:
                self.add_history_item(self.pulse_conn.uuid, self.subbed_ssh_orchestrator_script_path, "", e.message, False)

        def on_ssh_orchestrator_exited(process, result):
            try:
                success = process.wait_finish(result)
                exit_status = process.get_exit_status()
                message = f"Orchestrator script exited with status {exit_status}"
                self.add_history_item(self.pulse_conn.uuid, self.subbed_ssh_orchestrator_script_path, message, "", success)
            except GLib.Error as e:
                self.add_history_item(self.pulse_conn.uuid, self.subbed_ssh_orchestrator_script_path, "", e.message, False)
            finally:
                self.ssh_orchestrator_process = None


        if self.pulse_conn and self.pulse_conn.ssh_orchestrator_script:
            script_path = os.path.expanduser(self.pulse_conn.ssh_orchestrator_script)
            if not os.path.exists(script_path):
                message = f"Orchestrator script '{script_path}' not found"
                self.add_history_item(self.pulse_conn.uuid, script_path, "", message, False)
                return

            self.subbed_ssh_orchestrator_script_path = _utils.substitute_variables(script_path, self.pulse_conn, self.proxy_port)

            try:
                self.ssh_orchestrator_process = Gio.Subprocess.new(
                    [_globals.app_config.shell_program, '-c', self.subbed_ssh_orchestrator_script_path],
                    Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
                )
                if self.ssh_orchestrator_process:
                    self.ssh_orchestrator_stdin = self.ssh_orchestrator_process.get_stdin_pipe()
                    ssh_orchestrator_stdout = self.ssh_orchestrator_process.get_stdout_pipe()
                    if ssh_orchestrator_stdout:
                        stdout_stream = Gio.DataInputStream.new(ssh_orchestrator_stdout)
                        stdout_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, True)
                    ssh_orchestrator_stderr = self.ssh_orchestrator_process.get_stderr_pipe()
                    if ssh_orchestrator_stderr:
                        stderr_stream = Gio.DataInputStream.new(ssh_orchestrator_stderr)
                        stderr_stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_received, False)

                    self.ssh_orchestrator_process.wait_async(None, on_ssh_orchestrator_exited)
            except GLib.Error as e:
                self.add_history_item(self.pulse_conn.uuid, self.subbed_ssh_orchestrator_script_path, "", e.message, False)
