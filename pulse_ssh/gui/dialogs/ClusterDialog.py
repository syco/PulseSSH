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
from typing import Dict
from typing import Optional
import pulse_ssh.Utils as utils
import pulse_ssh.data.Cluster as cluster
import pulse_ssh.data.Connection as connection

class ConnectionCheckListItem(GObject.Object):
    def __init__(self, connection: connection.Connection, check_button: Gtk.CheckButton):
        super().__init__()
        self.connection = connection
        self.check_button = check_button

class ClusterDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int,))
    }

    def __init__(self, parent, connections: Dict[str, connection.Connection], cluster: Optional[cluster.Cluster] = None):
        super().__init__(title="Cluster Configuration", transient_for=parent, modal=True)
        screen_height = Gdk.Display.get_default().get_primary_monitor().get_geometry().height
        self.set_default_size(700, screen_height / 1.3)

        self.cluster = cluster
        self.connections = connections

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.CANCEL))

        ok_button = Gtk.Button.new_with_mnemonic("_OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.OK))

        self.set_default_widget(ok_button)

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

        if is_enter and not is_ctrl:
            self.emit("response", Gtk.ResponseType.OK)
            return True

    def filter_changed_callback(self, entry):
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def _build_ui(self):
        page = Adw.PreferencesPage()

        general_group = Adw.PreferencesGroup(title="General")
        page.add(general_group)

        self.name_entry = Adw.EntryRow(title="Name", text=self.cluster.name if self.cluster else "")
        general_group.add(self.name_entry)

        self.open_mode_dropdown = Adw.ComboRow(title="Open Mode", model=Gtk.StringList.new(["In Tabs", "In Split"]))
        if self.cluster and self.cluster.open_mode == "split":
            self.open_mode_dropdown.set_selected(1)
        else:
            self.open_mode_dropdown.set_selected(0)
        general_group.add(self.open_mode_dropdown)

        connections_group = Adw.PreferencesGroup(title="Connections")
        page.add(connections_group)

        self.connections_store = Gio.ListStore(item_type=ConnectionCheckListItem)
        checked_uuids = self.cluster.connection_uuids if self.cluster else []
        for conn in sorted(self.connections.values(), key=utils.connectionsSortFunction):
            check_button = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            check_button.set_active(conn.uuid in checked_uuids)
            self.connections_store.append(ConnectionCheckListItem(conn, check_button))

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)

        self.filter_entry = Gtk.SearchEntry(placeholder_text="Filter connections...")
        self.filter_entry.connect("search-changed", self.filter_changed_callback)
        self.filter_entry.connect("activate", self.filter_entry_activated_callback)

        self.filter = Gtk.CustomFilter.new(self.filter_list_function)
        self.filtered_model = Gtk.FilterListModel(model=self.connections_store, filter=self.filter)
        self.selection_model = Gtk.NoSelection(model=self.filtered_model)

        self.list_view = Gtk.ListView(model=self.selection_model, factory=factory)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scrolled_window.set_child(self.list_view)

        select_all_check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
        select_all_check.connect("toggled", self._on_select_all_toggled)

        filter_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_bottom=6)
        filter_row.set_homogeneous(False)
        filter_row.append(self.filter_entry)
        filter_row.append(select_all_check)

        self.filter_entry.set_hexpand(True)
        select_all_check.set_margin_end(18)
        select_all_check.set_tooltip_text("Select/Deselect All Connections")

        connections_group.add(filter_row)
        connections_group.add(scrolled_window)

        return page

    def setup_list_item(self, factory, list_item):
        row = Adw.ActionRow()
        list_item.row = row
        list_item.set_child(row)

    def bind_list_item(self, factory, list_item):
        row = list_item.row
        item = list_item.get_item()
        check_button = item.check_button

        if row.get_activatable_widget():
            row.remove(row.get_activatable_widget())

        conn = item.connection
        label_text = conn.name
        if conn.folder:
            label_text = f"{conn.folder}/{conn.name}"
        row.set_title(GLib.markup_escape_text(label_text))
        row.add_suffix(check_button)
        row.set_activatable_widget(check_button)

    def _on_select_all_toggled(self, check_button):
        for i in range(self.selection_model.get_n_items()):
            item = self.selection_model.get_item(i)
            if item:
                item.check_button.set_active(False)

        is_active = check_button.get_active()
        if is_active:
            for i in range(self.filtered_model.get_n_items()):
                item = self.filtered_model.get_item(i)
                if item:
                    item.check_button.set_active(True)

        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def filter_entry_activated_callback(self, entry):
        selection = self.selection_model.get_selection()
        if selection.get_size() == 0:
            return

        position = selection.get_nth(0)
        tree_row = self.filter_model.get_item(position)
        if not tree_row:
            return

        node = tree_row.get_item()
        if node and node.connection_data:
            self.app_window.open_connection_tab(node.connection_data)
            self.filter_entry.set_text("")

    def filter_list_function(self, item):
        search_text = self.filter_entry.get_text().lower()
        if not search_text:
            return True

        conn = item.connection
        full_name = conn.name.lower()
        if conn.folder:
            full_name = f"{conn.folder.lower()}/{full_name}"

        return search_text in full_name

    def get_data(self) -> cluster.Cluster:
        selected_uuids = []
        for i in range(self.connections_store.get_n_items()):
            item = self.connections_store.get_item(i)
            if item.check_button.get_active():
                selected_uuids.append(item.connection.uuid)

        open_mode_str = self.open_mode_dropdown.get_selected_item().get_string()
        open_mode = "split" if open_mode_str == "In Split" else "tabs"

        new_cluster = cluster.Cluster(
            name=self.name_entry.get_text().strip(),
            connection_uuids=selected_uuids,
            open_mode=open_mode
        )

        if self.cluster and hasattr(self.cluster, 'uuid'):
            new_cluster.uuid = self.cluster.uuid

        return new_cluster
