#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')

from gi.repository import Adw  # type: ignore
from gi.repository import GObject  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Pango  # type: ignore
import os
import pulse_ssh.Utils as utils
import pulse_ssh.data.AppConfig as app_config
import pulse_ssh.ui.views.list_items.StringObject as string_object

SHELL_PROGRAMS = [
    "bash",
    "zsh",
    "sh",
    "fish"
]
ON_DISCONNECT = {
    "Close Immediately": "close",
    "Restart Automatically": "restart",
    "Wait For Input": "wait_for_key",
}
CURSOR_SHAPES = {
    "Block": "block",
    "I-Beam": "ibeam",
    "Underline": "underline",
}
WINDOW_CONTROLS_POSITIONS = {
    "Right": "right",
    "Left": "left",
}
COLOR_SCHEMES = {
    "Follow System": "default",
    "Light": "force-light",
    "Dark": "force-dark",
}

class AppConfigDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int,))
    }

    def __init__(self, parent, config: app_config.AppConfig, about_info: dict):
        super().__init__(title="Application Configuration", transient_for=parent, modal=True)
        screen_height = Gdk.Display.get_default().get_primary_monitor().get_geometry().height
        self.set_default_size(700, screen_height / 1.3)

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.CANCEL))

        ok_button = Gtk.Button.new_with_mnemonic("_OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.OK))

        apply_button = Gtk.Button.new_with_mnemonic("_Apply")
        apply_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.APPLY))

        self.set_default_widget(ok_button)

        content = self._build_ui(config, about_info)

        header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        header_bar.pack_start(cancel_button)
        header_bar.pack_end(ok_button)
        header_bar.pack_end(apply_button)

        toolbar_view = Adw.ToolbarView(content = content)
        toolbar_view.add_top_bar(header_bar)

        self.set_content(toolbar_view)

        evk = Gtk.EventControllerKey()
        evk.connect("key-pressed", self.on_key_pressed)
        self.add_controller(evk)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape and not self.get_focus() in self._find_entries(self):
            self.emit("response", Gtk.ResponseType.CANCEL)
            return True

        is_ctrl = state & Gdk.ModifierType.CONTROL_MASK
        is_enter = keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)

        if is_enter and not is_ctrl:
            self.emit("response", Gtk.ResponseType.OK)
            return True

    def _find_entries(self, widget):
        entries = []
        if isinstance(widget, Gtk.Entry):
            entries.append(widget)
        if hasattr(widget, 'get_child') and widget.get_child():
            entries.extend(self._find_entries(widget.get_child()))
        return entries

    def _build_ui(self, config: app_config.AppConfig, about_info: dict):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        sidebar = Gtk.StackSidebar()
        self.stack = Gtk.Stack()
        sidebar.set_stack(self.stack)

        main_box.append(sidebar)
        main_box.append(self.stack)

        self._build_general_page(config)
        self._build_ssh_page(config)
        self._build_binaries_page(config)
        self._build_shortcuts_page()
        self._build_variables_page()
        self._build_about_page(about_info)

        return main_box

    def _build_general_page(self, config: app_config.AppConfig):
        page = Adw.PreferencesPage()

        appearance_group = Adw.PreferencesGroup(title="Appearance")
        page.add(appearance_group)

        self.font_chooser = Gtk.FontDialogButton(dialog=Gtk.FontDialog(modal=True))
        font_desc = Pango.FontDescription.from_string(f"{config.font_family} {config.font_size}")
        self.font_chooser.set_font_desc(font_desc)
        font_row = Adw.ActionRow(title="Terminal Font")
        font_row.add_suffix(self.font_chooser)
        font_row.set_activatable_widget(self.font_chooser)
        appearance_group.add(font_row)

        self.themes = utils.load_themes()
        theme_names = sorted(list(self.themes.keys()))

        theme_model = Gio.ListStore.new(string_object.StringObject)
        for name in theme_names:
            theme_model.append(string_object.StringObject(name=name))

        theme_expression = Gtk.PropertyExpression.new(string_object.StringObject, None, "name")

        theme_filter = Gtk.StringFilter.new(theme_expression)
        theme_filter.set_ignore_case(True)
        theme_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        filter_model = Gtk.FilterListModel.new(theme_model, theme_filter)

        self.theme = Gtk.DropDown()
        self.theme.set_model(filter_model)
        self.theme.set_expression(theme_expression)
        self.theme.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        self.theme.set_enable_search(True)

        def on_theme_search_changed(dropdown, _):
            theme_filter.set_search(dropdown.get_search())

        self.theme.connect("notify::search", on_theme_search_changed)

        try:
            self.theme.set_selected(theme_names.index(config.theme))
        except (ValueError, IndexError):
            self.theme.set_selected(0)
        theme_row = Adw.ActionRow(title="Theme")
        theme_row.add_suffix(self.theme)
        theme_row.set_activatable_widget(self.theme)
        appearance_group.add(theme_row)

        self.cursor_shape = Adw.ComboRow(title="Cursor Shape", model=Gtk.StringList.new(list(CURSOR_SHAPES.keys())))
        current_cursor_shape_key = next((k for k, v in CURSOR_SHAPES.items() if v == config.cursor_shape), "Block")
        self.cursor_shape.set_selected(list(CURSOR_SHAPES.keys()).index(current_cursor_shape_key))
        appearance_group.add(self.cursor_shape)

        self.color_scheme = Adw.ComboRow(title="Color Scheme", model=Gtk.StringList.new(list(COLOR_SCHEMES.keys())))
        current_color_scheme_key = next((k for k, v in COLOR_SCHEMES.items() if v == config.color_scheme), "Follow System")
        self.color_scheme.set_selected(list(COLOR_SCHEMES.keys()).index(current_color_scheme_key))
        appearance_group.add(self.color_scheme)

        self.scrollbar_visible = Adw.SwitchRow(title="Show Scrollbar", active=config.scrollbar_visible)
        appearance_group.add(self.scrollbar_visible)

        self.sidebar_on_right = Adw.SwitchRow(title="Show Sidebar on the Right", active=config.sidebar_on_right)
        appearance_group.add(self.sidebar_on_right)

        behavior_group = Adw.PreferencesGroup(title="Behavior")
        page.add(behavior_group)

        self.shell_program = Adw.ComboRow(title="Shell", model=Gtk.StringList.new(SHELL_PROGRAMS))
        try:
            self.shell_program.set_selected(SHELL_PROGRAMS.index(config.shell_program))
        except ValueError:
            self.shell_program.set_selected(0)
        behavior_group.add(self.shell_program)

        self.on_disconnect = Adw.ComboRow(title="On Disconnect", model=Gtk.StringList.new(list(ON_DISCONNECT.keys())))
        current_behavior_key = next((k for k, v in ON_DISCONNECT.items() if v == config.on_disconnect_behavior), "Wait For Input")
        self.on_disconnect.set_selected(list(ON_DISCONNECT.keys()).index(current_behavior_key))
        behavior_group.add(self.on_disconnect)

        self.split_at_root = Adw.SwitchRow(title="Split at the Root", subtitle="Splits the whole tab area instead of just the current terminal", active=config.split_at_root)
        behavior_group.add(self.split_at_root)

        self.audible_bell = Adw.SwitchRow(title="Audible Bell", subtitle="Enable the terminal bell sound", active=config.audible_bell)
        behavior_group.add(self.audible_bell)

        scrolling_group = Adw.PreferencesGroup(title="Scrolling")
        page.add(scrolling_group)

        scrollback_adjustment = Gtk.Adjustment(
            value=config.scrollback_lines,
            lower=-1,
            upper=1000000,
            step_increment=1000,
            page_increment=10000
        )
        self.scrollback = Adw.SpinRow(adjustment=scrollback_adjustment, title="Scrollback Lines", subtitle="Number of lines to keep in history (-1 for unlimited)")
        scrolling_group.add(self.scrollback)

        self.scroll_on_output = Adw.SwitchRow(title="Scroll on Output", active=config.scroll_on_output)
        scrolling_group.add(self.scroll_on_output)

        self.scroll_on_keystroke = Adw.SwitchRow(title="Scroll on Keystroke", active=config.scroll_on_keystroke)
        scrolling_group.add(self.scroll_on_keystroke)

        self.scroll_on_insert = Adw.SwitchRow(title="Scroll on Insert (deprecated)", subtitle="This option may have no effect", active=config.scroll_on_insert)
        scrolling_group.add(self.scroll_on_insert)

        self.stack.add_titled(page, "general", "General")

    def _build_ssh_page(self, config: app_config.AppConfig):
        page_grid = Gtk.Grid(margin_start=10, margin_end=10, margin_top=10, margin_bottom=10, row_spacing=6, column_spacing=6)

        self.ssh_forward_agent = Gtk.CheckButton(label="Enable Agent Forwarding (-A)", active=config.ssh_forward_agent)
        page_grid.attach(self.ssh_forward_agent, 0, 0, 2, 1)

        self.ssh_compression = Gtk.CheckButton(label="Enable Compression (-C)", active=config.ssh_compression)
        page_grid.attach(self.ssh_compression, 0, 1, 2, 1)

        self.ssh_x11_forwarding = Gtk.CheckButton(label="Enable X11 Forwarding (-X)", active=config.ssh_x11_forwarding)
        page_grid.attach(self.ssh_x11_forwarding, 0, 2, 2, 1)

        self.ssh_verbose = Gtk.CheckButton(label="Enable Verbose Mode (-v)", active=config.ssh_verbose)
        page_grid.attach(self.ssh_verbose, 0, 3, 2, 1)

        self.ssh_force_pty = Gtk.CheckButton(label="Force Pseudo-terminal Allocation (-t)", active=config.ssh_force_pty)
        page_grid.attach(self.ssh_force_pty, 0, 4, 2, 1)

        self.stack.add_titled(page_grid, "ssh_settings", "SSH Settings")

        self.pre_local_list = self._create_script_list_page(config.pre_local_cmds)
        self.post_local_list = self._create_script_list_page(config.post_local_cmds)
        self.post_remote_list = self._create_script_list_page(config.post_remote_cmds)
        self.remote_scripts_list = self._create_script_list_page(config.remote_scripts)
        self.post_manual_local_list = self._create_manual_script_list_page(config.post_manual_local_cmds)

        self.stack.add_titled(self.pre_local_list, "pre_local", "Pre-Local")
        self.stack.add_titled(self.post_local_list, "post_local", "Post-Local")
        self.stack.add_titled(self.post_remote_list, "post_remote", "Post-Remote")
        self.stack.add_titled(self.remote_scripts_list, "remote_scripts", "Remote Scripts")
        self.stack.add_titled(self.post_manual_local_list, "post_manual_local", "Manual Scripts")

    def _build_binaries_page(self, config: app_config.AppConfig):
        page_grid = Gtk.Grid(margin_start=10, margin_end=10, margin_top=10, margin_bottom=10, row_spacing=6, column_spacing=6)

        self.ssh_path_entry = Gtk.Entry(text=config.ssh_path, activates_default=True)
        page_grid.attach(Gtk.Label(label="SSH Path", xalign=0), 0, 0, 1, 1)
        page_grid.attach(self.ssh_path_entry, 1, 0, 1, 1)

        self.sftp_path_entry = Gtk.Entry(text=config.sftp_path, activates_default=True)
        page_grid.attach(Gtk.Label(label="SFTP Path", xalign=0), 0, 1, 1, 1)
        page_grid.attach(self.sftp_path_entry, 1, 1, 1, 1)

        self.scp_path_entry = Gtk.Entry(text=config.scp_path, activates_default=True)
        page_grid.attach(Gtk.Label(label="SCP Path", xalign=0), 0, 2, 1, 1)
        page_grid.attach(self.scp_path_entry, 1, 2, 1, 1)

        self.sshpass_path_entry = Gtk.Entry(text=config.sshpass_path, activates_default=True)
        page_grid.attach(Gtk.Label(label="SSHPASS Path", xalign=0), 0, 3, 1, 1)
        page_grid.attach(self.sshpass_path_entry, 1, 3, 1, 1)

        self.sudo_path_entry = Gtk.Entry(text=config.sudo_path, activates_default=True)
        page_grid.attach(Gtk.Label(label="SUDO Path", xalign=0), 0, 4, 1, 1)
        page_grid.attach(self.sudo_path_entry, 1, 4, 1, 1)

        self.stack.add_titled(page_grid, "binaries", "Binaries")

    def _build_shortcuts_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12)

        shortcuts = [
            ("Ctrl + 0", "Reset font size"),
            ("Ctrl + F", "Focus search bar in sidebar"),
            ("Ctrl + Minus", "Decrease font size"),
            ("Ctrl + Plus", "Increase font size"),
            ("Ctrl + Shift + B", "Split terminal vertically"),
            ("Ctrl + Shift + C", "Copy selected text"),
            ("Ctrl + Shift + D", "Duplicate focused terminal in a new tab"),
            ("Ctrl + Shift + H", "Split terminal horizontally"),
            ("Ctrl + Shift + T", "Open a new terminal tab"),
            ("Ctrl + Shift + V", "Paste from clipboard"),
            ("Ctrl + Shift + W", "Close the current tab"),
            ("F11", "Toggle fullscreen"),
            ("Shift + Arrow Keys", "Navigate between split terminals"),
        ]

        for i, (keys, description) in enumerate(shortcuts):
            keys_label = Gtk.Label(label=f"`{keys}`", xalign=1, use_markup=True)
            description_label = Gtk.Label(label=description, xalign=0)
            grid.attach(keys_label, 0, i, 1, 1)
            grid.attach(description_label, 1, i, 1, 1)

        page_box.append(grid)
        self.stack.add_titled(page_box, "shortcuts", "Shortcuts")

    def _build_variables_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12)

        variables = [
            ("${name}", "The name of the connection."),
            ("${host}", "The hostname or IP address."),
            ("${user}", "The username for the connection."),
            ("${port}", "The SSH port number."),
            ("${identity_file}", "Path to the identity file (if any)."),
            ("${password}", "The password for the connection (if stored)."),
            ("${folder}", "The folder the connection belongs to."),
            ("${uuid}", "The unique ID of the connection."),
            ("${proxy_port}", "The dynamic SOCKS proxy port (if enabled)."),
        ]

        for i, (variable, description) in enumerate(variables):
            var_label = Gtk.Label(label=f"`{variable}`", xalign=1, use_markup=True)
            desc_label = Gtk.Label(label=description, xalign=0)
            grid.attach(var_label, 0, i, 1, 1)
            grid.attach(desc_label, 1, i, 1, 1)

        page_box.append(grid)
        self.stack.add_titled(page_box, "variables", "Variables")

    def _build_about_page(self, about_info: dict):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=20, margin_end=20, margin_top=20, margin_bottom=20)
        page_box.set_valign(Gtk.Align.CENTER)
        page_box.set_halign(Gtk.Align.CENTER)

        icon_path = os.path.join(utils.project_root, 'res', 'icons', 'hicolor', '512x512', 'apps', 'pulse_ssh.png')

        if os.path.exists(icon_path):
            icon = Gtk.Image.new_from_file(icon_path)
            icon.set_pixel_size(128)
            page_box.append(icon)

        title_label = Gtk.Label(label="PulseSSH", use_markup=True)
        title_label.add_css_class("title-1")
        page_box.append(title_label)

        version_label = Gtk.Label(label=f"Version {about_info.get('version', 'N/A')}")
        page_box.append(version_label)

        description_label = Gtk.Label(label=about_info.get('description', ''))
        description_label.add_css_class("caption")
        page_box.append(description_label)

        link_button = Gtk.LinkButton(
            uri=about_info.get('website', ''),
            label="Visit Project Website"
        )
        page_box.append(link_button)

        self.stack.add_titled(page_box, "about", "About")

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
        remove_button.connect("clicked", self._on_remove_script_clicked, list_box, row)
        row_box.append(remove_button)

        row.set_child(row_box)
        list_box.append(row)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_script_drop, list_box)
        row.add_controller(drop_target)

    def _create_manual_script_list_page(self, commands: dict):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        for name, command in commands.items():
            self._add_manual_script_row(list_box, name, command)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_height=150)
        scrolled_window.set_child(list_box)
        page_box.append(scrolled_window)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", lambda w: self._add_manual_script_row(list_box))
        button_box.append(add_button)
        page_box.append(button_box)

        return page_box

    def _add_manual_script_row(self, list_box, name="", command=""):
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
        remove_button.connect("clicked", self._on_remove_script_clicked, list_box, row)
        row_box.append(remove_button)

        row.set_child(row_box)
        list_box.append(row)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_script_drop, list_box)
        row.add_controller(drop_target)

    def _on_remove_script_clicked(self, button, list_box, row):
        list_box.remove(row)

    def _on_script_drop(self, target, value, x, y, list_box):
        dragged_row = value
        target_row = target.get_widget()
        if dragged_row != target_row:
            pos = target_row.get_index()
            list_box.remove(dragged_row)
            list_box.insert(dragged_row, pos)
        return True

    def get_data(self) -> app_config.AppConfig:
        font_desc = self.font_chooser.get_font_desc()
        font_size = 12 if font_desc.get_size_is_absolute() else font_desc.get_size() / Pango.SCALE

        on_disconnect = ON_DISCONNECT[self.on_disconnect.get_selected_item().get_string()]
        cursor_shape = CURSOR_SHAPES[self.cursor_shape.get_selected_item().get_string()]
        color_scheme = COLOR_SCHEMES[self.color_scheme.get_selected_item().get_string()]

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

        def get_manual_scripts_from_list(page_box):
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

        return app_config.AppConfig(
            font_family=font_desc.get_family(),
            font_size=int(font_size),
            theme=self.theme.get_selected_item().name,
            cursor_shape=cursor_shape,
            split_at_root=self.split_at_root.get_active(),
            shell_program=self.shell_program.get_model().get_string(self.shell_program.get_selected()),
            on_disconnect_behavior=on_disconnect,
            color_scheme=color_scheme,
            scrollback_lines=int(self.scrollback.get_value()),
            scroll_on_output=self.scroll_on_output.get_active(),
            scroll_on_keystroke=self.scroll_on_keystroke.get_active(),
            scroll_on_insert=self.scroll_on_insert.get_active(),
            scrollbar_visible=self.scrollbar_visible.get_active(),
            sidebar_on_right=self.sidebar_on_right.get_active(),
            audible_bell=self.audible_bell.get_active(),
            ssh_forward_agent=self.ssh_forward_agent.get_active(),
            ssh_compression=self.ssh_compression.get_active(),
            ssh_x11_forwarding=self.ssh_x11_forwarding.get_active(),
            ssh_verbose=self.ssh_verbose.get_active(),
            ssh_force_pty=self.ssh_force_pty.get_active(),
            pre_local_cmds=get_scripts_from_list(self.pre_local_list),
            post_local_cmds=get_scripts_from_list(self.post_local_list),
            post_remote_cmds=get_scripts_from_list(self.post_remote_list),
            remote_scripts=get_scripts_from_list(self.remote_scripts_list),
            post_manual_local_cmds=get_manual_scripts_from_list(self.post_manual_local_list),
            ssh_path=self.ssh_path_entry.get_text(),
            sftp_path=self.sftp_path_entry.get_text(),
            scp_path=self.scp_path_entry.get_text(),
            sshpass_path=self.sshpass_path_entry.get_text(),
            sudo_path=self.sudo_path_entry.get_text(),
        )
