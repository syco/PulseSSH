#!/usr/bin/env python

from typing import Optional
import argparse
import os
import pulse_ssh.Globals as _globals
import pulse_ssh.Utils as _utils
import sys

class VersionInfoAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=0, **kwargs):
        super(VersionInfoAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string: Optional[str] = None):
        print(f"PulseSSH {_globals.__version__} - {_globals.about_info['description']}.")
        print(f"Copyright (c) 2025 {_globals.about_info['developer']}.")
        print(f"Find the source code at: {_globals.about_info['website']}")
        parser.exit()

def run_gtk_app(args):
    try:
        import gi
        gi.require_version('Adw', '1')
        gi.require_version('Gdk', '4.0')
        gi.require_version('Gtk', '4.0')
        gi.require_version('Vte', '3.91')

        from gi.repository import Adw  # type: ignore
        from gi.repository import GLib  # type: ignore
        import pulse_ssh.gui.Globals as _gui_globals
        import pulse_ssh.gui.MainWindow as _main_window
        import signal

        class PulseSSHApp(Adw.Application):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.add_main_option(
                    "config-dir",
                    0,
                    GLib.OptionFlags.NONE,
                    GLib.OptionArg.STRING,
                    "Path to the configuration directory",
                    "path"
                )
                self.add_main_option(
                    "readonly",
                    0,
                    GLib.OptionFlags.NONE,
                    GLib.OptionArg.NONE,
                    "Run in read-only mode",
                    None
                )
                self.connect('activate', self.on_activate)
                self.connect('handle-local-options', self.on_handle_local_options)

            def on_handle_local_options(self, app, options):
                _globals.config_dir = options.lookup_value("config-dir", None)
                if _globals.config_dir:
                    _globals.config_dir = _globals.config_dir.get_string()
                else:
                    _globals.config_dir = os.path.expanduser("~/.config/pulse_ssh")
                _globals.readonly = options.lookup_value("readonly", None) is not None

                return -1

            def on_activate(self, app):
                _globals.app_config, _globals.connections, _globals.clusters = _utils.load_app_config(_globals.config_dir)
                _gui_globals.cache_config = _utils.load_cache_config(_globals.config_dir)

                self.win = _main_window.MainWindow(self)
                self.win.present()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        app = PulseSSHApp(application_id="net.rinaudo.pulse_ssh")
        exit_status = app.run(sys.argv)
        sys.exit(exit_status)

    except ImportError:
        run_curses_app(args)

def run_curses_app(args):
    import pulse_ssh.tui.CursesWindow as _curses_window

    _globals.app_config, _globals.connections, _globals.clusters = _utils.load_app_config(_globals.config_dir)
    _curses_window.CursesWindow().run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="PulseSSH: An SSH connection manager with terminal multiplexing.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
By default, PulseSSH will launch a graphical GTK interface.
If no graphical environment (DISPLAY) is detected, it will fall back to a
terminal-based (ncurses) interface.
"""
    )
    parser.add_argument(
        '--ncurses',
        action='store_true',
        help='Force the terminal-based (ncurses) interface to run, even in a graphical environment.'
    )
    parser.add_argument(
        '--config-dir',
        type=str,
        default=os.path.expanduser("~/.config/pulse_ssh"),
        help='Path to the configuration directory.'
    )
    parser.add_argument(
        '--readonly',
        action='store_true',
        help='Run in read-only mode, disabling all save operations.'
    )
    parser.add_argument(
        '-v', '--version',
        action=VersionInfoAction,
        help="Show version information and exit."
    )
    args = parser.parse_args()

    _globals.config_dir = args.config_dir

    if args.ncurses or not os.environ.get('DISPLAY'):
        run_curses_app(args)
    else:
        run_gtk_app(args)
