#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import GLib  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import Gio  # type: ignore
from gi.repository import Gtk  # type: ignore
from gi.repository import Vte  # type: ignore
from typing import Dict
from typing import List
from typing import Optional
import math
import os
import pulse_ssh.Utils as utils
import pulse_ssh.data.Connection as connection
import pulse_ssh.ui.VteTerminal as vte_terminal
import pulse_ssh.ui.views.ClustersView as clusters_view
import pulse_ssh.ui.views.CommandsHistoryView as commands_history_view
import pulse_ssh.ui.views.ConnectionsView as connections_view
import pulse_ssh.ui.views.list_items.CommandHistoryItem as command_history_item
import uuid

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, config_dir: str, readonly: bool = False, about_info: Dict = {}):
        super().__init__(application=app, title="PulseSSH")

        self.config_dir = config_dir
        self.readonly = readonly
        self.about_info = about_info
        self._force_quit = False
        self.active_clusters: Dict[str, List[vte_terminal.VteTerminal]] = {}
        self.command_history: Dict[str, List[command_history_item.CommandHistoryItem]] = {}
        self.post_cmd_subprocesses = []
        self.app_config, self.connections, self.clusters = utils.load_app_config(self.config_dir)
        self.cache_config = utils.load_cache_config(self.config_dir)

        icon_dir = os.path.join(utils.project_root, 'res', 'icons', 'hicolor', '512x512', 'apps')
        icon_name = "pulse_ssh"

        icon_path = os.path.join(icon_dir, f"{icon_name}.png")

        if os.path.exists(icon_path):
            display = Gdk.Display.get_default()
            icon_theme = Gtk.IconTheme.get_for_display(display)

            icon_theme.add_search_path(os.path.join(utils.project_root, 'res', 'icons'))

            self.set_icon_name(icon_name)
        else:
            print("Icon file missing:", icon_path)

        self.set_default_size(self.cache_config.window_width, self.cache_config.window_height)
        if self.cache_config.window_maximized:
            self.maximize()

        self.split_view = Adw.NavigationSplitView()

        self.top_bar = Adw.HeaderBar(show_start_title_buttons=True, show_end_title_buttons=True, decoration_layout="menu:minimize,maximize,close", title_widget=Gtk.Label(label="PulseSSH", xalign=0))

        self.apply_config_settings()
        self._build_ui()

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        window.background {
            border-radius: 3px;
        }
        stackswitcher button {
            border-radius: 0;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def apply_config_settings(self):
        color_scheme_map = {
            "default": Adw.ColorScheme.DEFAULT,
            "force-light": Adw.ColorScheme.FORCE_LIGHT,
            "force-dark": Adw.ColorScheme.FORCE_DARK,
        }
        Adw.StyleManager.get_default().set_color_scheme(color_scheme_map.get(self.app_config.color_scheme, Adw.ColorScheme.DEFAULT))
        self.split_view.set_sidebar_position(Gtk.PositionType.RIGHT if self.app_config.sidebar_on_right else Gtk.PositionType.LEFT)

    def _build_ui(self):
        self.panel_stack = Adw.ViewStack()

        self.connections_view = connections_view.ConnectionsView(self)
        connections_widget = self.connections_view.getAdwToolbarView()
        self.panel_stack.add_titled(connections_widget, "connections", "")
        self.panel_stack.get_page(connections_widget).set_icon_name("utilities-terminal-symbolic")

        self.clusters_view = clusters_view.ClustersView(self)
        clusters_widget = self.clusters_view.getAdwToolbarView()
        self.panel_stack.add_titled(clusters_widget, "clusters", "")
        self.panel_stack.get_page(clusters_widget).set_icon_name("view-group-symbolic")

        self.commands_history_view = commands_history_view.CommandsHistoryView(self)
        history_widget = self.commands_history_view.getAdwToolbarView()
        self.panel_stack.add_titled(history_widget, "history", "")
        self.panel_stack.get_page(history_widget).set_icon_name("view-history-symbolic")

        stack_switcher = Adw.ViewSwitcher(policy=Adw.ViewSwitcherPolicy.WIDE)
        stack_switcher.set_stack(self.panel_stack)

        switcher_container = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False, title_widget=stack_switcher)

        self.side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.side_panel.append(switcher_container)
        self.side_panel.append(self.panel_stack)

        sidebar_page = Adw.NavigationPage.new(self.side_panel, "Sidebar")

        self.notebook = Adw.TabView()
        self.notebook.set_vexpand(True)
        self.notebook.connect("close-page", self.on_notebook_close_page)
        self.notebook.connect("notify::selected-page", self._on_tab_switched)
        self.connect("close-request", self.on_window_close_request)

        tab_bar = Adw.TabBar(autohide=False, expand_tabs=False, view=self.notebook)

        content_toolbar_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_toolbar_view.append(tab_bar)
        content_toolbar_view.append(self.notebook)

        content_page = Adw.NavigationPage.new(content_toolbar_view, "Terminals")

        self.split_view.set_sidebar(sidebar_page)
        self.split_view.set_content(content_page)
        self.split_view.set_collapsed(False)
        self.split_view.set_min_sidebar_width(200)
        self.split_view.set_max_sidebar_width(400)
        self.split_view.set_sidebar_width_fraction(0.2)
        self.split_view.set_sidebar_position(Gtk.PositionType.RIGHT if self.app_config.sidebar_on_right else Gtk.PositionType.LEFT)
        self.split_view.set_vexpand(True)

        toolbar_view = Adw.ToolbarView(content=self.split_view)
        toolbar_view.add_top_bar(self.top_bar)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

        self._setup_shortcuts()

        self.connections_view.list_view.grab_focus()

    def _save_window_state(self):
        if not self.is_maximized():
            self.cache_config.window_width = self.get_width()
            self.cache_config.window_height = self.get_height()

        self.cache_config.window_maximized = self.is_maximized()
        utils.save_cache_config(self.config_dir, self.readonly, self.cache_config)

    def on_window_close_request(self, window):
        self._save_window_state()

        if self._force_quit:
            return False

        terminals = self._find_all_terminals_in_widget(self.notebook)
        is_active = any(t.connected for t in terminals)

        if not is_active:
            return False

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
                self._force_quit = True
                self.close()

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
                self.notebook.close_page_finish(page, True)
            else:
                self.notebook.close_page_finish(page, False)

        dialog.connect("response", on_response)
        dialog.present()

        return True

    def _setup_shortcuts(self):
        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcut_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.add_controller(shortcut_controller)
        self.add_controller(self._create_fullscreen_controller())

        search_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>f"),
            Gtk.CallbackAction.new(self._on_search_shortcut)
        )
        shortcut_controller.add_shortcut(search_shortcut)

        duplicate_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>d"),
            Gtk.CallbackAction.new(self._on_duplicate_shortcut)
        )
        shortcut_controller.add_shortcut(duplicate_shortcut)

        next_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Shift>Right"),
            Gtk.CallbackAction.new(self._on_next_tab_shortcut)
        )
        shortcut_controller.add_shortcut(next_tab_shortcut)

        previous_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Shift>Left"),
            Gtk.CallbackAction.new(self._on_previous_tab_shortcut)
        )
        shortcut_controller.add_shortcut(previous_tab_shortcut)

        new_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>t"),
            Gtk.CallbackAction.new(self._on_new_tab_shortcut)
        )
        shortcut_controller.add_shortcut(new_tab_shortcut)

        close_tab_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>w"),
            Gtk.CallbackAction.new(self._on_close_tab_shortcut)
        )
        shortcut_controller.add_shortcut(close_tab_shortcut)

        split_h_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>h"),
            Gtk.CallbackAction.new(self._on_split_h_shortcut)
        )
        shortcut_controller.add_shortcut(split_h_shortcut)

        split_v_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>b"),
            Gtk.CallbackAction.new(self._on_split_v_shortcut)
        )
        shortcut_controller.add_shortcut(split_v_shortcut)

        zoom_in_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>plus"),
            Gtk.CallbackAction.new(self._on_zoom_in_shortcut)
        )
        shortcut_controller.add_shortcut(zoom_in_shortcut)

        zoom_out_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>minus"),
            Gtk.CallbackAction.new(self._on_zoom_out_shortcut)
        )
        shortcut_controller.add_shortcut(zoom_out_shortcut)

        zoom_reset_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>0"),
            Gtk.CallbackAction.new(self._on_zoom_reset_shortcut)
        )
        shortcut_controller.add_shortcut(zoom_reset_shortcut)

        copy_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>c"),
            Gtk.CallbackAction.new(self._on_copy_shortcut)
        )
        shortcut_controller.add_shortcut(copy_shortcut)

        paste_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>v"),
            Gtk.CallbackAction.new(self._on_paste_shortcut)
        )
        shortcut_controller.add_shortcut(paste_shortcut)

        edit_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Alt>e"),
            Gtk.CallbackAction.new(self._on_edit_shortcut)
        )
        shortcut_controller.add_shortcut(edit_shortcut)

    def _create_fullscreen_controller(self):
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.MANAGED)
        shortcut = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("F11"),
            action=Gtk.NamedAction.new("win.toggle-fullscreen")
        )
        controller.add_shortcut(shortcut)

        def toggle_fullscreen(action, parameter, window):
            if window.is_fullscreen():
                window.unfullscreen()
            else:
                window.fullscreen()

        action = Gio.SimpleAction.new("toggle-fullscreen", None)
        action.connect("activate", toggle_fullscreen, self)
        self.add_action(action)
        return controller

    def _on_new_tab_shortcut(self, *args):
        terminal = self.create_terminal(utils.local_connection)

        boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boxy.append(terminal)
        page = self.notebook.append(boxy)
        self.notebook.set_selected_page(page)
        self.updatePageTitle(page)
        return True

    def _on_close_tab_shortcut(self, *args):
        page = self.notebook.get_selected_page()
        if page:
            self.notebook.close_page(page)
        return True

    def _on_split_h_shortcut(self, *args):
        self._split_focused_terminal(Gtk.Orientation.HORIZONTAL)
        return True

    def _on_split_v_shortcut(self, *args):
        self._split_focused_terminal(Gtk.Orientation.VERTICAL)
        return True

    def _on_search_shortcut(self, *args):
        if self.panel_stack.get_visible_child_name() == "connections":
            self.connections_view.filter_entry.grab_focus()
            self.connections_view.filter_header_bar.set_visible(True)
        elif self.panel_stack.get_visible_child_name() == "clusters":
            self.clusters_view.filter_entry.grab_focus()
            self.clusters_view.filter_header_bar.set_visible(True)
        return True

    def _on_edit_shortcut(self, *args):
        active_view = self.panel_stack.get_visible_child_name()
        if active_view == "connections":
            self.connections_view.edit_selected_entry()
        elif active_view == "clusters":
            self.clusters_view.edit_selected_entry()
        return True

    def _on_duplicate_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal) and hasattr(focused_widget, 'pulse_conn'):
            self.open_connection_tab(focused_widget.pulse_conn)
        return True

    def _on_next_tab_shortcut(self, *args):
        n_pages = self.notebook.get_n_pages()
        if n_pages < 2:
            return True

        selected_page = self.notebook.get_selected_page()
        current_pos = self.notebook.get_page_position(selected_page)
        next_pos = (current_pos + 1) % n_pages
        self.notebook.set_selected_page(self.notebook.get_nth_page(next_pos))
        return True

    def _on_previous_tab_shortcut(self, *args):
        n_pages = self.notebook.get_n_pages()
        if n_pages < 2:
            return True

        selected_page = self.notebook.get_selected_page()
        current_pos = self.notebook.get_page_position(selected_page)
        prev_pos = (current_pos - 1 + n_pages) % n_pages
        self.notebook.set_selected_page(self.notebook.get_nth_page(prev_pos))
        return True

    def _on_copy_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal):
            focused_widget.copy_clipboard_format(Vte.Format.TEXT)
        return True

    def _on_paste_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal):
            focused_widget.paste_clipboard()
        return True

    def _on_zoom_in_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal):
            focused_widget.set_font_scale(focused_widget.get_font_scale() * 1.1)
        return True

    def _on_zoom_out_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal):
            focused_widget.set_font_scale(focused_widget.get_font_scale() / 1.1)
        return True

    def _on_zoom_reset_shortcut(self, *args):
        focused_widget = self.get_focus()
        if isinstance(focused_widget, vte_terminal.VteTerminal):
            focused_widget.set_font_scale(1.0)
        return True

    def _on_tab_switched(self, notebook, param):
        page = notebook.get_selected_page()
        if not page:
            return

        content = page.get_child()
        if not content:
            return

        terminal = self._find_first_terminal_in_widget(content)
        self.connections_view.select_connection_from_terminal(terminal)

    def _split_focused_terminal(self, orientation):
        terminal = self.get_focus()
        if isinstance(terminal, vte_terminal.VteTerminal):
            source_page = terminal.get_ancestor_page()
            if not source_page:
                self.show_error_dialog(
                    "Internal UI Error",
                    "Could not find the parent tab for the disconnected terminal. The tab's status indicator may not update correctly."
                )
                return
            source_page_idx = self.notebook.get_page_position(source_page)
            self.split_terminal_or_tab(None, None, terminal, source_page, source_page_idx, orientation, None, -1)
        return True

    def open_all_connections_in_tabs(self, action, param, conns_to_start: Optional[List[connection.Connection]], clustered=False, cluster_name=None):
        if not conns_to_start:
            return

        def do_open(cluster_id=None):
            if clustered and len(conns_to_start) > 1:
                if not cluster_id:
                    return
                for conn in conns_to_start:
                    self.open_connection_tab(conn, cluster_id)
            else:
                for conn in conns_to_start:
                    self.open_connection_tab(conn)

        if len(conns_to_start) > 1:
            if cluster_name:
                do_open(cluster_name)
                return
            elif clustered:
                self._ask_for_cluster_name(do_open)
                return
        do_open()

    def open_all_connections_split(self, action, param, conns_to_start: Optional[List[connection.Connection]], clustered=False, cluster_name=None):
        if not conns_to_start:
            return

        num_conns = len(conns_to_start)
        if num_conns == 0:
            return

        if num_conns == 1:
            self.open_connection_tab(conns_to_start[0])
            return

        notebook_w = self.notebook.get_allocated_width()
        notebook_h = self.notebook.get_allocated_height()

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

            GLib.idle_add(self._set_paned_position, paned, len(start_items), len(items), is_vertical)
            return paned

        def do_open(cluster_id=None):
            if clustered and len(conns_to_start) > 1:
                if not cluster_id:
                    return

            terminals = [self.create_terminal(conn, cluster_id) for conn in conns_to_start]

            grid_rows = [build_grid([terminals[r * cols + c] for c in range(cols) if r * cols + c < num_conns], False, cols) for r in range(rows)]
            final_grid = build_grid(grid_rows, True, rows)

            boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            boxy.append(final_grid)
            page = self.notebook.append(boxy)
            self.updatePageTitle(page)
            self.notebook.set_selected_page(page)

        if len(conns_to_start) > 1:
            if cluster_name:
                do_open(cluster_name)
                return
            elif clustered:
                self._ask_for_cluster_name(do_open)
                return
        do_open()

    def _set_paned_position(self, paned: Gtk.Paned, start_items_len: int, items_len: int, is_vertical: bool):
        print("Setting paned position after idle")
        if is_vertical:
            allocated_size = paned.get_allocated_height()
            if allocated_size > 0:
                paned.set_position(allocated_size * start_items_len // items_len)
        else:
            allocated_size = paned.get_allocated_width()
            if allocated_size > 0:
                paned.set_position(allocated_size * start_items_len // items_len)
        return GLib.SOURCE_REMOVE

    def open_connection_tab(self, conn: connection.Connection, cluster_id: Optional[str] = None):
        terminal = self.create_terminal(conn, cluster_id)

        boxy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boxy.append(terminal)
        page = self.notebook.append(boxy)
        self.notebook.set_selected_page(page)
        self.updatePageTitle(page)

        if conn.type == "ssh":
            def on_post_cmd_finished(subprocess, result, conn_uuid, cmd):
                try:
                    ok, stdout, stderr = subprocess.communicate_utf8_finish(result)
                    history_item = command_history_item.CommandHistoryItem(
                        command=cmd,
                        stdout=stdout,
                        stderr=stderr,
                        ok=ok,
                    )
                    if conn_uuid not in self.command_history:
                        self.command_history[conn_uuid] = []
                    self.command_history[conn_uuid].append(history_item)
                    self.commands_history_view.populate_tree()
                    if not ok:
                        self.show_error_dialog("Post-connection Command Failed", f"Command failed:\n{cmd}\n\n{stderr}")
                except GLib.Error as e:
                    if not e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                        self.show_error_dialog("Post-connection Command Failed", f"Command failed:\n{cmd}\n\n{e.message}")
                self.post_cmd_subprocesses.remove(subprocess)

            all_post_local_cmds = self.app_config.post_local_cmds + conn.post_local_cmds
            for cmd in all_post_local_cmds:
                if cmd:
                    substituted_cmd = utils.substitute_variables(cmd, conn)
                    try:
                        subprocess = Gio.Subprocess.new([self.app_config.shell_program, '-c', substituted_cmd], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
                        self.post_cmd_subprocesses.append(subprocess)
                        subprocess.communicate_utf8_async(None, None, on_post_cmd_finished, conn.uuid, cmd)
                    except GLib.Error as e:
                        self.show_error_dialog("Post-connection Command Failed", f"Failed to execute command:\n{cmd}\n\n{e.message}")
                        return

    def create_terminal(self, conn: connection.Connection, cluster_id: Optional[str] = None) -> Gtk.ScrolledWindow:
        if conn.uuid in self.connections:
            conn = self.connections[conn.uuid]

        terminal = vte_terminal.VteTerminal(self, conn, cluster_id)

        scrolled = Gtk.ScrolledWindow()
        if self.app_config.scrollbar_visible:
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        scrolled.set_child(terminal)

        return scrolled

    def _create_cluster_submenu(self, terminal, action_group):
        submenu = Gio.Menu()

        create_action = Gio.SimpleAction.new("create_new_cluster", None)
        create_action.connect("activate", lambda a, p, t=terminal: self._create_new_cluster(t))
        action_group.add_action(create_action)
        submenu.append("Create New Cluster", "term.create_new_cluster")

        if self.active_clusters:
            submenu.append_section(None, Gio.Menu())
            join_menu = Gio.Menu()
            for cluster_id, terminals_in_cluster in self.active_clusters.items():
                cluster_name = f"Cluster ({cluster_id[:4]})"
                join_action = Gio.SimpleAction.new(f"join_cluster_{cluster_id}", None)
                join_action.connect("activate", lambda a, p, t=terminal, cid=cluster_id: self._join_cluster(t, cid))
                action_group.add_action(join_action)
                join_menu.append(cluster_name, f"term.join_cluster_{cluster_id}")
            submenu.append_submenu("Join Existing Cluster", join_menu)

        if terminal.pulse_cluster_id:
            submenu.append_section(None, Gio.Menu())
            leave_action = Gio.SimpleAction.new("leave_cluster", None)
            leave_action.connect("activate", lambda a, p, t=terminal: self._leave_cluster(t))
            action_group.add_action(leave_action)
            submenu.append("Leave Cluster", "term.leave_cluster")

        return submenu

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

    def _create_new_cluster(self, terminal):
        def on_name_received(cluster_name):
            if cluster_name:
                self._join_cluster(terminal, cluster_name)

        self._ask_for_cluster_name(on_name_received)

    def _ask_for_cluster_name(self, callback):
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="New Cluster",
            body="Enter a name for the new cluster."
        )
        entry = Adw.EntryRow(title="Cluster Name", activates_default=True)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")

        def on_response(d, response_id):
            if response_id == "create":
                cluster_name = entry.get_text().strip() or str(uuid.uuid4())
                callback(cluster_name)
            else:
                callback(None)

        dialog.connect("response", on_response)
        dialog.present()

    def _join_cluster(self, terminal, cluster_id):
        self._leave_cluster(terminal)

        if cluster_id not in self.active_clusters:
            self.active_clusters[cluster_id] = []

        self.active_clusters[cluster_id].append(terminal)
        terminal.pulse_cluster_id = cluster_id
        terminal.add_controller(terminal.cluster_key_controller)

    def _leave_cluster(self, terminal):
        if not hasattr(terminal, 'pulse_cluster_id') or terminal.pulse_cluster_id is None:
            return

        cluster_id = terminal.pulse_cluster_id
        if cluster_id in self.active_clusters and terminal in self.active_clusters[cluster_id]:
            self.active_clusters[cluster_id].remove(terminal)
            terminal.remove_controller(terminal.cluster_key_controller)
            if not self.active_clusters[cluster_id]:
                del self.active_clusters[cluster_id]

        terminal.pulse_cluster_id = None

    def _create_local_scripts_submenu(self, terminal, action_group):
        submenu = Gio.Menu()
        all_manual_cmds = {**self.app_config.post_manual_local_cmds, **terminal.pulse_conn.post_manual_local_cmds}

        if not all_manual_cmds:
            no_scripts_item = Gio.MenuItem.new("No scripts defined", None)
            no_scripts_item.set_action_and_target_value("term.no_scripts", GLib.Variant.new_string(""))
            no_scripts_action = Gio.SimpleAction.new("no_scripts", None)
            no_scripts_action.set_enabled(False)
            action_group.add_action(no_scripts_action)
            return submenu

        for i, (name, command) in enumerate(all_manual_cmds.items()):
            action_name = f"run_manual_script_{i}"
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", self._run_manual_local_script, command, terminal.pulse_conn)
            action_group.add_action(action)
            submenu.append(name, f"term.{action_name}")
        return submenu

    def _find_first_terminal_in_widget(self, widget) -> Optional[vte_terminal.VteTerminal]:
        if isinstance(widget, vte_terminal.VteTerminal):
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

    def _find_all_terminals_in_widget(self, widget) -> List[vte_terminal.VteTerminal]:
        terminals = []
        if isinstance(widget, vte_terminal.VteTerminal):
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

    def _run_manual_local_script(self, action, param, cmd, conn):
        substituted_cmd = utils.substitute_variables(cmd, conn)
        def on_finished(subprocess, result, cmd, conn_uuid):
            try:
                ok, stdout, stderr = subprocess.communicate_utf8_finish(result)
                history_item = command_history_item.CommandHistoryItem(
                    command=substituted_cmd,
                    stdout=stdout,
                    stderr=stderr,
                    ok=ok,
                )
                if conn_uuid not in self.command_history:
                    self.command_history[conn_uuid] = []
                self.command_history[conn_uuid].append(history_item)
                self.commands_history_view.populate_tree()
                self.toast_overlay.add_toast(Adw.Toast.new(f"Script finished: {substituted_cmd}"))
                if not ok:
                    self.show_error_dialog("Manual Script Failed", f"Command failed:\n{substituted_cmd}\n\n{stderr}")
            except GLib.Error as e:
                if not e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                    self.show_error_dialog("Manual Script Failed", f"Command failed:\n{substituted_cmd}\n\n{e.message}")
            self.post_cmd_subprocesses.remove(subprocess)

        try:
            subprocess = Gio.Subprocess.new([self.app_config.shell_program, '-c', substituted_cmd], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            self.post_cmd_subprocesses.append(subprocess)
            subprocess.communicate_utf8_async(None, None, on_finished, substituted_cmd, conn.uuid)
        except GLib.Error as e:
            self.show_error_dialog("Manual Script Failed", f"Failed to execute command:\n{substituted_cmd}\n\n{e.message}")

    def build_paned_widget(self, orientation, source_content: Gtk.Widget, target_content: Gtk.Widget) -> Gtk.Paned:
        paned = Gtk.Paned(orientation=orientation, wide_handle=False)
        paned.set_start_child(source_content)
        paned.set_end_child(target_content)

        def set_paned_position(p):
            if p.get_orientation() == Gtk.Orientation.HORIZONTAL:
                p.set_position(p.get_allocated_width() // 2)
            else:
                p.set_position(p.get_allocated_height() // 2)
            return GLib.SOURCE_REMOVE

        paned.connect_after("map", lambda p: GLib.idle_add(set_paned_position, p))

        return paned

    def split_terminal_or_tab(self, action, param, terminal, source_page, source_page_idx, orientation, target_page, target_page_idx):
        if self.app_config.split_at_root or not terminal:
            self.split_tab(terminal, source_page, source_page_idx, orientation, target_page, target_page_idx)
        else:
            self.split_terminal(terminal, source_page, source_page_idx, orientation, target_page, target_page_idx)
        self.updatePageTitle(source_page)

    def split_tab(self, terminal, source_page, source_page_idx, orientation, target_page, target_page_idx):
        source_container = source_page.get_child()
        source_content = source_container.get_first_child()
        source_content.unparent()

        if not target_page:
            if not terminal:
                return
            if not hasattr(terminal, 'pulse_conn'):
                return
            target_content = self.create_terminal(terminal.pulse_conn)
        else:
            target_container = target_page.get_child()
            target_content = target_container.get_first_child()
            target_content.unparent()
            self.notebook.close_page(target_page)

        paned = self.build_paned_widget(orientation, source_content, target_content)

        source_container.append(paned)

    def split_terminal(self, terminal, source_page, source_page_idx, orientation, target_page, target_page_idx):
        source_scrolled_window = terminal.get_parent()
        parent = source_scrolled_window.get_parent()
        if not parent:
            return

        if isinstance(parent, Gtk.Box):
            self.split_tab(terminal, source_page, source_page_idx, orientation, target_page, target_page_idx)
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
                target_content = self.create_terminal(terminal.pulse_conn)
            else:
                target_container = target_page.get_child()
                target_content = target_container.get_first_child()
                target_content.unparent()
                self.notebook.close_page(target_page)

            paned = self.build_paned_widget(orientation, source_scrolled_window, target_content)

            if is_start_child:
                parent.set_start_child(paned)
            else:
                parent.set_end_child(paned)

    def unsplit_terminal(self, action, param, terminal, source_page):
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
            page = self.notebook.append(boxy)
            self.updatePageTitle(page)

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
                term = self._find_first_terminal_in_widget(sibling)
                if term:
                    term.grab_focus()

            self.updatePageTitle(source_page)

    def close_terminal(self, action, param, terminal, source_page):
        self._leave_cluster(terminal)
        source_scrolled_window = terminal.get_parent()
        parent = source_scrolled_window.get_parent()
        if not parent:
            return
        if isinstance(parent, Gtk.Box):
            self.notebook.close_page(source_page)
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
                term = self._find_first_terminal_in_widget(sibling)
                if term:
                    term.grab_focus()

            self.updatePageTitle(source_page)

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

    def on_terminal_child_exited(self, terminal: vte_terminal.VteTerminal, status: int, conn: connection.Connection):
        terminal.connected = False

        page = terminal.get_ancestor_page()
        if not page:
            self.show_error_dialog(
                "Internal UI Error",
                "Could not find the parent tab for the disconnected terminal. The tab's status indicator may not update correctly."
            )
            return

        self.updatePageTitle(page)

        behavior = self.app_config.on_disconnect_behavior

        timestamp = GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S")

        def wait_for_key_behavior():
            message = f"\r\n\r\n --- SSH connection closed at {timestamp}.\r\n --- Press Enter to restart.\r\n --- Press Esc to close terminal.\r\n"
            terminal.feed(message.encode('utf-8'))

            evk = Gtk.EventControllerKey()
            def on_key_pressed(controller, keyval, keycode, state):
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    terminal.remove_controller(evk)
                    self.replace_terminal(terminal, self.create_terminal(conn))
                    return True
                if keyval == Gdk.KEY_Escape:
                    terminal.remove_controller(evk)
                    self.close_terminal(None, None, terminal, page)
                    return True
                return False
            evk.connect("key-pressed", on_key_pressed)
            terminal.add_controller(evk)

        if behavior == "close":
            self.close_terminal(None, None, terminal, page)
        elif behavior == "restart":
            connect_duration = GLib.get_monotonic_time() - terminal.connect_time
            if connect_duration < 5 * 1_000_000:
                self.toast_overlay.add_toast(Adw.Toast.new(f"Restart loop detected for '{conn.name}'. Pausing auto-restart."))
                wait_for_key_behavior()
            else:
                self.replace_terminal(terminal, self.create_terminal(conn))
        elif behavior == "wait_for_key":
            wait_for_key_behavior()

    def replace_terminal(self, old_terminal: vte_terminal.VteTerminal, new_scrolled_window: Gtk.ScrolledWindow):
        page = old_terminal.get_ancestor_page()

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
            self.updatePageTitle(page)

    def show_error_dialog(self, title, message):
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()
