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
from gi.repository import Gtk  # type: ignore
import pulse_ssh.data.Cluster as _cluster
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.dialogs.AppConfigDialog as _app_config_dialog
import pulse_ssh.gui.dialogs.ClusterDialog as _cluster_dialog
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.views.list_items.ClusterListItem as _cluster_list_item
import pulse_ssh.Utils as _utils

class ClustersView():
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window

    def setup_list_item(self, factory, list_item):
        icon = Gtk.Image()
        label = Gtk.Label(xalign=0)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(icon)
        box.append(label)

        click_gesture = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click_gesture.connect("pressed", self.build_menu, list_item)
        box.add_controller(click_gesture)

        list_item.set_child(box)

    def bind_list_item(self, factory, list_item):
        box = list_item.get_child()
        icon = box.get_first_child()
        label = icon.get_next_sibling()
        item = list_item.get_item()
        icon.set_from_icon_name(item.icon_name)
        label.set_text(item.name)

    def getAdwToolbarView(self) -> Adw.ToolbarView:
        self.root_store = Gio.ListStore(item_type=_cluster_list_item.ClusterListItem)

        expression = Gtk.PropertyExpression.new(_cluster_list_item.ClusterListItem, None, "name")
        sorter = Gtk.StringSorter.new(expression)
        self.sorted_model = Gtk.SortListModel.new(self.root_store, sorter)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)

        self.filter_entry = Gtk.SearchEntry(placeholder_text="Filter clusters...")
        self.filter_entry.connect("search-changed", self.filter_changed_callback)
        self.filter_entry.connect("activate", self.filter_entry_activated_callback)
        self.filter_entry.set_hexpand(True)

        self.filter = Gtk.CustomFilter.new(self.filter_list_function)
        filter_model = Gtk.FilterListModel(model=self.sorted_model, filter=self.filter)
        self.selection_model = Gtk.SingleSelection(model=filter_model)

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

        content = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        content.set_child(self.list_view)

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

        toolbar_view = Adw.ToolbarView(content = content)
        toolbar_view.add_top_bar(self.filter_header_bar)
        toolbar_view.add_bottom_bar(bottom_bar)

        self.populate_tree()

        return toolbar_view

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

    def populate_tree(self):
        self.root_store.remove_all()
        for cluster in _globals.clusters.values():
            self.root_store.append(_cluster_list_item.ClusterListItem(cluster))

    def filter_changed_callback(self, entry):
        if self.filter:
            self.filter.changed(Gtk.FilterChange.DIFFERENT)
            GLib.idle_add(self.select_first_item)

    def select_first_item(self):
        if self.selection_model.get_model().get_n_items() > 0:
            self.selection_model.select_item(0, True)
            self.list_view.scroll_to(0, Gtk.ListScrollFlags.FOCUS, None)
        else:
            self.selection_model.unselect_all()
        return GLib.SOURCE_REMOVE

    def filter_entry_activated_callback(self, entry):
        selected_pos = self.selection_model.get_selected()
        if selected_pos == Gtk.INVALID_LIST_POSITION:
            return

        item = self.selection_model.get_selected_item()
        if item:
            self.open_cluster_in_tab(None, None, item.cluster_data)

    def filter_list_function(self, item):
        search_text = self.filter_entry.get_text().lower()
        if not search_text:
            return True

        if search_text in item.name.lower():
            return True

        return False

    def build_menu(self, gesture, n_press, x, y, list_item):
        cur_position = list_item.get_position()
        if not self.selection_model.is_selected(cur_position):
            self.selection_model.unselect_all()
            self.selection_model.select_item(cur_position, True)
            self.list_view.scroll_to(cur_position, Gtk.ListScrollFlags.FOCUS, None)

        item = list_item.get_item()
        if not item:
            return

        cluster_to_act_on = item.cluster_data

        menu_model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        gesture.get_widget().insert_action_group("cluster", action_group)

        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self.open_cluster_in_tab, cluster_to_act_on)
        action_group.add_action(open_action)
        menu_model.append("Open Cluster", "cluster.open")

        edit_action = Gio.SimpleAction.new("edit", None)
        edit_action.connect("activate", self.open_edit_modal, cluster_to_act_on)
        action_group.add_action(edit_action)
        menu_model.append("Edit Cluster", "cluster.edit")

        remove_action = Gio.SimpleAction.new("remove", None)
        remove_action.connect("activate", self.open_remove_modal, cluster_to_act_on)
        action_group.add_action(remove_action)
        menu_model.append("Remove Cluster", "cluster.remove")

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(gesture.get_widget())
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def open_add_modal(self, button):
        dlg = _cluster_dialog.ClusterDialog(self.app_window, _globals.connections)
        dlg.connect("response", self.add_callback)
        dlg.present()

    def add_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            cluster = dialog.get_data()
            _globals.clusters[cluster.uuid] = cluster
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
            self.populate_tree()
        dialog.destroy()

    def edit_selected_entry(self):
        selected_pos = self.selection_model.get_selected()
        if selected_pos == Gtk.INVALID_LIST_POSITION:
            return

        item = self.selection_model.get_selected_item()
        if not item:
            return

        cluster_to_edit = item.cluster_data
        self.open_edit_modal(None, None, cluster_to_edit)

    def open_edit_modal(self, action, param, cluster_to_edit: _cluster.Cluster):
        dlg = _cluster_dialog.ClusterDialog(self.app_window, _globals.connections, cluster_to_edit)
        dlg.connect("response", self.edit_callback)
        dlg.present()

    def edit_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            new_cluster = dialog.get_data()
            _globals.clusters[new_cluster.uuid] = new_cluster
            _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
            self.populate_tree()
        dialog.destroy()

    def open_remove_modal(self, action, param, cluster_to_remove: _cluster.Cluster):
        def remove_callback( dialog, response_id, cluster):
            if response_id == "remove":
                if cluster.uuid in _globals.clusters:
                    del _globals.clusters[cluster.uuid]
                _utils.save_app_config(_globals.config_dir, _globals.readonly, _globals.app_config, _globals.connections, _globals.clusters)
                self.populate_tree()
            dialog.destroy()

        dialog = Adw.MessageDialog(
            transient_for=self.app_window,
            modal=True,
            heading=f"Remove '{cluster_to_remove.name}'?",
            body="Are you sure you want to remove this cluster? This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, res: remove_callback(d, res, cluster_to_remove))
        dialog.present()

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

    def item_activated_callback(self, list_view, position):
        selection_model = list_view.get_model()
        item = selection_model.get_item(position)
        if not item:
            return

        cluster = item.cluster_data

        self.open_cluster_in_tab(None, None, cluster)

    def open_cluster_in_tab(self, action, param, cluster: _cluster.Cluster):
        conns_to_start = [_globals.connections[uuid] for uuid in cluster.connection_uuids if uuid in _globals.connections]

        if not conns_to_start:
            self.app_window.toast_overlay.add_toast(Adw.Toast.new("Cluster has no valid connections."))
            return

        if cluster.open_mode == "split":
            self.app_window.open_all_connections_split(None, None, conns_to_start, True, cluster.uuid, cluster.name)
        else:
            self.app_window.open_all_connections_in_tabs(None, None, conns_to_start, True, cluster.uuid, cluster.name)

        self.filter_entry.set_text("")
