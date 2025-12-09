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
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.dialogs.AppConfigDialog as _app_config_dialog
import pulse_ssh.gui.dialogs.ConnectionDialog as _connection_dialog
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.views.list_items.ConnectionListItem as _connection_list_item
import pulse_ssh.Utils as _utils

class ConnectionsView():
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window

    def setup_list_item(self, factory, list_item):
        icon = Gtk.Image()
        label = Gtk.Label(xalign=0)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(icon)
        box.append(label)

        expander = Gtk.TreeExpander()
        expander.set_child(box)
        list_item.set_child(expander)

        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(Gdk.BUTTON_SECONDARY)

        click_gesture.connect("pressed", self.build_menu, list_item)
        expander.add_controller(click_gesture)

    def create_submodel(self, item: _connection_list_item.ConnectionListItem):
        return item.children_store

    def bind_list_item(self, factory, list_item):
        expander = list_item.get_child()
        tree_row = list_item.get_item()
        node = tree_row.get_item()

        icon = expander.get_child().get_first_child()
        label = icon.get_next_sibling()

        icon.set_from_icon_name(node.icon_name)
        label.set_text(node.name)
        expander.set_list_row(tree_row)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        expander.add_controller(drag_source)

        drag_source.connect("prepare", self.item_dragged_callback)

        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        expander.add_controller(drop_target)

        drop_target.connect("drop", lambda target, value, x, y: self.item_dropped_callback(target, value, x, y, list_item))

    def getAdwToolbarView(self) -> Adw.ToolbarView:
        self.root_store = Gio.ListStore.new(_connection_list_item.ConnectionListItem)

        self.tree_store = Gtk.TreeListModel.new(
            root=self.root_store,
            passthrough=False,
            autoexpand=True,
            create_func=self.create_submodel
        )

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)

        self.filter_entry = Gtk.SearchEntry(placeholder_text="Filter connections...")
        self.filter_entry.connect("search-changed", self.filter_changed_callback)
        self.filter_entry.connect("activate", self.filter_entry_activated_callback)
        self.filter_entry.set_hexpand(True)

        self.filter = Gtk.CustomFilter.new(self.filter_list_function)
        self.filter_model = Gtk.FilterListModel(model=self.tree_store, filter=self.filter)
        self.selection_model = Gtk.MultiSelection(model=self.filter_model)

        self.list_view = Gtk.ListView(model=self.selection_model, factory=factory)
        self.list_view.connect("activate", self.item_activated_callback)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.list_view.add_controller(key_controller)

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_filter_focus_changed)
        self.filter_entry.add_controller(focus_controller)

        filter_key_controller = Gtk.EventControllerKey()
        filter_key_controller.connect("key-pressed", self._on_filter_entry_key_pressed)
        self.filter_entry.add_controller(filter_key_controller)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scrolled_window.set_child(self.list_view)

        bottom_bar = Adw.HeaderBar(show_title = False, show_start_title_buttons=False, show_end_title_buttons=False)
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.connect("clicked", self.open_add_modal)
        bottom_bar.pack_start(add_btn)

        config_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        config_btn.connect("clicked", self.open_appconfig_modal)
        bottom_bar.pack_end(config_btn)

        local_term_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
        local_term_btn.connect("clicked", self.open_local_terminal)
        bottom_bar.pack_end(local_term_btn)

        self.filter_header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        self.filter_header_bar.set_title_widget(self.filter_entry)
        self.filter_header_bar.set_visible(False)

        toolbar_view = Adw.ToolbarView(content = scrolled_window)
        toolbar_view.add_top_bar(self.filter_header_bar)
        toolbar_view.add_bottom_bar(bottom_bar)

        for conn in sorted(_globals.connections.values(), key=_utils.connectionsSortFunction):
            self.insert_entry(conn)

        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        return toolbar_view

    def find_folder(self, parent_gio_list_store: Gio.ListStore, folder_name: str, create: bool = False) -> _connection_list_item.ConnectionListItem | None:
        for i in range(parent_gio_list_store.get_n_items()):
            item = parent_gio_list_store.get_item(i)
            if item and item.name == folder_name and item.children_store:
                return item

        if not create:
            return None

        folder_item = _connection_list_item.ConnectionListItem(folder_name, None)
        parent_gio_list_store.append(folder_item)
        return folder_item

    def insert_entry(self, conn: _connection.Connection):
        current_gio_list_store = self.root_store
        if conn.folder:
            for part in conn.folder.split('/'):
                folder_item = self.find_folder(current_gio_list_store, part, True)
                current_gio_list_store = folder_item.children_store

        listItem = _connection_list_item.ConnectionListItem(conn.name, conn.uuid)
        if current_gio_list_store is not None:
            current_gio_list_store.append(listItem)

    def find_entry(self, current_gio_list_store: Gio.ListStore, conn: _connection.Connection):
        if conn.folder:
            for part in conn.folder.split('/'):
                folder_item = self.find_folder(current_gio_list_store, part, False)
                if folder_item and folder_item.children_store:
                    current_gio_list_store = folder_item.children_store
                else:
                    return None, None

        for i in range(current_gio_list_store.get_n_items()):
            item = current_gio_list_store.get_item(i)
            if item and item.conn_uuid == conn.uuid:
                return item, current_gio_list_store

        return None, None

    def delete_entry(self, conn: _connection.Connection):
        item, store, index = self._find_item_by_uuid(self.root_store, conn.uuid)
        if store and index is not None:
            store.remove(index)

    def open_local_terminal(self, button):
        _gui_globals.layout_manager.open_connection_tab(_utils.local_connection)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if self.filter_entry.has_focus():
            return Gdk.EVENT_PROPAGATE

        unichar = Gdk.keyval_to_unicode(keyval)
        is_modifier = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK)

        if not is_modifier and unichar and chr(unichar).isprintable():
            self.filter_header_bar.set_visible(True)
            self.filter_entry.grab_focus()
            self.filter_entry.set_text(self.filter_entry.get_text() + chr(unichar))
            self.filter_entry.set_position(-1)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _on_filter_focus_changed(self, controller):
        if not self.filter_entry.get_text():
            self.filter_header_bar.set_visible(False)

    def _on_filter_entry_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.filter_entry.set_text("")
            self.filter_header_bar.set_visible(False)
            self.list_view.grab_focus()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def filter_changed_callback(self, entry):
        if self.filter:
            self.filter.changed(Gtk.FilterChange.DIFFERENT)
            GLib.idle_add(self.select_first_item)

    def select_first_item(self):
        self.selection_model.unselect_all()
        self.selection_model.select_item(0, True)
        for x in range(self.filter_model.get_n_items()):
            item = self.filter_model.get_item(x)
            conn_item = item.get_item()
            if conn_item.conn_uuid:
                self.selection_model.select_item(x, True)
                self.list_view.scroll_to(x, Gtk.ListScrollFlags.FOCUS, None)
                break
        return GLib.SOURCE_REMOVE

    def filter_entry_activated_callback(self, entry):
        selection = self.selection_model.get_selection()
        if selection.get_size() == 0:
            return

        position = selection.get_nth(0)
        tree_row = self.filter_model.get_item(position)
        if not tree_row:
            return

        node = tree_row.get_item()
        if node and node.conn_uuid:
            _gui_globals.layout_manager.open_connection_tab(_globals.connections[node.conn_uuid])
            self.filter_entry.set_text("")

    def filter_list_function(self, item):
        search_text = self.filter_entry.get_text().lower()
        if not search_text:
            return True

        conn_item = item.get_item()

        def check_item_and_children(current_item):
            if search_text in current_item.name.lower():
                return True

            if current_item.conn_uuid:
                conn = _globals.connections.get(current_item.conn_uuid)
                if conn and conn.folder and search_text in conn.folder.lower():
                    return True
                if conn and conn.host and search_text in conn.host.lower():
                    return True

            if current_item.children_store:
                for i in range(current_item.children_store.get_n_items()):
                    child_item = current_item.children_store.get_item(i)
                    if check_item_and_children(child_item):
                        return True
            return False

        return check_item_and_children(conn_item)

    def build_menu(self, gesture, n_press, x, y, list_item):
        cur_position = list_item.get_position()
        if not self.selection_model.is_selected(cur_position):
            self.selection_model.unselect_all()
            self.selection_model.select_item(cur_position, True)
            self.list_view.scroll_to(cur_position, Gtk.ListScrollFlags.FOCUS, None)

        selection_bitset = self.selection_model.get_selection()

        menu_model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        gesture.get_widget().insert_action_group("list", action_group)

        selected_conns = []

        def collect_connections_recursive(item):
            if item.conn_uuid:
                if conn := _globals.connections.get(item.conn_uuid):
                    selected_conns.append(conn)
            elif item.children_store:
                for i in range(item.children_store.get_n_items()):
                    collect_connections_recursive(item.children_store.get_item(i))

        for i in range(selection_bitset.get_size()):
            pos = selection_bitset.get_nth(i)
            tree_list_row = self.selection_model.get_model().get_item(pos)
            if tree_list_row and tree_list_row.get_item():
                collect_connections_recursive(tree_list_row.get_item())

        if not selected_conns:
            return

        def create_action(name, callback, *args):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback, *args)
            action_group.add_action(action)

        if len(selected_conns) == 1:
            create_action("open_tab", self.app_window.open_all_connections_in_tabs, selected_conns)
            menu_model.append("Open in new tab", "list.open_tab")

            create_action("edit", self.open_edit_modal, selected_conns[0])
            menu_model.append("Edit Connection", "list.edit")

            create_action("clone", self.clone_connection, selected_conns[0])
            menu_model.append("Clone Connection", "list.clone")

            create_action("remove", self.open_remove_modal, selected_conns[0])
            menu_model.append("Remove Connection", "list.remove")
        else:
            open_all_submenu = Gio.Menu()

            create_action("open_tabs", self.app_window.open_all_connections_in_tabs, selected_conns)
            open_all_submenu.append("In tabs", "list.open_tabs")

            create_action("open_split", self.app_window.open_all_connections_split, selected_conns)
            open_all_submenu.append("In split", "list.open_split")

            create_action("open_clustered_tabs", self.app_window.open_all_connections_in_tabs, selected_conns, True)
            open_all_submenu.append("In clustered tabs", "list.open_clustered_tabs")

            create_action("open_clustered_split", self.app_window.open_all_connections_split, selected_conns, True)
            open_all_submenu.append("In clustered split", "list.open_clustered_split")

            menu_model.append_submenu("Open All", open_all_submenu)

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(gesture.get_widget())
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def item_dragged_callback(self, source, x, y):
        uuids_to_drag = []
        selection = self.selection_model.get_selection()
        for i in range(selection.get_size()):
            pos = selection.get_nth(i)
            tree_row = self.tree_store.get_item(pos)
            item = tree_row.get_item()
            if item.conn_uuid:
                uuids_to_drag.append(item.conn_uuid)
            else:
                uuids_to_drag.append(item.name)

        if not uuids_to_drag:
            return None

        data_string = "\n".join(uuids_to_drag)
        return Gdk.ContentProvider.new_for_value(data_string)

    def item_dropped_callback(self, target, value, x, y, list_item_widget):
        tree_row = list_item_widget.get_item()
        target_node = tree_row.get_item()

        target_folder = None
        if target_node.conn_uuid:
            if conn := _globals.connections.get(target_node.conn_uuid):
                target_folder = conn.folder
        else:
            target_folder = target_node.name

        dragged_conn_uuids = value.split('\n')
        for uuid_str in dragged_conn_uuids:
            dragged_conn = _globals.connections.get(uuid_str)

            if dragged_conn:
                self.delete_entry(dragged_conn)
                dragged_conn.folder = target_folder if target_folder else ""
                self.insert_entry(dragged_conn)
            else:
                move_folder = uuid_str.split('/')[-1]
                for conn in _globals.connections.values():
                    if conn.folder.startswith(uuid_str):
                        self.delete_entry(conn)
                        conn.folder = (f"{target_folder if target_folder else ""}/{move_folder}").strip().strip('/').replace('//', '/')
                        self.insert_entry(conn)

        _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)

        return True

    def open_add_modal(self, button):
        dlg = _connection_dialog.ConnectionDialog(self.app_window)
        dlg.connect("response", self.add_callback)
        dlg.present()

    def add_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            conn = dialog.get_data()
            _globals.connections[conn.uuid] = conn
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
            self.insert_entry(conn)
        dialog.destroy()

    def edit_selected_entry(self):
        selection = self.selection_model.get_selection()
        if selection.get_size() != 1:
            return

        pos = selection.get_nth(0)
        tree_row = self.selection_model.get_model().get_item(pos)
        if not tree_row:
            return

        node = tree_row.get_item()
        if node and node.conn_uuid:
            self.open_edit_modal(None, None, node.conn_uuid)

    def open_edit_modal(self, action, param, conn_to_edit: _connection.Connection):
        dlg = _connection_dialog.ConnectionDialog(self.app_window, conn_to_edit)
        dlg.connect("response", self.edit_callback)
        dlg.present()

    def edit_callback(self, dialog, response_id, *args):
        if response_id == Gtk.ResponseType.OK:
            new_conn: _connection.Connection = dialog.get_data()
            self.delete_entry(_globals.connections[new_conn.uuid])
            _globals.connections[new_conn.uuid] = new_conn
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
            self.insert_entry(new_conn)
        dialog.destroy()
        self.conn_to_edit = None

    def clone_connection(self, action, param, conn_to_clone: _connection.Connection):
        clone = conn_to_clone.get_cloned_connection()
        clone.name = f"Copy of {conn_to_clone.name}"
        _globals.connections[clone.uuid] = clone
        _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
        self.insert_entry(clone)

        self.open_edit_modal(None, None, _globals.connections[clone.uuid])

    def open_remove_modal(self, action, param, conn_to_remove: _connection.Connection):
        dialog = Adw.MessageDialog(
            transient_for=self.app_window,
            modal=True,
            heading=f"Remove '{conn_to_remove.name}'?",
            body="Are you sure you want to remove this connection? This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.remove_callback, conn_to_remove)
        dialog.present()

    def remove_callback(self, dialog, response_id, conn):
        if response_id == "remove":
            if conn.uuid in _globals.connections:
                self.delete_entry(_globals.connections[conn.uuid])
                del _globals.connections[conn.uuid]
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
        dialog.destroy()

    def open_appconfig_modal(self, button):
        dlg = _app_config_dialog.AppConfigDialog(self.app_window, _globals.app_config, _globals.about_info)
        dlg.connect("response", self.appconfig_dialog_callback)
        dlg.present()

    def appconfig_dialog_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK or response_id == Gtk.ResponseType.APPLY:
            _globals.app_config = dialog.get_data()
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
            self.app_window.apply_config_settings()
            for notebook in _gui_globals.all_notebooks:
                for terminal in self.app_window._find_all_terminals_in_widget(notebook):
                    terminal.apply_theme()

        if response_id == Gtk.ResponseType.OK or response_id == Gtk.ResponseType.CANCEL:
            dialog.destroy()

    def select_connection_from_terminal(self, terminal):
        if not terminal or not hasattr(terminal, 'pulse_conn') or not terminal.pulse_conn:
            self.selection_model.unselect_all()
            return

        conn_uuid = terminal.pulse_conn.uuid
        if conn_uuid == "local":
            self.selection_model.unselect_all()
            return

        item, _, _ = self._find_item_by_uuid(self.root_store, conn_uuid)

        if not item:
            self.selection_model.unselect_all()
            return

        for i in range(self.filter_model.get_n_items()):
            tree_row = self.filter_model.get_item(i)
            if tree_row and tree_row.get_item() == item:
                parent_row = tree_row.get_parent()
                while parent_row:
                    parent_row.set_expanded(True)
                    parent_row = parent_row.get_parent()

                self.selection_model.unselect_all()
                self.selection_model.select_item(i, True)
                self.list_view.scroll_to(i, Gtk.ListScrollFlags.FOCUS, None)
                return

        self.selection_model.unselect_all()

    def _find_item_by_uuid(self, store: Gio.ListStore, uuid_to_find: str):
        """Recursively finds an item by its UUID in the data stores."""
        for i in range(store.get_n_items()):
            item = store.get_item(i)
            if item.conn_uuid == uuid_to_find:
                return item, store, i
            if item.children_store:
                found_item, found_store, found_index = self._find_item_by_uuid(item.children_store, uuid_to_find)
                if found_item:
                    return found_item, found_store, found_index
        return None, None, None

    def item_activated_callback(self, list_view, position):
        selection = self.selection_model.get_selection()
        opened_connection = False
        for i in range(selection.get_size()):
            pos = selection.get_nth(i)
            tree_row = self.selection_model.get_model().get_item(pos)
            if tree_row:
                node = tree_row.get_item()
                if node.children_store:
                    tree_row.set_expanded(not tree_row.get_expanded())
                if node and node.conn_uuid:
                    _gui_globals.layout_manager.open_connection_tab(_globals.connections[node.conn_uuid])
                    opened_connection = True
        if opened_connection:
            self.filter_entry.set_text("")
