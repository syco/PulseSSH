#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk
from typing import TYPE_CHECKING
import libs.AppConfigDialog as app_config_dialog
import libs.Cluster as cluster
import libs.ClusterDialog as cluster_dialog
import libs.ClusterListItem as cluster_list_item
import libs.Utils as utils

if TYPE_CHECKING:
    from libs.MainWindow import MainWindow
class ClustersView():
    def __init__(self, app_window: "MainWindow"):
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
        self.root_store = Gio.ListStore(item_type=cluster_list_item.ClusterListItem)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)

        self.filter_entry = Gtk.SearchEntry(placeholder_text="Filter clusters...")
        self.filter_entry.connect("search-changed", self.filter_changed_callback)
        self.filter_entry.connect("activate", self.filter_entry_activated_callback)

        self.filter = Gtk.CustomFilter.new(self.filter_list_function)
        filter_model = Gtk.FilterListModel(model=self.root_store, filter=self.filter)
        self.selection_model = Gtk.SingleSelection(model=filter_model)

        self.list_view = Gtk.ListView(model=self.selection_model, factory=factory)
        self.list_view.connect("activate", self.item_activated_callback)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.list_view.add_controller(key_controller)

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

        header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        header_bar.set_title_widget(self.filter_entry)

        toolbar_view = Adw.ToolbarView(content = content)
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.add_bottom_bar(bottom_bar)

        self.populate_tree()

        return toolbar_view

    def open_local_terminal(self, button):
        self.app_window.open_connection_tab(utils.local_connection)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if self.filter_entry.has_focus():
            return Gdk.EVENT_PROPAGATE

        unichar = Gdk.keyval_to_unicode(keyval)
        is_modifier = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK)

        if not is_modifier and unichar and chr(unichar).isprintable():
            self.filter_entry.grab_focus()
            self.filter_entry.set_text(self.filter_entry.get_text() + chr(unichar))
            self.filter_entry.set_position(-1)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def populate_tree(self):
        self.root_store.remove_all()
        for cluster in sorted(self.app_window.clusters.values(), key=lambda c: c.name.lower()):
            self.root_store.append(cluster_list_item.ClusterListItem(cluster))

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
        if not self.selection_model.is_selected(list_item.get_position()):
            self.selection_model.select_item(list_item.get_position(), True)

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
        dlg = cluster_dialog.ClusterDialog(self.app_window, self.app_window.connections)
        dlg.connect("response", self.add_callback)
        dlg.present()

    def add_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            cluster = dialog.get_data()
            self.app_window.clusters[cluster.uuid] = cluster
            utils.save_app_config(self.app_window.config_dir, self.app_window.readonly, self.app_window.app_config, self.app_window.connections, self.app_window.clusters)
            self.populate_tree()
        dialog.destroy()

    def open_edit_modal(self, action, param, cluster_to_edit: cluster.Cluster):
        dlg = cluster_dialog.ClusterDialog(self.app_window, self.app_window.connections, cluster_to_edit)
        dlg.connect("response", self.edit_callback)
        dlg.present()

    def edit_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            new_cluster = dialog.get_data()
            self.app_window.clusters[new_cluster.uuid] = new_cluster
            utils.save_app_config(self.app_window.config_dir, self.app_window.readonly, self.app_window.app_config, self.app_window.connections, self.app_window.clusters)
            self.populate_tree()
        dialog.destroy()

    def open_remove_modal(self, action, param, cluster_to_remove: cluster.Cluster):
        dialog = Adw.MessageDialog(
            transient_for=self.app_window,
            modal=True,
            heading=f"Remove '{cluster_to_remove.name}'?",
            body="Are you sure you want to remove this cluster? This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, res: self.remove_callback(d, res, cluster_to_remove))
        dialog.present()

    def remove_callback(self, dialog, response_id, cluster):
        if response_id == "remove":
            if cluster.uuid in self.app_window.clusters:
                del self.app_window.clusters[cluster.uuid]
            utils.save_app_config(self.app_window.config_dir, self.app_window.readonly, self.app_window.app_config, self.app_window.connections, self.app_window.clusters)
            self.populate_tree()
        dialog.destroy()

    def open_appconfig_modal(self, button):
        dlg = app_config_dialog.AppConfigDialog(self.app_window, self.app_window.app_config, self.app_window.about_info)
        dlg.connect("response", self.appconfig_dialog_callback)
        dlg.present()

    def appconfig_dialog_callback(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK or response_id == Gtk.ResponseType.APPLY:
            self.app_window.app_config = dialog.get_data()
            utils.save_app_config(self.app_window.config_dir, self.app_window.readonly, self.app_window.app_config, self.app_window.connections, self.app_window.clusters)
            self.app_window.apply_config_settings()
            for terminal in self.app_window._find_all_terminals_in_widget(self.app_window.notebook):
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

    def open_cluster_in_tab(self, action, param, cluster: cluster.Cluster):
        conns_to_start = [self.app_window.connections[uuid] for uuid in cluster.connection_uuids if uuid in self.app_window.connections]

        if not conns_to_start:
            self.app_window.toast_overlay.add_toast(Adw.Toast.new("Cluster has no valid connections."))
            return

        self.app_window.open_all_connections_split(None, None, conns_to_start, True, cluster.name) if cluster.open_mode == "split" else self.app_window.open_all_connections_in_tabs(None, None, conns_to_start, True, cluster.name)

        self.filter_entry.set_text("")
