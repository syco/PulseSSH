#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')

from gi.repository import Adw
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import Pango
from typing import TYPE_CHECKING
import libs.AppConfigDialog as app_config_dialog
import libs.CommandHistoryItem as command_history_item
import libs.Utils as utils

if TYPE_CHECKING:
    from libs.MainWindow import MainWindow
class CommandsHistoryView():
    def __init__(self, app_window: "MainWindow"):
        super().__init__()
        self.app_window = app_window

    def setup_list_item(self, factory, list_item):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, margin_start=6, margin_end=6, margin_top=6, margin_bottom=6)
        list_item.set_child(box)

    def create_submodel(self, item: command_history_item.CommandHistoryItem):
        return item.children_store

    def bind_list_item(self, factory, list_item):
        tree_row = list_item.get_item()
        node = tree_row.get_item()

        if node.children_store:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            label = Gtk.Label(xalign=0, label=node.command)
            box.append(icon)
            box.append(label)

            expander = Gtk.TreeExpander()
            expander.set_child(box)
            expander.set_list_row(tree_row)
            list_item.set_child(expander)
        else:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, margin_start=6, margin_end=6, margin_top=6, margin_bottom=6)
            top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic" if node.ok else "emblem-error-symbolic")
            cmd_label = Gtk.Label(xalign=0, label=node.command)
            top_box.append(status_icon)
            top_box.append(cmd_label)

            time_str = node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            details_label = Gtk.Label(xalign=0, label=f"@ {time_str}")
            details_label.add_css_class("caption")

            box.append(top_box)
            box.append(details_label)
            list_item.set_child(box)

    def getAdwToolbarView(self) -> Adw.ToolbarView:
        self.root_store = Gio.ListStore(item_type=command_history_item.CommandHistoryItem)

        tree_store = Gtk.TreeListModel.new(
            root=self.root_store,
            passthrough=False,
            autoexpand=False,
            create_func=self.create_submodel
        )

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)

        list_view = Gtk.ListView(model=Gtk.NoSelection(model=tree_store), factory=factory)
        list_view.connect("activate", self.item_activated_callback)

        content = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        content.set_child(list_view)

        bottom_bar = Adw.HeaderBar(show_title = False, show_start_title_buttons=False, show_end_title_buttons=False)
        clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic")
        clear_btn.set_tooltip_text("Clear History")
        clear_btn.connect("clicked", self.clear_history_callback)
        bottom_bar.pack_start(clear_btn)

        history_config_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        history_config_btn.connect("clicked", self.open_appconfig_modal)
        bottom_bar.pack_end(history_config_btn)

        local_term_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
        local_term_btn.connect("clicked", self.open_local_terminal)
        bottom_bar.pack_end(local_term_btn)

        toolbar_view = Adw.ToolbarView(content = content)
        toolbar_view.add_bottom_bar(bottom_bar)

        self.populate_tree()

        return toolbar_view

    def open_local_terminal(self, button):
        self.app_window.open_connection_tab(utils.local_connection)

    def populate_tree(self):
        self.root_store.remove_all()

        for conn_uuid, conn_history in self.app_window.command_history.items():
            conn = self.app_window.connections.get(conn_uuid)
            if not conn: continue
            new_store = Gio.ListStore(item_type=command_history_item.CommandHistoryItem)
            for history_item in conn_history:
                new_store.append(history_item)
            folder_item = command_history_item.CommandHistoryItem(conn.name, None, None, False, children_store=new_store)
            self.root_store.append(folder_item)

    def clear_history_callback(self, button):
        self.app_window.command_history.clear()
        self.root_store.remove_all()

    def item_activated_callback(self, list_view, position):
        tree_row = list_view.get_model().get_item(position)
        if not tree_row:
            return

        node = tree_row.get_item()

        if node.children_store:
            tree_row.set_expanded(not tree_row.get_expanded())
            return

        for i in range(self.app_window.notebook.get_n_pages()):
            page = self.app_window.notebook.get_nth_page(i)
            if hasattr(page, 'pulse_history_uuid') and page.pulse_history_uuid == node.uuid:
                self.app_window.notebook.set_selected_page(page)
                return

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        text_view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        text_buffer = text_view.get_buffer()

        stdout_tag = text_buffer.create_tag("stdout_title", weight=Pango.Weight.BOLD, scale=1.2)
        stderr_tag = text_buffer.create_tag("stderr_title", weight=Pango.Weight.BOLD, scale=1.2, foreground="red")

        text_buffer.insert_with_tags_by_name(text_buffer.get_end_iter(), "STDOUT\n", "stdout_title")
        text_buffer.insert(text_buffer.get_end_iter(), node.stdout or "No standard output.\n")
        text_buffer.insert(text_buffer.get_end_iter(), "\n")
        text_buffer.insert_with_tags_by_name(text_buffer.get_end_iter(), "STDERR\n", "stderr_title")
        text_buffer.insert(text_buffer.get_end_iter(), node.stderr or "No standard error.\n")

        scrolled_window.set_child(text_view)

        page = self.app_window.notebook.append(scrolled_window)
        page.set_title(f"History: {node.command[:20]}")
        page.pulse_history_uuid = node.uuid
        self.app_window.notebook.set_selected_page(page)

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
