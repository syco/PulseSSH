#!/usr/bin/python

import curses
import pulse_ssh.Utils as utils
import signal
import subprocess
import sys
import traceback

class CursesWindow:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.app_config, self.connections, self.clusters = utils.load_app_config(self.config_dir)
        self.original_tree = self._build_tree_structure()

    def run(self):
        try:
            curses.wrapper(self._curses_main)
        except Exception as e:
            curses.endwin()
            print(f"An error occurred: {e}")
            print(traceback.format_exc())

    def _cleanup_and_exit(self, signum, frame):
        sys.exit(0)

    def _build_tree_structure(self):
        tree = {}

        for conn_uuid, conn in self.connections.items():
            folder = conn.folder
            if not folder:
                folder = 'Uncategorized'
            parts = folder.split('/')
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[conn.name] = conn_uuid
        return self._sort_tree(tree)

    def _sort_tree(self, tree):
        sorted_tree = {}
        for key in sorted(tree.keys()):
            if isinstance(tree[key], dict):
                sorted_tree[key] = self._sort_tree(tree[key])
            else:
                sorted_tree[key] = tree[key]
        return sorted_tree

    def _search_tree(self, tree, query):
        if not query:
            return tree
        result = {}
        for key, value in tree.items():
            if isinstance(value, dict):
                sub_result = self._search_tree(value, query)
                if sub_result:
                    result[key] = sub_result
            else:
                conn_details = self.connections.get(value)
                if conn_details and (query.lower() in conn_details.name.lower() or query.lower() in conn_details.host.lower()):
                    result[key] = value
        return result

    def _draw_tree(self, window, tree, selected_path, y_offset, height, scroll_offset, collapsed, prefix="", level=0):
        paths = []
        y = y_offset
        all_paths = []

        def collect_paths(subtree, subprefix, sublevel):
            for k, v in sorted(subtree.items()):
                path = f"{subprefix}/{k}".strip('/')
                all_paths.append((path, k, v, sublevel))
                if isinstance(v, dict) and path not in collapsed:
                    collect_paths(v, path, sublevel + 1)

        collect_paths(tree, prefix, level)

        visible_paths = all_paths[scroll_offset:scroll_offset + (height - y_offset)]

        for path, key, value, lvl in visible_paths:
            indent = '  ' * lvl
            if isinstance(value, dict) and 'uuid' not in value:
                marker = "[-]" if path not in collapsed else "[+]"
                window.addstr(y, 0, f"{indent}{marker} {key}", curses.color_pair(1) if path == selected_path else curses.A_NORMAL)
            else:
                window.addstr(y, 0, f"{indent}{key}", curses.color_pair(2) if path == selected_path else curses.A_NORMAL)
            paths.append((path, value))
            y += 1

        return paths

    def _curses_main(self, stdscr):
        signal.signal(signal.SIGINT, self._cleanup_and_exit)

        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)

        current_query = ""
        filtered_tree = self.original_tree
        selected_path = None
        uuid_to_execute = None
        scroll_offset = 0
        collapsed = set()

        while True:
            stdscr.clear()

            max_tree_height = curses.LINES - 5

            stdscr.addstr(0, 0, "Tree:", curses.A_UNDERLINE)

            paths = self._draw_tree(stdscr, filtered_tree, selected_path, 1, max_tree_height + 1, scroll_offset, collapsed)

            stdscr.hline(max_tree_height + 1, 0, '-', curses.COLS)

            stdscr.addstr(max_tree_height + 2, 0, "Search: " + current_query, curses.A_BOLD)

            stdscr.addstr(max_tree_height + 4, 0, "Press Enter to Execute | Press CTRL+C to Quit", curses.A_DIM)

            stdscr.refresh()

            key = stdscr.getch()

            if paths:
                path_list = [p[0] for p in paths]
                current_index = path_list.index(selected_path) if selected_path in path_list else -1

                if key == curses.KEY_DOWN:
                    if current_index + 1 < len(paths):
                        selected_path = paths[current_index + 1][0]
                        uuid_to_execute = paths[current_index + 1][1]

                        if current_index + 2 >= max_tree_height:
                            scroll_offset += 1

                elif key == curses.KEY_UP:
                    if current_index > 0:
                        selected_path = paths[current_index - 1][0]
                        uuid_to_execute = paths[current_index - 1][1]

                        if current_index - 1 < scroll_offset:
                            scroll_offset -= 1

                elif key == curses.KEY_NPAGE:
                    scroll_offset = min(scroll_offset + max_tree_height, max(len(paths) - max_tree_height, 0))
                    selected_path = paths[min(current_index + max_tree_height, len(paths) - 1)][0]

                elif key == curses.KEY_PPAGE:
                    scroll_offset = max(scroll_offset - max_tree_height, 0)
                    selected_path = paths[max(current_index - max_tree_height, 0)][0]

            if key == 32:
                if selected_path and isinstance(filtered_tree, dict):
                    if selected_path in collapsed:
                        collapsed.remove(selected_path)
                    else:
                        collapsed.add(selected_path)

            elif key == 10:
                conn_details = self.connections.get(uuid_to_execute)
                final_cmd, all_remote_scripts, remote_script_paths, proxy_port = utils.build_ssh_command(self.app_config, conn_details)

                if final_cmd:
                    curses.endwin()
                    subprocess.run(final_cmd, shell=True)
                    curses.doupdate()

            elif key == curses.KEY_BACKSPACE or key == 127:
                current_query = current_query[:-1]
                filtered_tree = self._search_tree(self.original_tree, current_query)
                selected_path = None
                scroll_offset = 0

            elif 32 <= key <= 126:
                current_query += chr(key)
                filtered_tree = self._search_tree(self.original_tree, current_query)
                selected_path = None
                scroll_offset = 0
