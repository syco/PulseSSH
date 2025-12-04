#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')

from gi.repository import Adw  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import GObject  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import Gtk  # type: ignore
from typing import Optional
import os
import pulse_ssh.data.Connection as connection

class ConnectionDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int,))
    }

    def __init__(self, parent, conn: Optional[connection.Connection] = None):
        super().__init__(title="Connection Configuration", transient_for=parent, modal=True)
        screen_height = Gdk.Display.get_default().get_primary_monitor().get_geometry().height
        self.set_default_size(700, screen_height / 1.3)

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.CANCEL))

        ok_button = Gtk.Button.new_with_mnemonic("_OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.OK))

        self.set_default_widget(ok_button)

        self.conn = conn
        content = self._build_ui()

        header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        header_bar.pack_start(cancel_button)
        header_bar.pack_end(ok_button)

        toolbar_view = Adw.ToolbarView(content = content)
        toolbar_view.add_top_bar(header_bar)

        self.set_content(toolbar_view)

        evk = Gtk.EventControllerKey()
        evk.connect("key-pressed", self.on_key_pressed)
        self.add_controller(evk)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.emit("response", Gtk.ResponseType.CANCEL)
            return True

        is_ctrl = state & Gdk.ModifierType.CONTROL_MASK
        is_enter = keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)

        if is_enter and is_ctrl:
            self.emit("response", Gtk.ResponseType.OK)
            return True

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        sidebar = Gtk.StackSidebar()
        self.stack = Gtk.Stack()
        sidebar.set_stack(self.stack)

        main_box.append(sidebar)
        main_box.append(self.stack)

        page = Adw.PreferencesPage()

        general_group = Adw.PreferencesGroup(title="General")
        page.add(general_group)

        self.name = Adw.EntryRow(title="Name", text=self.conn.name if self.conn else "")
        general_group.add(self.name)

        self.type_dropdown = Adw.ComboRow(title="Type", model=Gtk.StringList.new(["ssh", "sftp"]))
        if self.conn and self.conn.type == "ssh":
            self.type_dropdown.set_selected(0)
        elif self.conn and self.conn.type == "sftp":
            self.type_dropdown.set_selected(1)
        else:
            self.type_dropdown.set_selected(0)
        general_group.add(self.type_dropdown)

        self.folder = Adw.EntryRow(title="Folder", text=self.conn.folder if self.conn else "")
        general_group.add(self.folder)

        details_group = Adw.PreferencesGroup(title="Connection Details")
        page.add(details_group)

        self.host = Adw.EntryRow(title="Host", text=self.conn.host if self.conn else "")
        details_group.add(self.host)

        port_adjustment = Gtk.Adjustment(value=self.conn.port if self.conn else 22, lower=1, upper=65535, step_increment=1)
        self.port = Adw.SpinRow(title="Port", adjustment=port_adjustment)
        details_group.add(self.port)

        self.user = Adw.EntryRow(title="User", text=self.conn.user if self.conn else "")
        details_group.add(self.user)

        self.password = Adw.PasswordEntryRow(title="Password", text=self.conn.password if self.conn and self.conn.password else "")
        details_group.add(self.password)

        self.identity_file = Gtk.Entry(text=self.conn.identity_file if self.conn else "", hexpand=True)
        browse_button = Gtk.Button(label="Browse…")
        browse_button.connect("clicked", self.on_browse_identity_file)
        identity_row = Adw.ActionRow(title="Identity File")
        identity_row.add_suffix(self.identity_file)
        identity_row.add_suffix(browse_button)
        details_group.add(identity_row)

        self.key_passphrase = Adw.PasswordEntryRow(title="Key Passphrase", text=self.conn.key_passphrase if self.conn and self.conn.key_passphrase else "")
        details_group.add(self.key_passphrase)

        behavior_group = Adw.PreferencesGroup(title="Behavior")
        page.add(behavior_group)

        self.use_sudo = Adw.SwitchRow(
            title="Execute with sudo",
            subtitle="Prepend 'sudo' to the SSH command",
            active=self.conn.use_sudo if self.conn else False
        )
        behavior_group.add(self.use_sudo)

        self.use_sshpass = Adw.SwitchRow(
            title="Use sshpass for password",
            subtitle="Pass the password via sshpass (less secure)",
            active=self.conn.use_sshpass if self.conn else False
        )
        behavior_group.add(self.use_sshpass)
        self.use_sshpass.connect("notify::active", self._on_use_sshpass_toggled)

        is_sshpass_active = self.use_sshpass.get_active()
        self.password.set_sensitive(is_sshpass_active)
        self.key_passphrase.set_sensitive(is_sshpass_active)

        self.stack.add_titled(page, "connection", "Connection")

        self._build_ssh_options_page()

        self.prepend_cmds_list = self._create_script_list_page(self.conn.prepend_cmds if self.conn else [])
        self.stack.add_titled(self.prepend_cmds_list, "prepend_cmds", "Pre-Local")

        self._build_orchestrator_script_page()

        self.local_cmds_list = self._create_cmds_list_page(self.conn.local_cmds if self.conn else {})
        self.stack.add_titled(self.local_cmds_list, "local_cmds", "Local Commands")

        self.remote_cmds_list = self._create_cmds_list_page(self.conn.remote_cmds if self.conn else {})
        self.stack.add_titled(self.remote_cmds_list, "remote_cmds", "Remote Commands")

        return main_box

    def _on_use_sshpass_toggled(self, switch, _):
        is_active = switch.get_active()
        self.password.set_sensitive(is_active)
        self.key_passphrase.set_sensitive(is_active)

    def _create_script_list_page(self, commands):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        for command in commands:
            self._add_script_row(list_box, command)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_height=150)
        scrolled_window.set_child(list_box)
        page_box.append(scrolled_window)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_script_row(list_box))
        button_box.append(add_button)
        page_box.append(button_box)

        return page_box

    def _add_script_row(self, list_box, text=""):
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)

        drag_handle = Gtk.Image.new_from_icon_name("open-menu-symbolic")
        drag_handle.set_valign(Gtk.Align.CENTER)
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", lambda s, x, y: Gdk.ContentProvider.new_for_value(row))
        drag_handle.add_controller(drag_source)
        row_box.append(drag_handle)

        entry = Gtk.Entry(text=text, hexpand=True)
        row_box.append(entry)

        remove_button = Gtk.Button(icon_name="list-remove-symbolic")
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect("clicked", self._on_remove_cmds_clicked, list_box, row)
        row_box.append(remove_button)

        row.set_child(row_box)
        list_box.append(row)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_script_drop, list_box)
        row.add_controller(drop_target)

    def _create_cmds_list_page(self, commands: dict):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        for name, command in commands.items():
            self._add_cmds_row(list_box, name, command)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_height=150)
        scrolled_window.set_child(list_box)
        page_box.append(scrolled_window)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_cmds_row(list_box))
        button_box.append(add_button)
        page_box.append(button_box)

        return page_box

    def _add_cmds_row(self, list_box, name="", command=""):
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)

        drag_handle = Gtk.Image.new_from_icon_name("open-menu-symbolic")
        drag_handle.set_valign(Gtk.Align.CENTER)
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", lambda s, x, y: Gdk.ContentProvider.new_for_value(row))
        drag_handle.add_controller(drag_source)
        row_box.append(drag_handle)

        name_entry = Gtk.Entry(text=name, placeholder_text="Name")
        row_box.append(name_entry)

        command_entry = Gtk.Entry(text=command, hexpand=True, placeholder_text="Command")
        row_box.append(command_entry)

        remove_button = Gtk.Button(icon_name="list-remove-symbolic")
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.connect("clicked", self._on_remove_cmds_clicked, list_box, row)
        row_box.append(remove_button)

        row.set_child(row_box)
        list_box.append(row)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_script_drop, list_box)
        row.add_controller(drop_target)

    def _on_remove_cmds_clicked(self, button, list_box, row):
        list_box.remove(row)

    def _on_script_drop(self, target, value, x, y, list_box):
        dragged_row = value
        target_row = target.get_widget()
        if dragged_row != target_row:
            pos = target_row.get_index()
            list_box.remove(dragged_row)
            list_box.insert(dragged_row, pos)
        return True

    def _build_ssh_options_page(self):
        page = Adw.PreferencesPage()

        flags_group = Adw.PreferencesGroup(title="SSH Flags")
        page.add(flags_group)

        self.ssh_forward_agent = Adw.SwitchRow(title="Enable Agent Forwarding (-A)", active=self.conn.ssh_forward_agent if self.conn else False)
        flags_group.add(self.ssh_forward_agent)

        self.ssh_compression = Adw.SwitchRow(title="Enable Compression (-C)", active=self.conn.ssh_compression if self.conn else False)
        flags_group.add(self.ssh_compression)

        self.ssh_x11_forwarding = Adw.SwitchRow(title="Enable X11 Forwarding (-X)", active=self.conn.ssh_x11_forwarding if self.conn else False)
        flags_group.add(self.ssh_x11_forwarding)

        self.ssh_verbose = Adw.SwitchRow(title="Enable Verbose Mode (-v)", active=self.conn.ssh_verbose if self.conn else False)
        flags_group.add(self.ssh_verbose)

        self.ssh_force_pty = Adw.SwitchRow(title="Force Pseudo-terminal Allocation (-t)", active=self.conn.ssh_force_pty if self.conn else False)
        flags_group.add(self.ssh_force_pty)

        self.ssh_unique_sock_proxy = Adw.SwitchRow(title="Unique SOCKS Proxy (-D)", subtitle="Creates a SOCKS proxy on a unique local port", active=self.conn.ssh_unique_sock_proxy if self.conn else False)
        flags_group.add(self.ssh_unique_sock_proxy)

        options_group = Adw.PreferencesGroup(title="Additional Options")
        page.add(options_group)

        self.additional_options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_height=100)
        scrolled_window.set_child(self.additional_options_box)
        options_group.add(scrolled_window)

        if self.conn and self.conn.ssh_additional_options:
            for option in self.conn.ssh_additional_options:
                self._add_option_entry(option)

        add_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_option_entry())
        add_button.set_halign(Gtk.Align.CENTER)
        add_button_box.append(add_button)
        options_group.add(add_button_box)

        self.stack.add_titled(page, "ssh_options", "SSH Options")

    def _add_option_entry(self, text=""):
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry(text=text, hexpand=True)
        remove_button = Gtk.Button(icon_name="list-remove-symbolic")
        remove_button.connect("clicked", self._on_remove_option_clicked, entry_box)

        entry_box.append(entry)
        entry_box.append(remove_button)
        self.additional_options_box.append(entry_box)

    def _on_remove_option_clicked(self, button, box_to_remove):
        self.additional_options_box.remove(box_to_remove)

    def _build_orchestrator_script_page(self):
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="Orchestrator Script")
        page.add(group)

        self.orchestrator_script_entry = Gtk.Entry(text=self.conn.orchestrator_script if self.conn and self.conn.orchestrator_script else "", hexpand=True)
        browse_button = Gtk.Button(label="Browse…")
        browse_button.connect("clicked", self.on_browse_orchestrator_script_file)

        script_row = Adw.ActionRow(title="Script File")
        script_row.add_suffix(self.orchestrator_script_entry)
        script_row.add_suffix(browse_button)
        group.add(script_row)

        self.stack.add_titled(page, "orchestrator_script", "Orchestrator Script")

    def on_browse_orchestrator_script_file(self, button):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Select Orchestrator Script File")
        file_dialog.open(self, None, self.on_orchestrator_script_file_selected)

    def on_orchestrator_script_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.orchestrator_script_entry.set_text(file.get_path())
        except GLib.Error:
            pass

    def on_browse_identity_file(self, button):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Select Identity File")

        ssh_dir = os.path.expanduser("~/.ssh")
        if os.path.isdir(ssh_dir):
            file_dialog.set_initial_folder(Gio.File.new_for_path(ssh_dir))

        file_dialog.open(self, None, self.on_identity_file_selected)

    def on_identity_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.identity_file.set_text(file.get_path())
        except GLib.Error:
            pass

    def get_data(self) -> connection.Connection:
        def get_scripts_from_list(page_box):
            scripts = []
            list_box = page_box.get_first_child().get_child().get_child()
            idx = 0
            while row := list_box.get_row_at_index(idx):
                row_box = row.get_child()
                entry = row_box.get_first_child().get_next_sibling()
                scripts.append(entry.get_text())
                idx += 1

            return [script for script in scripts if script]

        def get_cmds_from_list(page_box):
            scripts = {}
            list_box = page_box.get_first_child().get_child().get_child()
            idx = 0
            while row := list_box.get_row_at_index(idx):
                row_box = row.get_child()
                name_entry = row_box.get_first_child().get_next_sibling()
                command_entry = name_entry.get_next_sibling()
                if name_entry.get_text() and command_entry.get_text():
                    scripts[name_entry.get_text()] = command_entry.get_text()
                idx += 1
            return scripts

        additional_options = []
        child = self.additional_options_box.get_first_child()
        while child:
            entry = child.get_first_child()
            additional_options.append(entry.get_text())
            child = child.get_next_sibling()

        new_conn = connection.Connection(
            name=self.name.get_text(),
            type=self.type_dropdown.get_selected_item().get_string(),
            folder=self.folder.get_text().strip('/') or "",
            host=self.host.get_text(),
            port=int(self.port.get_value()),
            user=self.user.get_text(),
            password=self.password.get_text() or None if self.use_sshpass.get_active() else None,
            identity_file=self.identity_file.get_text() or None,
            key_passphrase=self.key_passphrase.get_text() or None if self.use_sshpass.get_active() else None,
            prepend_cmds=get_scripts_from_list(self.prepend_cmds_list),
            local_cmds=get_cmds_from_list(self.local_cmds_list),
            remote_cmds=get_cmds_from_list(self.remote_cmds_list),
            orchestrator_script=self.orchestrator_script_entry.get_text() or None,
            ssh_forward_agent=self.ssh_forward_agent.get_active(),
            ssh_compression=self.ssh_compression.get_active(),
            ssh_x11_forwarding=self.ssh_x11_forwarding.get_active(),
            ssh_verbose=self.ssh_verbose.get_active(),
            ssh_force_pty=self.ssh_force_pty.get_active(),
            ssh_additional_options=[opt for opt in additional_options if opt],
            ssh_unique_sock_proxy=self.ssh_unique_sock_proxy.get_active(),
            use_sudo=self.use_sudo.get_active(),
            use_sshpass=self.use_sshpass.get_active(),
        )
        if self.conn and hasattr(self.conn, 'uuid'):
            new_conn.uuid = self.conn.uuid

        return new_conn
