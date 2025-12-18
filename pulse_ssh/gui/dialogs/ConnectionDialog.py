#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import GObject  # type: ignore
from gi.repository import Gtk  # type: ignore
from typing import Optional
import os
import pulse_ssh.Globals as _globals
import pulse_ssh.data.Connection as _connection
import pulse_ssh.gui.views.list_items.StringObject as _string_object

class ConnectionDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int,))
    }

    def __init__(self, parent, conn: Optional[_connection.Connection] = None):
        super().__init__(title="Connection Configuration", transient_for=parent, modal=True)

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
        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(200)
        split_view.set_max_sidebar_width(300)
        split_view.set_collapsed(False)

        sidebar = Gtk.StackSidebar()
        self.stack = Gtk.Stack()
        self.stack.set_size_request(600, 400)
        self.stack.set_hhomogeneous(True)
        self.stack.set_vhomogeneous(True)
        sidebar.set_stack(self.stack)

        split_view.set_sidebar(Adw.NavigationPage.new(sidebar, "Categories"))
        split_view.set_content(Adw.NavigationPage.new(self.stack, "Settings"))

        general_page = Adw.PreferencesPage()
        self.stack.add_titled(general_page, "general", "General")

        general_group = Adw.PreferencesGroup()
        general_page.add(general_group)

        self.name = Adw.EntryRow(title="Name", text=self.conn.name if self.conn else "")
        general_group.add(self.name)

        self.type_dropdown = Adw.ComboRow(title="Type", model=Gtk.StringList.new(["ssh", "sftp", "ftp"]))
        if self.conn and self.conn.type == "ftp":
            self.type_dropdown.set_selected(2)
        elif self.conn and self.conn.type == "sftp":
            self.type_dropdown.set_selected(1)
        else:
            self.type_dropdown.set_selected(0)
        general_group.add(self.type_dropdown)
        self.type_dropdown.connect("notify::selected-item", self._on_type_changed)

        self.folder = Adw.EntryRow(title="Folder", text=self.conn.folder if self.conn else "")
        general_group.add(self.folder)

        details_page = Adw.PreferencesPage()
        self.stack.add_titled(details_page, "connection_details", "Connection Details")

        details_group = Adw.PreferencesGroup()
        details_page.add(details_group)

        self.host = Adw.EntryRow(title="Host", text=self.conn.host if self.conn else "")
        details_group.add(self.host)

        port_adjustment = Gtk.Adjustment(value=self.conn.port if self.conn else 22, lower=1, upper=65535, step_increment=1)
        self.port = Adw.SpinRow(title="Port", adjustment=port_adjustment)
        details_group.add(self.port)

        self.user = Adw.EntryRow(title="User", text=self.conn.user if self.conn else "")
        details_group.add(self.user)

        self.password_group = Adw.PreferencesGroup(title="Password Authentication")
        details_page.add(self.password_group)

        self.password = Adw.PasswordEntryRow(title="Password", text=self.conn.password if self.conn and self.conn.password else "")
        self.password_group.add(self.password)

        self.identity_group = Adw.PreferencesGroup(title="Identity File Authentication")
        details_page.add(self.identity_group)

        self.identity_file = Gtk.Entry(text=self.conn.identity_file if self.conn else "", hexpand=True)
        browse_button = Gtk.Button(label="Browse…")
        browse_button.connect("clicked", self.on_browse_identity_file)
        identity_row = Adw.ActionRow(title="Identity File")
        identity_row.add_suffix(self.identity_file)
        identity_row.add_suffix(browse_button)
        self.identity_group.add(identity_row)

        self.key_passphrase = Adw.PasswordEntryRow(title="Key Passphrase", text=self.conn.key_passphrase if self.conn and self.conn.key_passphrase else "")
        self.identity_group.add(self.key_passphrase)

        execution_group = Adw.PreferencesGroup(title="Execution Options")
        details_page.add(execution_group)

        self.use_sshpass = Adw.SwitchRow(title="Use sshpass for password", subtitle="Pass the password via sshpass (less secure)", active=self.conn.use_sshpass if self.conn else False)
        self.use_sshpass.connect("notify::active", self._on_use_sshpass_toggled)
        execution_group.add(self.use_sshpass)

        self.use_sudo = Adw.SwitchRow(title="Execute with sudo", subtitle="Prepend 'sudo' to the SSH command", active=self.conn.use_sudo if self.conn else False)
        execution_group.add(self.use_sudo)

        is_sshpass_active = self.use_sshpass.get_active()
        self.password.set_sensitive(is_sshpass_active)

        self.ssh_options_page = self._build_ssh_options_page()
        self.stack.add_titled(self.ssh_options_page, "ssh_options", "SSH Options")

        self.ssh_prepend_cmds_list = self._create_script_list_page(self.conn.ssh_prepend_cmds if self.conn else [])
        self.stack.add_titled(self.ssh_prepend_cmds_list, "ssh_prepend_cmds", "SSH Pre-Local")

        self.ssh_orchestrator_script_page = self._build_ssh_orchestrator_script_page()
        self.stack.add_titled(self.ssh_orchestrator_script_page, "ssh_orchestrator_script", "SSH Orchestrator Script")

        self.ssh_remote_cmds_list = self._create_cmds_list_page(self.conn.ssh_remote_cmds if self.conn else {})
        self.stack.add_titled(self.ssh_remote_cmds_list, "ssh_remote_cmds", "SSH Remote Commands")

        self.ssh_local_cmds_list = self._create_cmds_list_page(self.conn.ssh_local_cmds if self.conn else {})
        self.stack.add_titled(self.ssh_local_cmds_list, "ssh_local_cmds", "SSH Local Commands")

        self.sftp_options_page = self._build_sftp_options_page()
        self.stack.add_titled(self.sftp_options_page, "sftp_options", "SFTP Options")

        self.ftp_options_page = self._build_ftp_options_page()
        self.stack.add_titled(self.ftp_options_page, "ftp_options", "FTP Options")

        self._on_type_changed(self.type_dropdown, None)

        return split_view

    def _on_use_sshpass_toggled(self, switch, _):
        is_active = switch.get_active()
        self.password.set_sensitive(is_active)

    def _on_type_changed(self, dropdown, _):
        selected_type = dropdown.get_selected_item().get_string()

        if selected_type == "ssh":
            self.port.set_value(22)
        elif selected_type == "sftp":
            self.port.set_value(22)
        elif selected_type == "ftp":
            self.port.set_value(21)

        self.stack.get_page(self.ssh_options_page).set_visible(selected_type == "ssh")
        self.stack.get_page(self.ssh_prepend_cmds_list).set_visible(selected_type == "ssh")
        self.stack.get_page(self.ssh_orchestrator_script_page).set_visible(selected_type == "ssh")
        self.stack.get_page(self.ssh_remote_cmds_list).set_visible(selected_type == "ssh")
        self.stack.get_page(self.ssh_local_cmds_list).set_visible(selected_type == "ssh")
        self.user.set_visible(selected_type != "ftp")
        self.password_group.set_visible(selected_type != "ftp")
        self.identity_group.set_visible(selected_type != "ftp")
        self.use_sshpass.set_visible(selected_type != "ftp")
        self.stack.get_page(self.sftp_options_page).set_visible(selected_type == "sftp")
        self.stack.get_page(self.ftp_options_page).set_visible(selected_type == "ftp")

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

        proxy_jump_group = Adw.PreferencesGroup(title="Proxy Jump")
        page.add(proxy_jump_group)

        self.proxy_jump_connections = {"": "None"}
        for c in sorted(_globals.connections.values(), key=lambda item: (item.folder or "", item.name)):
            if self.conn and c.uuid == self.conn.uuid:
                continue
            if c.type == "ssh":
                self.proxy_jump_connections[c.uuid] = f"{c.folder}/{c.name}" if c.folder else c.name

        ssh_proxy_jump_model = Gio.ListStore.new(_string_object.StringObject)
        for id, name in self.proxy_jump_connections.items():
            ssh_proxy_jump_model.append(_string_object.StringObject(id, name))

        ssh_proxy_jump_expression = Gtk.PropertyExpression.new(_string_object.StringObject, None, "name")

        ssh_proxy_jump_filter = Gtk.StringFilter.new(ssh_proxy_jump_expression)
        ssh_proxy_jump_filter.set_ignore_case(True)
        ssh_proxy_jump_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        filter_model = Gtk.FilterListModel.new(ssh_proxy_jump_model, ssh_proxy_jump_filter)

        self.ssh_proxy_jump = Gtk.DropDown()
        self.ssh_proxy_jump.set_model(filter_model)
        self.ssh_proxy_jump.set_expression(ssh_proxy_jump_expression)
        self.ssh_proxy_jump.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        self.ssh_proxy_jump.set_enable_search(True)

        def on_theme_search_changed(dropdown, _):
            ssh_proxy_jump_filter.set_search(dropdown.get_search())

        self.ssh_proxy_jump.connect("notify::search", on_theme_search_changed)

        if self.conn and self.conn.ssh_proxy_jump:
            for i in range(ssh_proxy_jump_model.get_n_items()):
                item = ssh_proxy_jump_model.get_item(i)
                if item.id == self.conn.ssh_proxy_jump:
                    self.ssh_proxy_jump.set_selected(i)
                    break
        else:
            self.ssh_proxy_jump.set_selected(0)

        proxy_jump_row = Adw.ActionRow(title="Jump Host (-J)", activatable_widget=self.ssh_proxy_jump)
        proxy_jump_row.add_suffix(self.ssh_proxy_jump)
        proxy_jump_row.set_activatable_widget(self.ssh_proxy_jump)
        proxy_jump_group.add(proxy_jump_row)

        self.ssh_unique_sock_proxy = Adw.SwitchRow(title="Unique SOCKS Proxy (-D)", subtitle="Creates a SOCKS proxy on a unique local port", active=self.conn.ssh_unique_sock_proxy if self.conn else False)
        flags_group.add(self.ssh_unique_sock_proxy)

        options_group = Adw.PreferencesGroup(title="Additional Options")
        page.add(options_group)

        self.ssh_additional_options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        options_group.add(self.ssh_additional_options_box)

        if self.conn and self.conn.ssh_additional_options:
            for option in self.conn.ssh_additional_options:
                self._add_option_entry(self.ssh_additional_options_box, option)

        add_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_option_entry(self.ssh_additional_options_box))
        add_button.set_halign(Gtk.Align.CENTER)
        add_button_box.append(add_button)
        options_group.add(add_button_box)

        return page

    def _build_sftp_options_page(self):
        page = Adw.PreferencesPage()

        flags_group = Adw.PreferencesGroup(title="SFTP Flags")
        page.add(flags_group)

        self.sftp_forward_agent = Adw.SwitchRow(title="Enable Agent Forwarding (-A)", active=self.conn.sftp_forward_agent if self.conn else False)
        flags_group.add(self.sftp_forward_agent)

        self.sftp_compression = Adw.SwitchRow(title="Enable Compression (-C)", active=self.conn.sftp_compression if self.conn else False)
        flags_group.add(self.sftp_compression)

        self.sftp_verbose = Adw.SwitchRow(title="Enable Verbose Mode (-v)", active=self.conn.sftp_verbose if self.conn else False)
        flags_group.add(self.sftp_verbose)

        options_group = Adw.PreferencesGroup(title="Additional Options")
        page.add(options_group)

        self.sftp_additional_options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        options_group.add(self.sftp_additional_options_box)

        if self.conn and self.conn.sftp_additional_options:
            for option in self.conn.sftp_additional_options:
                self._add_option_entry(self.sftp_additional_options_box, option)

        add_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_option_entry(self.sftp_additional_options_box))
        add_button.set_halign(Gtk.Align.CENTER)
        add_button_box.append(add_button)
        options_group.add(add_button_box)

        return page

    def _build_ftp_options_page(self):
        page = Adw.PreferencesPage()

        flags_group = Adw.PreferencesGroup(title="FTP Flags")
        page.add(flags_group)

        self.ftp_active = Adw.SwitchRow(title="Enable Active Mode (-A)", active=self.conn.ftp_active if self.conn else False)
        flags_group.add(self.ftp_active)

        self.ftp_passive = Adw.SwitchRow(title="Enable Passive Mode (-p)", active=self.conn.ftp_passive if self.conn else False)
        flags_group.add(self.ftp_passive)

        self.ftp_trace = Adw.SwitchRow(title="Enable Trace Mode (-T)", active=self.conn.ftp_trace if self.conn else False)
        flags_group.add(self.ftp_trace)

        self.ftp_verbose = Adw.SwitchRow(title="Enable Verbose Mode (-v)", active=self.conn.ftp_trace if self.conn else False)
        flags_group.add(self.ftp_verbose)

        return page

    def _add_option_entry(self, target_box, text=""):
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry(text=text, hexpand=True)
        remove_button = Gtk.Button(icon_name="list-remove-symbolic")
        remove_button.connect("clicked", self._on_remove_option_clicked, entry_box, target_box)

        entry_box.append(entry)
        entry_box.append(remove_button)
        target_box.append(entry_box)

    def _on_remove_option_clicked(self, button, box_to_remove, target_box):
        target_box.remove(box_to_remove)

    def _build_ssh_orchestrator_script_page(self):
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="Orchestrator Script")
        page.add(group)

        self.ssh_orchestrator_script_entry = Gtk.Entry(text=self.conn.ssh_orchestrator_script if self.conn and self.conn.ssh_orchestrator_script else "", hexpand=True)
        browse_button = Gtk.Button(label="Browse…")
        browse_button.connect("clicked", self.on_browse_ssh_orchestrator_script_file)

        script_row = Adw.ActionRow(title="Script File")
        script_row.add_suffix(self.ssh_orchestrator_script_entry)
        script_row.add_suffix(browse_button)
        group.add(script_row)

        return page

    def on_browse_ssh_orchestrator_script_file(self, button):
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Select SSH Orchestrator Script File")
        file_dialog.open(self, None, self.on_ssh_orchestrator_script_file_selected)

    def on_ssh_orchestrator_script_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.ssh_orchestrator_script_entry.set_text(file.get_path())
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

    def get_data(self) -> _connection.Connection:
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

        def get_additional_options_from_box(box):
            options = []
            if not box:
                return options
            child = box.get_first_child()
            while child:
                entry = child.get_first_child()
                options.append(entry.get_text())
                child = child.get_next_sibling()
            return [opt for opt in options if opt]

        ssh_additional_options = get_additional_options_from_box(self.ssh_additional_options_box)
        sftp_additional_options = get_additional_options_from_box(self.sftp_additional_options_box)


        ssh_proxy_jump_uuid = None
        selected_ssh_jump = self.ssh_proxy_jump.get_selected_item()
        if selected_ssh_jump:
            selected_jump_uuid = selected_ssh_jump.id
            if _globals.connections.get(selected_jump_uuid):
                ssh_proxy_jump_uuid = _globals.connections[selected_jump_uuid].uuid

        new_conn = _connection.Connection(
            name=self.name.get_text(),
            type=self.type_dropdown.get_selected_item().get_string(),
            folder=self.folder.get_text().strip().strip('/').replace('//', '/') or "",
            host=self.host.get_text(),
            port=int(self.port.get_value()),
            user=self.user.get_text(),
            password=self.password.get_text() or None if self.use_sshpass.get_active() else None,
            identity_file=self.identity_file.get_text() or None,
            key_passphrase=self.key_passphrase.get_text() or None,
            ssh_forward_agent=self.ssh_forward_agent.get_active(),
            ssh_compression=self.ssh_compression.get_active(),
            ssh_x11_forwarding=self.ssh_x11_forwarding.get_active(),
            ssh_verbose=self.ssh_verbose.get_active(),
            ssh_force_pty=self.ssh_force_pty.get_active(),
            ssh_unique_sock_proxy=self.ssh_unique_sock_proxy.get_active(),
            ssh_proxy_jump=ssh_proxy_jump_uuid,
            ssh_additional_options=ssh_additional_options,
            ssh_prepend_cmds=get_scripts_from_list(self.ssh_prepend_cmds_list),
            ssh_orchestrator_script=self.ssh_orchestrator_script_entry.get_text() or None,
            ssh_remote_cmds=get_cmds_from_list(self.ssh_remote_cmds_list),
            ssh_local_cmds=get_cmds_from_list(self.ssh_local_cmds_list),
            sftp_forward_agent=self.sftp_forward_agent.get_active(),
            sftp_compression=self.sftp_compression.get_active(),
            sftp_verbose=self.sftp_verbose.get_active(),
            sftp_additional_options=sftp_additional_options,
            ftp_active=self.ftp_active.get_active(),
            ftp_passive=self.ftp_passive.get_active(),
            ftp_trace=self.ftp_trace.get_active(),
            ftp_verbose=self.ftp_verbose.get_active(),
            use_sudo=self.use_sudo.get_active(),
            use_sshpass=self.use_sshpass.get_active(),
        )
        if self.conn and hasattr(self.conn, 'uuid'):
            new_conn.uuid = self.conn.uuid

        return new_conn
