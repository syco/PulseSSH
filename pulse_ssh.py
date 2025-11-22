#!/usr/bin/env python

import argparse
import os
import sys

__version__ = "0.0.1"
about_info = {
    "version": __version__,
    "description": "An SSH connection manager with terminal multiplexing",
    "license": "GPL-3.0",
    "developer": "Syco",
    "website": "https://github.com/syco/PulseSSH",
    "issue_url": "https://github.com/syco/PulseSSH/issues"
}

class VersionInfoAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=0, **kwargs):
        super(VersionInfoAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"PulseSSH {__version__} - {about_info['description']}.")
        print(f"Copyright (c) 2025 {about_info['developer']}.")
        print(f"Find the source code at: {about_info['website']}")
        parser.exit()

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

    if args.ncurses or not os.environ.get('DISPLAY'):
        import libs.CursesWindow as curses_app
        curses_app.CursesWindow(config_dir=args.config_dir).run()
    else:
        import gi
        gi.require_version('Adw', '1')
        gi.require_version('Gdk', '4.0')
        from gi.repository import Adw
        import libs.MainWindow as pulse_ssh
        import signal

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        class PulseSSHApp(Adw.Application):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.connect('activate', self.on_activate)

            def on_activate(self, app):
                self.win = pulse_ssh.MainWindow(
                    self, config_dir=args.config_dir, readonly=args.readonly, about_info=about_info
                )
                self.win.present()

        app = PulseSSHApp(application_id="net.rinaudo.pulse_ssh")
        sys.exit(app.run(sys.argv))
