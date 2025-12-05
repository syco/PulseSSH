#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from typing import Dict
from typing import List
import pulse_ssh.data.AppConfig as app_config
import pulse_ssh.data.Cluster as cluster
import pulse_ssh.data.Connection as connection
import pulse_ssh.data.HistoryEntry as history_entry
import pulse_ssh.gui.VteTerminal as vte_terminal

__version__ = "0.0.1"
about_info = {
    "description": "An SSH connection manager with terminal multiplexing",
    "developer": "Syco",
    "issue_url": "https://github.com/PulseSSH/PulseSSH.git/issues",
    "license": "GPL-3.0",
    "version": __version__,
    "website": "https://github.com/PulseSSH/PulseSSH.git"
}
active_clusters: Dict[str, List[vte_terminal.VteTerminal]] = {}
all_notebooks: List[Adw.TabView] = []
appy_config: app_config.AppConfig = app_config.AppConfig()
clusters: Dict[str, cluster.Cluster] = {}
command_history: Dict[str, List[history_entry.HistoryEntry]] = {}
config_dir: str = ""
connections: Dict[str, connection.Connection] = {}
readonly: bool = False
