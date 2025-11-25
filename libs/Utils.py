#!/usr/bin/env python

from dataclasses import asdict
from dataclasses import fields
from typing import Dict
from typing import Optional
import json
import libs.AppConfig as app_config
import libs.CacheConfig as cache_config
import libs.Cluster as cluster
import libs.Connection as connection
import os
import shlex
import socket
import uuid

local_connection = connection.Connection(
    name="Local",
    uuid="local",
    type="local"
)

def load_themes() -> Dict:
    themes = {}
    seen_colors = {}
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    themes_path = os.path.join(project_root, 'res', 'themes.json')

    if os.path.exists(themes_path):
        with open(themes_path, 'r') as f:
            themes_data = json.load(f)

        for theme in themes_data:
            theme_name = theme.get("name")
            if not theme_name:
                continue

            for key, value in theme.items():
                if isinstance(value, str) and key != "name":
                    theme[key] = value.upper()

            if theme_name in themes:
                print(f"Warning: Duplicate theme name found: '{theme_name}'. The previous entry will be overwritten.")

            color_data = {k: v for k, v in theme.items() if k != 'name'}
            color_tuple = tuple(sorted(color_data.items()))

            if color_tuple in seen_colors:
                print(f"Warning: Theme '{theme_name}' has the same colors as '{seen_colors[color_tuple]}'.")
            else:
                seen_colors[color_tuple] = theme_name

            themes[theme_name] = theme

    return themes

def load_app_config(config_dir: str) -> (app_config.AppConfig, Dict[str, connection.Connection], Dict[str, cluster.Cluster]):
    if config_dir is None:
        config_dir = os.path.expanduser("~/.config/pulse_ssh")

    cfg_path = os.path.join(config_dir, "settings.json")

    app_config_ = app_config.AppConfig()
    connections_ = {}
    clusters_ = {}

    if os.path.exists(cfg_path):
        with open(cfg_path, 'r') as f:
            data = json.load(f) or {}

        tmp_data = data.get('config', {})
        if tmp_data:
            afields = {f.name for f in fields(app_config.AppConfig)}
            filtered = {k: v for k, v in tmp_data.items() if k in afields}
            app_config_ = app_config.AppConfig(**filtered)

        temps_data = data.get('connections', [])
        if temps_data:
            afields = {f.name for f in fields(connection.Connection)}
            for tmp_data in temps_data:
                filtered = {k: v for k, v in tmp_data.items() if k in afields}
                connections_[filtered['uuid']] = connection.Connection(**filtered)

        temps_data = data.get('clusters', [])
        if temps_data:
            afields = {f.name for f in fields(cluster.Cluster)}
            for tmp_data in temps_data:
                filtered = {k: v for k, v in tmp_data.items() if k in afields}
                clusters_[filtered['uuid']] = cluster.Cluster(**filtered)

    return (app_config_, connections_, clusters_)

def save_app_config(config_dir: str, readonly: bool, app_config_: app_config.AppConfig, connections_: Dict[str, connection.Connection], clusters_: Dict[str, cluster.Cluster]):
    if readonly:
        return

    os.makedirs(config_dir, exist_ok=True)
    cfg_path = os.path.join(config_dir, "settings.json")

    data = {
        'config': asdict(app_config_),
        'connections': [asdict(c) for c in connections_.values() if c.uuid != "local"],
        'clusters': [asdict(c) for c in clusters_.values()]
    }
    with open(cfg_path, 'w') as f:
        json.dump(data, f, indent=4)

def load_cache_config(config_dir: str) -> cache_config.CacheConfig:
    if config_dir is None:
        config_dir = os.path.expanduser("~/.config/pulse_ssh")

    cfg_path = os.path.join(config_dir, "cache.json")

    cache_config_ = cache_config.CacheConfig()

    if os.path.exists(cfg_path):
        with open(cfg_path, 'r') as f:
            data = json.load(f) or {}

        cfields = {f.name for f in fields(cache_config.CacheConfig)}
        filtered = {k: v for k, v in data.items() if k in cfields}
        cache_config_ = cache_config.CacheConfig(**filtered)

    return cache_config_

def save_cache_config(config_dir: str, readonly: bool, cache_config_: cache_config.CacheConfig):
    if readonly:
        return

    os.makedirs(config_dir, exist_ok=True)
    cfg_path = os.path.join(config_dir, "cache.json")
    with open(cfg_path, 'w') as f:
        json.dump(asdict(cache_config_), f, indent=4)

def connectionsSortFunction(e: connection.Connection) -> str:
    if not e.folder:
        return f"zzz/{e.name.lower()}"
    return f"{e.folder.lower()}/{e.name.lower()}"

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def substitute_variables(command: str, conn: connection.Connection, proxy_port: Optional[int] = None) -> str:
    if not command:
        return ""

    substitutions = asdict(conn)
    if proxy_port:
        substitutions['proxy_port'] = proxy_port

    for key, value in substitutions.items():
        if value is not None:
            command = command.replace(f'${{{key}}}', str(value))
    return command

def build_ssh_command(app_config: app_config.AppConfig, connection: connection.Connection) -> (str, list, list, Optional[int]):
    ssh_base_cmd = app_config.ssh_path
    if connection.use_sudo:
        ssh_base_cmd = f'{app_config.sudo_path} {ssh_base_cmd}'

    if connection.use_sshpass and connection.password:
        ssh_base_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.password)} {ssh_base_cmd}"

    ssh_cmd_parts = shlex.split(ssh_base_cmd) + ['-p', str(connection.port)]
    if connection.identity_file:
        ssh_cmd_parts += ['-i', connection.identity_file]

    if app_config.ssh_forward_agent: ssh_cmd_parts.append('-A')
    if app_config.ssh_compression: ssh_cmd_parts.append('-C')
    if app_config.ssh_x11_forwarding: ssh_cmd_parts.append('-X')
    if app_config.ssh_verbose: ssh_cmd_parts.append('-v')
    if app_config.ssh_force_pty: ssh_cmd_parts.append('-t')

    if connection.ssh_forward_agent and '-A' not in ssh_cmd_parts: ssh_cmd_parts.append('-A')
    if connection.ssh_compression and '-C' not in ssh_cmd_parts: ssh_cmd_parts.append('-C')
    if connection.ssh_x11_forwarding and '-X' not in ssh_cmd_parts: ssh_cmd_parts.append('-X')
    if connection.ssh_verbose and '-v' not in ssh_cmd_parts: ssh_cmd_parts.append('-v')
    if connection.ssh_force_pty and '-t' not in ssh_cmd_parts: ssh_cmd_parts.append('-t')

    proxy_port = None
    if connection.ssh_unique_sock_proxy:
        proxy_port = get_free_port()
        ssh_cmd_parts.extend(['-D', f'localhost:{proxy_port}'])

    for option in connection.ssh_additional_options:
        substituted_option = substitute_variables(option, connection, proxy_port)
        ssh_cmd_parts.extend(shlex.split(substituted_option))

    ssh_cmd_parts += [connection.host if not connection.user else f"{connection.user}@{connection.host}"]

    all_remote_scripts = app_config.remote_scripts + connection.remote_scripts
    scp_pre_cmds = []
    remote_script_paths = []

    if all_remote_scripts:
        scp_base_cmd = app_config.scp_path
        if connection.use_sudo:
            scp_base_cmd = f"{app_config.sudo_path} {scp_base_cmd}"

        if connection.use_sshpass and connection.password:
            scp_base_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.password)} {scp_base_cmd}"

        for script_path in all_remote_scripts:
            if not os.path.exists(os.path.expanduser(script_path)):
                remote_tmp_path = f"/tmp/pulses-ssh-script-{uuid.uuid4()}"
                remote_script_paths.append(remote_tmp_path)

                scp_cmd_parts = shlex.split(scp_base_cmd) + ['-P', str(connection.port)]
                if connection.identity_file:
                    scp_cmd_parts += ['-i', connection.identity_file]
                scp_cmd_parts += [script_path, f"{connection.user}@{connection.host}:{remote_tmp_path}"]
                scp_pre_cmds.append(" ".join([shlex.quote(part) for part in scp_cmd_parts]))

    add_key_cmd = []
    if connection.identity_file and connection.key_passphrase:
        ssh_add_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.key_passphrase)} ssh-add {shlex.quote(connection.identity_file)}"
        add_key_cmd.append(ssh_add_cmd)

    quoted_ssh_command = " ".join([shlex.quote(part) for part in ssh_cmd_parts])
    all_pre_local_cmds = add_key_cmd + scp_pre_cmds + app_config.pre_local_cmds + connection.pre_local_cmds
    substituted_pre_local_cmds = [substitute_variables(cmd, connection, proxy_port) for cmd in all_pre_local_cmds]
    final_cmd = " && ".join(substituted_pre_local_cmds + [quoted_ssh_command])

    return final_cmd, all_remote_scripts, remote_script_paths, proxy_port

def build_sftp_command(app_config: app_config.AppConfig, connection: connection.Connection) -> (str):
    ssh_base_cmd = app_config.sftp_path
    if connection.use_sudo:
        ssh_base_cmd = f'{app_config.sudo_path} {ssh_base_cmd}'

    if connection.use_sshpass and connection.password:
        ssh_base_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.password)} {ssh_base_cmd}"

    ssh_cmd_parts = shlex.split(ssh_base_cmd) + ['-P', str(connection.port)]
    if connection.identity_file:
        ssh_cmd_parts += ['-i', connection.identity_file]

    for option in connection.ssh_additional_options:
        substituted_option = substitute_variables(option, connection)
        ssh_cmd_parts.extend(shlex.split(substituted_option))

    ssh_cmd_parts += [connection.host if not connection.user else f"{connection.user}@{connection.host}"]

    quoted_ssh_command = " ".join([shlex.quote(part) for part in ssh_cmd_parts])

    return quoted_ssh_command
