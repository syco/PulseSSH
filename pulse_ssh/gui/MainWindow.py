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
from typing import List
from typing import Optional
import math
import os
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import pulse_ssh.gui.dialogs.PasswordDialog as _password_dialog
import pulse_ssh.gui.Globals as _gui_globals
import pulse_ssh.gui.managers.ClusterManager as _cluster_manager
import pulse_ssh.gui.managers.LayoutManager as _layout_manager
import pulse_ssh.gui.managers.ShortcutManager as _shortcut_manager
import pulse_ssh.gui.views.ClustersView as _clusters_view
import pulse_ssh.gui.views.ConnectionsView as _connections_view
import pulse_ssh.gui.views.HistoryView as _history_view
import pulse_ssh.gui.VteTerminal as _vte_terminal
import pulse_ssh.Utils as _utils


if _globals.app_config.use_adw_window:
    BASE_WINDOW_CLASS = Adw.ApplicationWindow
else:
    BASE_WINDOW_CLASS = Gtk.ApplicationWindow

class MainWindow(BASE_WINDOW_CLASS):
    def __init__(self, app):
        super().__init__(application=app, title="PulseSSH")

        _gui_globals.cluster_manager = _cluster_manager.ClusterManager(self)
        _gui_globals.layout_manager = _layout_manager.LayoutManager(self)
        _gui_globals.shortcut_manager = _shortcut_manager.ShortcutManager(self)

        self.fix_icon(self)

        self.set_default_size(_gui_globals.cache_config.window_width, _gui_globals.cache_config.window_height)
        if _gui_globals.cache_config.window_maximized:
            self.maximize()

        self.top_bar_view = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        self.sidebar_toggle_btn = Gtk.Button()

        self.sidebar_toggle_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.sidebar_toggle_container.append(self.sidebar_toggle_btn)
        self.sidebar_toggle_container.set_hexpand(False)
        self.sidebar_toggle_container.add_css_class("toolbar")
        self.sidebar_toggle_container.add_css_class("toolbar_with_bg")

        self.split_view = Adw.OverlaySplitView()

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._build_ui()

        self.apply_config_settings()

    def fix_icon(self, window):
        icon_dir = os.path.join(_utils.project_root, 'res', 'icons', 'hicolor', '512x512', 'apps')
        icon_name = "pulse_ssh"

        icon_path = os.path.join(icon_dir, f"{icon_name}.png")

        if os.path.exists(icon_path):
            display = Gdk.Display.get_default()
            icon_theme = Gtk.IconTheme.get_for_display(display)

            icon_theme.add_search_path(os.path.join(_utils.project_root, 'res', 'icons'))

            window.set_icon_name(icon_name)
        else:
            print("Icon file missing:", icon_path)

    def apply_config_settings(self):
        color_scheme_map = {
            "default": Adw.ColorScheme.DEFAULT,
            "force-light": Adw.ColorScheme.FORCE_LIGHT,
            "force-dark": Adw.ColorScheme.FORCE_DARK,
        }
        Adw.StyleManager.get_default().set_color_scheme(color_scheme_map.get(_globals.app_config.color_scheme, Adw.ColorScheme.DEFAULT))
        self.split_view.set_sidebar_position(Gtk.PositionType.RIGHT if _globals.app_config.sidebar_on_right else Gtk.PositionType.LEFT)

        css = f"""
        {_globals.app_config.custom_css or ""}
        .toolbar_with_bg {{
            background-color: @headerbar_bg_color;
            border-bottom: 1px solid @headerbar_shade_color;
        }}
        """
        self.css_provider.load_from_data(css.encode('utf-8'))

        self.top_bar_view.remove(self.sidebar_toggle_container)
        if _globals.app_config.sidebar_on_right:
            self.top_bar_view.append(self.sidebar_toggle_container)
        else:
            self.top_bar_view.prepend(self.sidebar_toggle_container)

        self.set_sidebar_toggle_btn_icon()

    def _build_ui(self):
        self.connect("realize", self.on_realize)

        self.connect("close-request", self.on_app_close_request)

        self.panel_stack = Adw.ViewStack()

        self.connections_view = _connections_view.ConnectionsView(self)
        connections_widget = self.connections_view.get_adw_toolbar_view()
        self.panel_stack.add_titled(connections_widget, "connections", "")
        self.panel_stack.get_page(connections_widget).set_icon_name("utilities-terminal-symbolic")

        self.clusters_view = _clusters_view.ClustersView(self)
        clusters_widget = self.clusters_view.get_adw_toolbar_view()
        self.panel_stack.add_titled(clusters_widget, "clusters", "")
        self.panel_stack.get_page(clusters_widget).set_icon_name("view-group-symbolic")

        self.history_view = _history_view.HistoryView(self)
        history_widget = self.history_view.get_adw_toolbar_view()
        self.panel_stack.add_titled(history_widget, "history", "")
        self.panel_stack.get_page(history_widget).set_icon_name("view-history-symbolic")

        stack_switcher = Adw.ViewSwitcher(policy=Adw.ViewSwitcherPolicy.WIDE)
        stack_switcher.set_stack(self.panel_stack)
        stack_switcher.add_css_class("toolbar")

        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side_panel.set_hexpand(True)
        side_panel.set_vexpand(True)
        side_panel.append(stack_switcher)
        side_panel.append(self.panel_stack)

        notebook = Adw.TabView()
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)
        notebook.connect("close-page", self.on_notebook_close_page)
        notebook.connect("notify::selected-page", self._on_tab_switched)
        notebook.connect("create-window", self._on_create_window)

        _gui_globals.all_notebooks.append(notebook)

        tab_bar = Adw.TabBar(autohide=False, expand_tabs=False, view=notebook)
        tab_bar.set_hexpand(True)

        self.sidebar_toggle_btn.set_tooltip_text("Toggle Sidebar")
        self.sidebar_toggle_btn.connect("clicked", self.on_toggle_sidebar)

        self.set_sidebar_toggle_btn_icon()

        self.top_bar_view.append(tab_bar)

        content_toolbar_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_toolbar_view.append(self.top_bar_view)
        content_toolbar_view.append(notebook)

        self.split_view.set_sidebar(side_panel)
        self.split_view.set_content(content_toolbar_view)
        self.split_view.set_collapsed(not _gui_globals.cache_config.sidebar_visible)
        self.split_view.set_min_sidebar_width(200)
        self.split_view.set_max_sidebar_width(400)
        self.split_view.set_sidebar_width_fraction(0.2)
        self.split_view.set_sidebar_position(Gtk.PositionType.RIGHT if _globals.app_config.sidebar_on_right else Gtk.PositionType.LEFT)
        self.split_view.set_hexpand(True)
        self.split_view.set_vexpand(True)

        toolbar_view = Adw.ToolbarView(content=self.split_view)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(toolbar_view)

        if _globals.app_config.use_adw_window:
            header_bar = Adw.HeaderBar(show_start_title_buttons=True, show_end_title_buttons=True)
            toolbar_view.add_top_bar(header_bar)

            self.set_content(self.toast_overlay)
        else:
            self.set_child(self.toast_overlay)

        _gui_globals.shortcut_manager._setup_shortcuts_for_window(self)

        self.connections_view.list_view.grab_focus()

    def on_realize(self, widget):
        if _globals.app_config.encryption_enabled and _globals.app_config.encryption_canary:
            self._prompt_for_decryption_password()

    def set_sidebar_toggle_btn_icon(self):
        if self.split_view.get_collapsed() == _globals.app_config.sidebar_on_right:
            self.sidebar_toggle_btn.set_icon_name('arrow-left-symbolic')
        else:
            self.sidebar_toggle_btn.set_icon_name('arrow-right-symbolic')

    def on_toggle_sidebar(self, button):
        self.split_view.set_collapsed(not self.split_view.get_collapsed())
        self.set_sidebar_toggle_btn_icon()

    def _prompt_for_decryption_password(self):
        dialog = _password_dialog.PasswordDialog(
            self,
            "Decryption Password Required",
            "Your configuration is encrypted. Please enter the password to continue."
        )

        def on_response(d, response_id, password):
            if response_id == Gtk.ResponseType.OK and password:
                if _utils.verify_encryption_password(password):
                    if _utils.decrypt_all_connections():
                        return
                    else:
                        fail_dialog = Adw.MessageDialog(transient_for=self, modal=True, heading="Decryption Failed", body="Could not decrypt connection data. The configuration might be corrupted. The application will now exit.")

            fail_dialog = Adw.MessageDialog(transient_for=self, modal=True, heading="Incorrect Password", body="The password was incorrect. The application will now exit.")
            fail_dialog.add_response("ok", "OK")
            fail_dialog.connect("response", lambda *_: self.get_application().quit())
            fail_dialog.present()

        dialog.connect("response", on_response)
        dialog.present()

    def _on_create_window(self, tab_view):
        app = self.get_application()
        if not app:
            return None

        win = BASE_WINDOW_CLASS(application=app, title="PulseSSH")
        win._force_quit = False

        self.fix_icon(win)

        notebook = Adw.TabView()
        notebook.connect("close-page", self.on_notebook_close_page)
        tab_bar = Adw.TabBar(autohide=True, expand_tabs=False, view=notebook)

        content_toolbar_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_toolbar_view.append(tab_bar)
        content_toolbar_view.append(notebook)

        toolbar_view = Adw.ToolbarView(content=content_toolbar_view)

        win.toast_overlay = Adw.ToastOverlay()
        win.toast_overlay.set_child(toolbar_view)

        if _globals.app_config.use_adw_window:
            header_bar = Adw.HeaderBar()
            toolbar_view.add_top_bar(header_bar)

            win.set_content(win.toast_overlay)
        else:
            win.set_child(win.toast_overlay)
        win.set_default_size(800, 600)
        win.present()

        _gui_globals.all_notebooks.append(notebook)

        _gui_globals.shortcut_manager._setup_shortcuts_for_window(win)

        win.connect("close-request", lambda w: self.on_sub_window_close_request(win, notebook))

        return notebook

    def _save_window_state(self):
        if _gui_globals.cache_config:
            if not self.is_maximized():
                _gui_globals.cache_config.window_width = self.get_width()
                _gui_globals.cache_config.window_height = self.get_height()

            _gui_globals.cache_config.window_maximized = self.is_maximized()

            _gui_globals.cache_config.sidebar_visible = not self.split_view.get_collapsed()

            _utils.save_cache_config(_globals.config_dir, _globals.readonly, _gui_globals.cache_config)

    def on_app_close_request(self, window):
        all_terminals = []
        for notebook in _gui_globals.all_notebooks:
            all_terminals.extend(self._find_all_terminals_in_widget(notebook))

        is_active = any(t.connected for t in all_terminals)

        if not is_active:
            app = self.get_application()
            if app:
                self._save_window_state()
                app.quit()

        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Quit PulseSSH?",
            body="There are active SSH connections. Are you sure you want to quit?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", "Quit")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d, response_id):
            if response_id == "quit":
                app = self.get_application()
                if app:
                    self._save_window_state()
                    app.quit()

        dialog.connect("response", on_response)
        dialog.present()

        return True

    def on_sub_window_close_request(self, window, notebook):
        if window._force_quit:
            _gui_globals.all_notebooks.remove(notebook)
            return False

        terminals = self._find_all_terminals_in_widget(notebook)
        is_active = any(t.connected for t in terminals)

        if not is_active:
            _gui_globals.all_notebooks.remove(notebook)
            return False

        dialog = Adw.MessageDialog(
            transient_for=window,
            modal=True,
            heading="Close window?",
            body="There are active SSH connections. Are you sure you want to close them?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", "Quit")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d, response_id):
            if response_id == "quit":
                window._force_quit = True
                window.close()

        dialog.connect("response", on_response)
        dialog.present()

        return True

    def on_notebook_close_page(self, notebook, page):
        terminals = self._find_all_terminals_in_widget(page.get_child())
        is_active = False
        for t in terminals:
            if t.connected:
                is_active = True
                break

        if not is_active:
            return False

        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Close Tab?",
            body="This tab contains active SSH connections. Are you sure you want to close it?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("close", "Close")
        dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d, response_id):
            if response_id == "close":
                notebook.close_page_finish(page, True)
            else:
                notebook.close_page_finish(page, False)

        dialog.connect("response", on_response)
        dialog.present()

        return True

    def _on_tab_switched(self, notebook, param):
        page = notebook.get_selected_page()
        if not page:
            return

        content = page.get_child()
        if not content:
            return

        if hasattr(page, 'pulse_history_uuid') and page.pulse_history_uuid:
            self.history_view.open_history_in_tab(None, None, page.pulse_history_uuid)
            return

        terminal = self._find_first_terminal_in_widget(content)
        self.connections_view.select_connection_from_terminal(terminal)

    def open_all_connections_in_tabs(self, action, param, conns_to_start: Optional[List[_connection.Connection]], clustered=False, cluster_id: Optional[str] = None, cluster_name: Optional[str] = None):
        if not conns_to_start:
            return

        def do_open(c_id: Optional[str] = None, c_name: Optional[str] = None):
            if clustered and len(conns_to_start) > 1:
                if not c_id or not c_name:
                    return
                for conn in conns_to_start:
                    _gui_globals.layout_manager.open_connection_tab(conn, c_id, c_name)
            else:
                for conn in conns_to_start:
                    _gui_globals.layout_manager.open_connection_tab(conn)

        if len(conns_to_start) > 1:
            if cluster_id and cluster_name:
                do_open(cluster_id, cluster_name)
                return
            elif clustered:
                _gui_globals.ask_for_cluster_name(self, do_open)
                return
        do_open()

    def open_all_connections_split(self, action, param, conns_to_start: Optional[List[_connection.Connection]], clustered=False, cluster_id: Optional[str] = None, cluster_name: Optional[str] = None):
        if not conns_to_start:
            return

        num_conns = len(conns_to_start)
        if num_conns == 0:
            return

        if num_conns == 1:
            _gui_globals.layout_manager.open_connection_tab(conns_to_start[0])
            return

        notebook_w = _gui_globals.all_notebooks[0].get_allocated_width()
        notebook_h = _gui_globals.all_notebooks[0].get_allocated_height()

        best_overall_cols = 1
        best_overall_rows = num_conns
        max_overall_squareness = -1

        best_perfect_cols = 0
        best_perfect_rows = 0
        max_perfect_squareness = -1

        for c in range(1, num_conns + 1):
            r = math.ceil(num_conns / c)
            cell_w = notebook_w / c
            cell_h = notebook_h / r
            if cell_w == 0 or cell_h == 0:
                continue

            squareness = min(cell_w, cell_h) / max(cell_w, cell_h)

            if c * r == num_conns:
                if squareness > max_perfect_squareness:
                    max_perfect_squareness = squareness
                    best_perfect_cols = c
                    best_perfect_rows = r

            if squareness > max_overall_squareness:
                max_overall_squareness = squareness
                best_overall_cols = c
                best_overall_rows = r

        cols = best_perfect_cols if best_perfect_cols > 0 else best_overall_cols
        rows = best_perfect_rows if best_perfect_rows > 0 else best_overall_rows

        def build_grid(items, is_vertical, total_items):
            if not items or len(items) == 0:
                return None
            if len(items) == 1:
                return items[0]

            mid = len(items) // 2
            start_items = items[:mid]
            end_items = items[mid:]

            paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL if is_vertical else Gtk.Orientation.HORIZONTAL)
            paned.set_start_child(build_grid(start_items, is_vertical, total_items))
            paned.set_end_child(build_grid(end_items, is_vertical, total_items))

            def _set_paned_position(paned: Gtk.Paned, start_items_len: int, items_len: int, is_vertical: bool):
                if is_vertical:
                    allocated_size = paned.get_allocated_height()
                    if allocated_size > 0:
                        paned.set_position(allocated_size * start_items_len // items_len)
                else:
                    allocated_size = paned.get_allocated_width()
                    if allocated_size > 0:
                        paned.set_position(allocated_size * start_items_len // items_len)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_set_paned_position, paned, len(start_items), len(items), is_vertical)
            return paned

        def do_open(c_id: Optional[str] = None, c_name: Optional[str] = None):
            if clustered and len(conns_to_start) > 1:
                if not c_id or not c_name:
                    return

            terminals = [_gui_globals.layout_manager.create_terminal(conn, c_id, c_name) for conn in conns_to_start]

            grid_rows = [build_grid([terminals[r * cols + c] for c in range(cols) if r * cols + c < num_conns], False, cols) for r in range(rows)]
            final_grid = build_grid(grid_rows, True, rows)

            boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            boxy.append(final_grid)
            page = _gui_globals.all_notebooks[0].append(boxy)
            if len(conns_to_start) > 1 and cluster_id and cluster_name:
                page.custom_title = cluster_name
            self.updatePageTitle(page)
            _gui_globals.all_notebooks[0].set_selected_page(page)

        if len(conns_to_start) > 1:
            if cluster_id and cluster_name:
                do_open(cluster_id, cluster_name)
                return
            elif clustered:
                _gui_globals.ask_for_cluster_name(self, do_open)
                return
        do_open()

    def _rename_tab(self, action, param, terminal, page):
        if not page:
            return

        dialog = Adw.MessageDialog(transient_for=self, modal=True, heading="Rename Tab")
        entry = Adw.EntryRow(title="Tab Name", text=page.get_title(), activates_default=True)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")

        def on_response(d, response_id):
            if response_id == "rename":
                new_title = entry.get_text().strip()
                page.custom_title = new_title if new_title else None
                self.updatePageTitle(page)

        dialog.connect("response", on_response)
        dialog.present()

    def _find_first_terminal_in_widget(self, widget) -> Optional[_vte_terminal.VteTerminal]:
        if isinstance(widget, _vte_terminal.VteTerminal):
            return widget

        if hasattr(widget, 'get_start_child') and widget.get_start_child():
            term = self._find_first_terminal_in_widget(widget.get_start_child())
            if term:
                return term
        if hasattr(widget, 'get_end_child') and widget.get_end_child():
            term = self._find_first_terminal_in_widget(widget.get_end_child())
            if term:
                return term

        if hasattr(widget, 'get_child') and widget.get_child():
             term = self._find_first_terminal_in_widget(widget.get_child())
             if term:
                 return term

        if hasattr(widget, 'get_first_child'):
            child = widget.get_first_child()
            while child:
                term = self._find_first_terminal_in_widget(child)
                if term:
                    return term
                child = child.get_next_sibling()

        return None

    def _find_all_terminals_in_widget(self, widget) -> List[_vte_terminal.VteTerminal]:
        terminals = []
        if isinstance(widget, _vte_terminal.VteTerminal):
            terminals.append(widget)
            return terminals

        children = []
        if hasattr(widget, 'get_start_child') and widget.get_start_child():
            children.append(widget.get_start_child())
        if hasattr(widget, 'get_end_child') and widget.get_end_child():
            children.append(widget.get_end_child())

        if not children and hasattr(widget, 'get_child') and widget.get_child():
             children.append(widget.get_child())

        if not children and hasattr(widget, 'get_first_child'):
            child = widget.get_first_child()
            while child:
                children.append(child)
                child = child.get_next_sibling()

        for child in children:
            terminals.extend(self._find_all_terminals_in_widget(child))

        return terminals

    def updatePageTitle(self, page: Adw.TabPage):
        if not page:
            return

        content = page.get_child()
        if not content:
            page.set_title("Empty Tab")
            page.set_indicator_icon(None)
            page.set_needs_attention(False)
            return

        terminals = self._find_all_terminals_in_widget(content)

        custom_title = page.custom_title if hasattr(page, 'custom_title') else None
        if custom_title:
            page.set_title(GLib.markup_escape_text(custom_title))
        else:
            if terminals:
                conn_names = [t.pulse_conn.name for t in terminals if hasattr(t, 'pulse_conn')]
                unique_names = list(set(dict.fromkeys(conn_names)))
                page.set_title(GLib.markup_escape_text(" + ".join(unique_names)))
            else:
                page.set_title("Empty Tab")
                page.set_indicator_icon(None)
                page.set_needs_attention(False)

        total_terminals = len(terminals)
        connected_terminals = sum(1 for t in terminals if t.connected)

        if connected_terminals == total_terminals:
            page.set_indicator_icon(Gio.Icon.new_for_string("emblem-mounted"))
            page.set_needs_attention(False)
        elif connected_terminals > 0:
            page.set_indicator_icon(Gio.Icon.new_for_string("emblem-warning"))
            page.set_needs_attention(True)
        else:
            page.set_indicator_icon(Gio.Icon.new_for_string("emblem-unmounted"))
            page.set_needs_attention(True)
