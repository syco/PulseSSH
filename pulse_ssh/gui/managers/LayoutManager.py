#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import GLib  # type: ignore
from gi.repository import Gtk  # type: ignore
from typing import Optional
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.VteTerminal as _vte_terminal

class LayoutManager:
    def __init__(self, app_window):
        self.app_window = app_window

    def build_paned_widget(self, orientation, source_content: Gtk.Widget, target_content: Gtk.Widget) -> Gtk.Paned:
        paned = Gtk.Paned(orientation=orientation, wide_handle=False)
        paned.set_start_child(source_content)
        paned.set_end_child(target_content)

        def set_initial_position(p):
            if p.get_orientation() == Gtk.Orientation.HORIZONTAL:
                width = p.get_allocated_width()
                if width > 0:
                    p.set_position(width // 2)
                    return GLib.SOURCE_REMOVE
            else:
                height = p.get_allocated_height()
                if height > 0:
                    p.set_position(height // 2)
                    return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        paned.connect_after("map", lambda p: GLib.idle_add(set_initial_position, p))

        return paned

    def open_connection_tab(self, conn: _connection.Connection, cluster_id: Optional[str] = None):
        terminal = _gui_globals.layout_manager.create_terminal(conn, cluster_id)

        boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boxy.append(terminal)
        page = _gui_globals.all_notebooks[0].append(boxy)
        _gui_globals.all_notebooks[0].set_selected_page(page)
        self.app_window.updatePageTitle(page)

    def create_terminal(self, conn: _connection.Connection, cluster_id: Optional[str] = None) -> Gtk.ScrolledWindow:
        if conn.uuid in _globals.connections:
            conn = _globals.connections[conn.uuid]

        terminal = _vte_terminal.VteTerminal(self.app_window, conn, cluster_id)

        scrolled = Gtk.ScrolledWindow()
        if _globals.app_config.scrollbar_visible:
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        scrolled.set_child(terminal)

        return scrolled

    def replace_terminal(self, old_terminal, new_scrolled_window):
        notebook, page = old_terminal.get_ancestor_page()

        old_scrolled_window = old_terminal.get_parent()
        parent = old_scrolled_window.get_parent()
        if not parent:
            return
        if isinstance(parent, Gtk.Box):
            parent.remove(old_scrolled_window)
            parent.append(new_scrolled_window)
        elif isinstance(parent, Gtk.Paned):
            if parent.get_start_child() == old_scrolled_window:
                parent.set_start_child(new_scrolled_window)
            else:
                parent.set_end_child(new_scrolled_window)
        if page:
            self.app_window.updatePageTitle(page)

    def split_terminal_or_tab(self, action, param, terminal, source_page, orientation, target_page, target_notebook):
        if _globals.app_config.split_at_root or not terminal:
            self.split_tab(terminal, source_page, orientation, target_page, target_notebook)
        else:
            self.split_terminal(terminal, source_page, orientation, target_page, target_notebook)
        self.app_window.updatePageTitle(source_page)

    def split_tab(self, terminal, source_page, orientation, target_page, target_notebook):
        source_container = source_page.get_child()
        source_content = source_container.get_first_child()
        source_content.unparent()

        if not target_page:
            if not terminal:
                return
            if not hasattr(terminal, 'pulse_conn'):
                return
            target_content = _gui_globals.layout_manager.create_terminal(terminal.pulse_conn)
        else:
            target_container = target_page.get_child()
            target_content = target_container.get_first_child()
            target_content.unparent()
            target_notebook.close_page(target_page)

        paned = self.build_paned_widget(orientation, source_content, target_content)

        source_container.append(paned)

    def split_terminal(self, terminal, source_page, orientation, target_page, target_notebook):
        source_scrolled_window = terminal.get_parent()
        parent = source_scrolled_window.get_parent()
        if not parent:
            return

        if isinstance(parent, Gtk.Box):
            self.split_tab(terminal, source_page, orientation, target_page, target_notebook)
        elif isinstance(parent, Gtk.Paned):
            is_start_child = parent.get_start_child() == source_scrolled_window
            source_scrolled_window.unparent()
            if is_start_child:
                parent.set_start_child(None)
            else:
                parent.set_end_child(None)

            if not target_page:
                if not hasattr(terminal, 'pulse_conn'):
                    return
                target_content = _gui_globals.layout_manager.create_terminal(terminal.pulse_conn)
            else:
                target_container = target_page.get_child()
                target_content = target_container.get_first_child()
                target_content.unparent()
                target_notebook.close_page(target_page)

            paned = self.build_paned_widget(orientation, source_scrolled_window, target_content)

            if is_start_child:
                parent.set_start_child(paned)
            else:
                parent.set_end_child(paned)

    def unsplit_terminal(self, action, param, terminal, source_page, source_notebook):
        source_scrolled_window = terminal.get_parent()
        parent = source_scrolled_window.get_parent()
        if not parent:
            return

        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() == source_scrolled_window:
                sibling = parent.get_end_child()
            else:
                sibling = parent.get_start_child()

            sibling.unparent()

            parent.set_start_child(None)
            parent.set_end_child(None)

            boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            boxy.append(source_scrolled_window)
            page = source_notebook.append(boxy)
            self.app_window.updatePageTitle(page)

            grandparent = parent.get_parent()
            if not grandparent:
                return

            if isinstance(grandparent, Gtk.Box):
                parent.unparent()
                grandparent.append(sibling)

            if isinstance(grandparent, Gtk.Paned):
                if grandparent.get_start_child() == parent:
                    grandparent.set_start_child(sibling)
                else:
                    grandparent.set_end_child(sibling)

            if sibling:
                term = self.app_window._find_first_terminal_in_widget(sibling)
                if term:
                    term.grab_focus()

            self.app_window.updatePageTitle(source_page)

    def close_terminal(self, action, param, terminal, page, notebook):
        _gui_globals.cluster_manager.leave_cluster(terminal)
        source_scrolled_window = terminal.get_parent()
        parent = source_scrolled_window.get_parent()
        if not parent:
            return

        if isinstance(parent, Gtk.Box):
            notebook.close_page(page)
            if notebook != _gui_globals.all_notebooks[0] and notebook.get_n_pages() == 0:
                window_to_close = notebook.get_ancestor(Gtk.ApplicationWindow)
                if window_to_close: window_to_close.close()
            return

        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() == source_scrolled_window:
                sibling = parent.get_end_child()
            else:
                sibling = parent.get_start_child()

            sibling.unparent()

            parent.set_start_child(None)
            parent.set_end_child(None)

            grandparent = parent.get_parent()
            if not grandparent:
                return

            if isinstance(grandparent, Gtk.Box):
                parent.unparent()
                grandparent.append(sibling)

            if isinstance(grandparent, Gtk.Paned):
                if grandparent.get_start_child() == parent:
                    grandparent.set_start_child(sibling)
                else:
                    grandparent.set_end_child(sibling)

            if sibling:
                term = self.app_window._find_first_terminal_in_widget(sibling)
                if term:
                    term.grab_focus()

            self.app_window.updatePageTitle(page)
