#!/usr/bin/env python

from typing import Dict
import pulse_ssh.data.AppConfig as _app_config
import pulse_ssh.data.Cluster as _cluster
import pulse_ssh.data.Connection as _connection

__version__ = "0.0.1"
about_info = {
    "description": "An SSH connection manager with terminal multiplexing",
    "developer": "Syco",
    "issue_url": "https://github.com/PulseSSH/PulseSSH.git/issues",
    "license": "GPL-3.0",
    "version": __version__,
    "website": "https://github.com/PulseSSH/PulseSSH.git"
}
app_config: _app_config.AppConfig = _app_config.AppConfig()
clusters: Dict[str, _cluster.Cluster] = {}
config_dir: str = ""
connections: Dict[str, _connection.Connection] = {}
readonly: bool = False
