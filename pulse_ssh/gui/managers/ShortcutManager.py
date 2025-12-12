#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Vte  # type: ignore
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.VteTerminal as _vte_terminal
import pulse_ssh.Utils as _utils

class ShortcutManager:
    def __init__(self, app_window):
        self.app_window = app_window

    def _setup_shortcuts_for_window(self, window: Adw.ApplicationWindow):
        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcut_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        window.add_controller(shortcut_controller)
        window.add_controller(self._create_fullscreen_controller(window))

        search_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>f"),
            Gtk.CallbackAction.new(self._on_search_shortcut, window)
        )
        shortcut_controller.add_shortcut(search_shortcut)

        duplicate_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>d"),
            Gtk.CallbackAction.new(self._on_duplicate_shortcut)
        )
        shortcut_controller.add_shortcut(duplicate_shortcut)

        next_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Shift>Right"),
            Gtk.CallbackAction.new(self._on_next_tab_shortcut, window)
        )
        shortcut_controller.add_shortcut(next_tab_shortcut)

        previous_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Shift>Left"),
            Gtk.CallbackAction.new(self._on_previous_tab_shortcut, window)
        )
        shortcut_controller.add_shortcut(previous_tab_shortcut)

        new_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>t"),
            Gtk.CallbackAction.new(self._on_new_tab_shortcut, window)
        )
        shortcut_controller.add_shortcut(new_tab_shortcut)

        close_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>w"),
            Gtk.CallbackAction.new(self._on_close_tab_shortcut, window)
        )
        shortcut_controller.add_shortcut(close_tab_shortcut)

        split_h_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>h"),
            Gtk.CallbackAction.new(self._on_split_h_shortcut, window)
        )
        shortcut_controller.add_shortcut(split_h_shortcut)

        split_v_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>b"),
            Gtk.CallbackAction.new(self._on_split_v_shortcut, window)
        )
        shortcut_controller.add_shortcut(split_v_shortcut)

        zoom_in_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>plus"),
            Gtk.CallbackAction.new(self._on_zoom_in_shortcut, window)
        )
        shortcut_controller.add_shortcut(zoom_in_shortcut)

        zoom_out_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>minus"),
            Gtk.CallbackAction.new(self._on_zoom_out_shortcut, window)
        )
        shortcut_controller.add_shortcut(zoom_out_shortcut)

        zoom_reset_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>0"),
            Gtk.CallbackAction.new(self._on_zoom_reset_shortcut, window)
        )
        shortcut_controller.add_shortcut(zoom_reset_shortcut)

        copy_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>c"),
            Gtk.CallbackAction.new(self._on_copy_shortcut, window)
        )
        shortcut_controller.add_shortcut(copy_shortcut)

        paste_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>v"),
            Gtk.CallbackAction.new(self._on_paste_shortcut, window)
        )
        shortcut_controller.add_shortcut(paste_shortcut)

        edit_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Alt>e"),
            Gtk.CallbackAction.new(self._on_edit_shortcut)
        )
        shortcut_controller.add_shortcut(edit_shortcut)

    def _create_fullscreen_controller(self, window: Adw.ApplicationWindow):
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.MANAGED)
        shortcut = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("F11"),
            action=Gtk.NamedAction.new(f"win.toggle-fullscreen-{id(window)}")
        )
        controller.add_shortcut(shortcut)

        def toggle_fullscreen(action, parameter, window):
            if window.is_fullscreen():
                window.unfullscreen()
            else:
                window.fullscreen()

        action = Gio.SimpleAction.new(f"toggle-fullscreen-{id(window)}", None)
        action.connect("activate", toggle_fullscreen, window)
        window.add_action(action)
        return controller

    def _on_new_tab_shortcut(self, widget, *args):
        notebook = None

        focused_widget = widget.get_focus()
        if focused_widget:
            notebook = focused_widget.get_ancestor(Adw.TabView)

        if not notebook:
            notebook = _gui_globals.all_notebooks[0]

        terminal = _gui_globals.layout_manager.create_terminal(_utils.local_connection)

        boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boxy.append(terminal)
        page = notebook.append(boxy)
        notebook.set_selected_page(page)
        self.app_window.updatePageTitle(page)
        return True

    def _on_close_tab_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if not focused_widget:
            return True

        notebook = focused_widget.get_ancestor(Adw.TabView)
        if not notebook:
            return True

        page = notebook.get_selected_page()
        if page:
            notebook.close_page(page)
        return True

    def _split_focused_terminal(self, window, orientation):
        terminal = window.get_focus()
        if isinstance(terminal, _vte_terminal.VteTerminal):
            notebook, page = terminal.get_ancestor_page()
            if not notebook or not page:
                _gui_globals.show_error_dialog(self.app_window, "Internal UI Error", "Could not find the parent tab for the disconnected terminal. The tab's status indicator may not update correctly.")
                return
            _gui_globals.layout_manager.split_terminal_or_tab(None, None, terminal, page, orientation, None, None)
        return True

    def _on_split_h_shortcut(self, widget, *args):
        self._split_focused_terminal(widget, Gtk.Orientation.HORIZONTAL)
        return True

    def _on_split_v_shortcut(self, widget, *args):
        self._split_focused_terminal(widget, Gtk.Orientation.VERTICAL)
        return True

    def _on_search_shortcut(self, *args):
        if self.app_window.panel_stack.get_visible_child_name() == "connections":
            self.app_window.connections_view.filter_header_bar.set_visible(True)
            self.app_window.connections_view.filter_entry.grab_focus()
            self.app_window.connections_view.filter_entry.select_region(0, -1)
        elif self.app_window.panel_stack.get_visible_child_name() == "clusters":
            self.app_window.clusters_view.filter_header_bar.set_visible(True)
            self.app_window.clusters_view.filter_entry.grab_focus()
            self.app_window.clusters_view.filter_entry.select_region(0, -1)
        elif self.app_window.panel_stack.get_visible_child_name() == "history":
            self.app_window.history_view.filter_header_bar.set_visible(True)
            self.app_window.history_view.filter_entry.grab_focus()
            self.app_window.history_view.filter_entry.select_region(0, -1)
        return True

    def _on_edit_shortcut(self, *args):
        active_view = self.app_window.panel_stack.get_visible_child_name()
        if active_view == "connections":
            self.app_window.connections_view.edit_selected_entry()
        elif active_view == "clusters":
            self.app_window.clusters_view.edit_selected_entry()
        return True

    def _on_duplicate_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal) and hasattr(focused_widget, 'pulse_conn'):
            _gui_globals.layout_manager.open_connection_tab(focused_widget.pulse_conn)
        return True

    def _on_next_tab_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if not focused_widget:
            return True

        notebook = focused_widget.get_ancestor(Adw.TabView)
        if not notebook:
            return True

        n_pages = notebook.get_n_pages()
        if n_pages < 2:
            return True

        selected_page = notebook.get_selected_page()
        current_pos = notebook.get_page_position(selected_page)
        next_pos = (current_pos + 1) % n_pages
        notebook.set_selected_page(notebook.get_nth_page(next_pos))
        return True

    def _on_previous_tab_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if not focused_widget:
            return True

        notebook = focused_widget.get_ancestor(Adw.TabView)
        if not notebook:
            return True

        n_pages = notebook.get_n_pages()
        if n_pages < 2:
            return True

        selected_page = notebook.get_selected_page()
        current_pos = notebook.get_page_position(selected_page)
        prev_pos = (current_pos - 1 + n_pages) % n_pages
        notebook.set_selected_page(notebook.get_nth_page(prev_pos))
        return True

    def _on_copy_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal):
            focused_widget.copy_clipboard_format(Vte.Format.TEXT)
        return True

    def _on_paste_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal):
            focused_widget.paste_clipboard()
        return True

    def _on_zoom_in_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal):
            newscale = focused_widget.get_font_scale() + 0.1
            cluster_id = focused_widget.pulse_cluster_id
            if cluster_id and cluster_id in _gui_globals.active_clusters:
                for terminal in _gui_globals.active_clusters[cluster_id].terminals:
                    terminal.set_font_scale(newscale)
            else:
                focused_widget.set_font_scale(newscale)
        return True

    def _on_zoom_out_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal):
            newscale = focused_widget.get_font_scale() - 0.1
            cluster_id = focused_widget.pulse_cluster_id
            if cluster_id and cluster_id in _gui_globals.active_clusters:
                for terminal in _gui_globals.active_clusters[cluster_id].terminals:
                    terminal.set_font_scale(newscale)
            else:
                focused_widget.set_font_scale(newscale)
        return True

    def _on_zoom_reset_shortcut(self, widget, *args):
        focused_widget = widget.get_focus()
        if isinstance(focused_widget, _vte_terminal.VteTerminal):
            cluster_id = focused_widget.pulse_cluster_id
            if cluster_id and cluster_id in _gui_globals.active_clusters:
                for terminal in _gui_globals.active_clusters[cluster_id].terminals:
                    terminal.set_font_scale(1.0)
            else:
                focused_widget.set_font_scale(1.0)
        return True
