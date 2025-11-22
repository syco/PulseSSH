#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from typing import Dict
from typing import Optional
import libs.Cluster as cluster
import libs.Connection as connection

class ConnectionCheckListItem(GObject.Object):
    def __init__(self, connection: connection.Connection, is_checked: bool):
        super().__init__()
        self.connection = connection
        self.is_checked = is_checked

class ClusterDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int,))
    }

    def __init__(self, parent, connections: Dict[str, connection.Connection], cluster: Optional[cluster.Cluster] = None):
        super().__init__(title="Cluster Configuration", transient_for=parent, modal=True)
        self.set_default_size(400, 500)

        self.cluster = cluster
        self.connections = connections

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.CANCEL))

        ok_button = Gtk.Button.new_with_mnemonic("_OK")
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.OK))

        self.set_default_widget(ok_button)
        ok_button.grab_focus()

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

    def on_filter_changed(self, entry):
        """Called when the filter entry text changes."""
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
        for conn in sorted(self.connections.values(), key=lambda c: c.name.lower()):
            self.connections_store.append(ConnectionCheckListItem(conn, conn.uuid in checked_uuids))

        self.filter = Gtk.CustomFilter.new(self._filter_func)
        self.filtered_model = Gtk.FilterListModel(model=self.connections_store, filter=self.filter)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_conn_list_item)
        factory.connect("bind", self._bind_conn_list_item)

        selection_model = Gtk.NoSelection(model=self.filtered_model)
        list_view = Gtk.ListView(model=selection_model, factory=factory)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_height=200)
        scrolled_window.set_child(list_view)

        grid.attach(Gtk.Label(label="Connections", xalign=0, valign=Gtk.Align.START), 0, 3, 1, 1)
        grid.attach(scrolled_window, 1, 3, 1, 1)

        self.filter_entry = Gtk.SearchEntry(placeholder_text="Filter connections...")
        self.filter_entry.connect("search-changed", self.on_filter_changed)
        filter_row = Adw.ActionRow(title="Filter")
        filter_row.add_suffix(self.filter_entry)
        connections_group.add(filter_row)
        connections_group.add(scrolled_window)

        return page

    def _setup_conn_list_item(self, factory, list_item):
        row = Adw.ActionRow()
        list_item.set_child(row)

    def _bind_conn_list_item(self, factory, list_item):
        row = list_item.get_child()
        item = list_item.get_item()

        conn = item.connection
        label_text = conn.name
        if conn.folder:
            label_text = f"{conn.folder}/{conn.name}"
        row.set_title(label_text)

        check_button = Gtk.CheckButton()
        check_button.set_active(item.is_checked)
        check_button.set_valign(Gtk.Align.CENTER)
        row.add_suffix(check_button)
        row.set_activatable_widget(check_button)

        check_button.connect("toggled", self._on_check_button_toggled, item)

    def _on_check_button_toggled(self, check_button, item):
        item.is_checked = check_button.get_active()

    def _filter_func(self, item):
        """The filter function for the connections list."""
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
            if item.is_checked:
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
