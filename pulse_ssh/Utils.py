#!/usr/bin/env python

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dataclasses import asdict
from dataclasses import fields
from typing import Dict
from typing import Optional
import base64
import json
import os
import pulse_ssh.data.AppConfig as _app_config
import pulse_ssh.data.CacheConfig as _cache_config
import pulse_ssh.data.Cluster as _cluster
import pulse_ssh.data.Connection as _connection
import pulse_ssh.Globals as _globals
import shlex
import socket

color_iblue = '\x1b[34;1m'
color_igreen = '\x1b[32;1m'
color_ired = '\x1b[31;1m'
color_iyellow = '\x1b[33;1m'
color_reset = '\x1b[0m'

local_connection = _connection.Connection(
    name="Local",
    uuid="local",
    type="local"
)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENCRYPTION_CANARY_PLAINTEXT = "d11d1ec3692ce6d554068424915baf630064b457"

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derives a cryptographic key from a password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def set_encryption_password(password: str):
    """Sets the global encryption key and creates a new canary."""
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    _globals.encryption_key = key

    fernet = Fernet(key)
    encrypted_canary = fernet.encrypt(ENCRYPTION_CANARY_PLAINTEXT.encode())

    _globals.app_config.encryption_canary = f"{salt.hex()}.{encrypted_canary.hex()}"

def verify_encryption_password(password: str) -> bool:
    """Verifies the password against the encrypted canary."""
    if not _globals.app_config.encryption_canary:
        return False

    try:
        salt_hex, encrypted_canary_hex = _globals.app_config.encryption_canary.split('.')
        salt = bytes.fromhex(salt_hex)
        encrypted_canary = bytes.fromhex(encrypted_canary_hex)

        key = _derive_key(password, salt)
        fernet = Fernet(key)
        decrypted_canary = fernet.decrypt(encrypted_canary)
        if decrypted_canary.decode() == ENCRYPTION_CANARY_PLAINTEXT:
            _globals.encryption_key = key
            return True
    except (InvalidToken, ValueError, TypeError):
        return False
    return False

def encrypt_string(plaintext: str) -> Optional[str]:
    """Encrypts a string using the global encryption key."""
    if not _globals.encryption_key or not plaintext:
        return None
    try:
        fernet = Fernet(_globals.encryption_key)
        encrypted_text = fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted_text).decode()
    except Exception:
        return None

def decrypt_string(encrypted_text: str) -> Optional[str]:
    """Decrypts a string using the global encryption key."""
    if not _globals.encryption_key or not encrypted_text:
        return None
    try:
        fernet = Fernet(_globals.encryption_key)
        decoded_encrypted_text = base64.urlsafe_b64decode(encrypted_text)
        return fernet.decrypt(decoded_encrypted_text).decode()
    except (InvalidToken, ValueError, TypeError):
        return None

def decrypt_all_connections() -> bool:
    """Iterates and decrypts all connection passwords and passphrases."""
    if not _globals.encryption_key:
        return False
    try:
        for conn in _globals.connections.values():
            if conn.password:
                conn.password = decrypt_string(conn.password)
            if conn.key_passphrase:
                conn.key_passphrase = decrypt_string(conn.key_passphrase)
        return True
    except (InvalidToken, ValueError, TypeError):
        return False

def load_themes() -> Dict:
    themes = {}
    seen_colors = {}
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

def load_app_config(config_dir: str) -> tuple[_app_config.AppConfig, Dict[str, _connection.Connection], Dict[str, _cluster.Cluster]]:
    if config_dir is None:
        config_dir = os.path.expanduser("~/.config/pulse_ssh")

    cfg_path = os.path.join(config_dir, "settings.json")

    app_config_ = _app_config.AppConfig()
    connections_ = {}
    clusters_ = {}

    if os.path.exists(cfg_path):
        with open(cfg_path, 'r') as f:
            data = json.load(f) or {}

        tmp_data = data.get('config', {})
        if tmp_data:
            afields = {f.name for f in fields(_app_config.AppConfig)}
            filtered = {k: v for k, v in tmp_data.items() if k in afields}
            app_config_ = _app_config.AppConfig(**filtered)

        temps_data = data.get('connections', [])
        if temps_data:
            afields = {f.name for f in fields(_connection.Connection)}
            for tmp_data in temps_data:
                filtered = {k: v for k, v in tmp_data.items() if k in afields}
                connections_[filtered['uuid']] = _connection.Connection(**filtered)

        temps_data = data.get('clusters', [])
        if temps_data:
            afields = {f.name for f in fields(_cluster.Cluster)}
            for tmp_data in temps_data:
                filtered = {k: v for k, v in tmp_data.items() if k in afields}
                clusters_[filtered['uuid']] = _cluster.Cluster(**filtered)

    return (app_config_, connections_, clusters_)

def save_app_config(config_dir: str, readonly: bool, app_config_: _app_config.AppConfig, connections_: Dict[str, _connection.Connection], clusters_: Dict[str, _cluster.Cluster]):
    if readonly:
        return

    os.makedirs(config_dir, exist_ok=True)
    cfg_path = os.path.join(config_dir, "settings.json")

    connections_to_save = []
    for c in connections_.values():
        if c.uuid == "local":
            continue
        conn_dict = asdict(c)
        if _globals.encryption_key:
            if conn_dict.get('password'):
                conn_dict['password'] = encrypt_string(conn_dict['password'])
            if conn_dict.get('key_passphrase'):
                conn_dict['key_passphrase'] = encrypt_string(conn_dict['key_passphrase'])
        connections_to_save.append(conn_dict)

    data = {
        'config': asdict(app_config_),
        'connections': connections_to_save,
        'clusters': [asdict(c) for c in clusters_.values()]
    }
    with open(cfg_path, 'w') as f:
        json.dump(data, f, indent=4)

def load_cache_config(config_dir: str) -> _cache_config.CacheConfig:
    if config_dir is None:
        config_dir = os.path.expanduser("~/.config/pulse_ssh")

    cfg_path = os.path.join(config_dir, "cache.json")

    cache_config_ = _cache_config.CacheConfig()

    if os.path.exists(cfg_path):
        with open(cfg_path, 'r') as f:
            data = json.load(f) or {}

        cfields = {f.name for f in fields(_cache_config.CacheConfig)}
        filtered = {k: v for k, v in data.items() if k in cfields}
        cache_config_ = _cache_config.CacheConfig(**filtered)

    return cache_config_

def save_cache_config(config_dir: str, readonly: bool, cache_config_: _cache_config.CacheConfig):
    if readonly:
        return

    os.makedirs(config_dir, exist_ok=True)
    cfg_path = os.path.join(config_dir, "cache.json")
    with open(cfg_path, 'w') as f:
        json.dump(asdict(cache_config_), f, indent=4)

def connectionsSortFunction(e: _connection.Connection) -> str:
    if not e.folder:
        return f"/{e.name.lower()}"
    return f"/{e.folder.lower()}/{e.name.lower()}"

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def substitute_variables(command: str, conn: _connection.Connection, proxy_port: Optional[int] = None) -> str:
    if not command:
        return ""

    substitutions = asdict(conn)
    if proxy_port:
        substitutions['proxy_port'] = proxy_port

    for key, value in substitutions.items():
        if value is not None:
            command = command.replace(f'{{{key}}}', str(value))
    return command

def build_ssh_command(app_config: _app_config.AppConfig, connection: _connection.Connection) -> tuple[str, Optional[int]]:
    ssh_base_cmd = app_config.ssh_path
    if connection.use_sudo:
        ssh_base_cmd = f'{app_config.sudo_path} {ssh_base_cmd}'

    if connection.use_sshpass and connection.password:
        ssh_base_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.password)} {ssh_base_cmd}"

    ssh_options = []
    if connection.proxy_jump and connection.proxy_jump in _globals.connections:
        jump_conn = _globals.connections[connection.proxy_jump]
        jump_host_string = jump_conn.host if not jump_conn.user else f"{jump_conn.user}@{jump_conn.host}"
        ssh_options.extend(['-J', jump_host_string])

    ssh_cmd_parts = shlex.split(ssh_base_cmd) + ['-p', str(connection.port)]
    if connection.identity_file:
        ssh_cmd_parts += ['-i', connection.identity_file]

    if app_config.ssh_forward_agent or connection.ssh_forward_agent: ssh_cmd_parts.append('-A')
    if app_config.ssh_compression or connection.ssh_compression: ssh_cmd_parts.append('-C')
    if app_config.ssh_x11_forwarding or connection.ssh_x11_forwarding: ssh_cmd_parts.append('-X')
    if app_config.ssh_verbose or connection.ssh_verbose: ssh_cmd_parts.append('-v')
    if app_config.ssh_force_pty or connection.ssh_force_pty: ssh_cmd_parts.append('-t')

    ssh_cmd_parts.extend(ssh_options)

    proxy_port = None
    if app_config.ssh_unique_sock_proxy or connection.ssh_unique_sock_proxy:
        proxy_port = get_free_port()
        ssh_cmd_parts.extend(['-D', f'localhost:{proxy_port}'])

    combined_options = list(dict.fromkeys(app_config.ssh_additional_options + connection.ssh_additional_options))
    for option in combined_options:
        substituted_option = substitute_variables(option, connection, proxy_port)
        ssh_cmd_parts.extend(shlex.split(substituted_option))

    ssh_cmd_parts += [connection.host if not connection.user else f"{connection.user}@{connection.host}"]

    add_key_cmd = []
    if connection.identity_file and connection.key_passphrase:
        ssh_add_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.key_passphrase)} ssh-add {shlex.quote(connection.identity_file)}"
        add_key_cmd.append(ssh_add_cmd)

    quoted_ssh_command = " ".join([shlex.quote(part) for part in ssh_cmd_parts])
    all_prepend_cmds = add_key_cmd + connection.prepend_cmds
    substituted_prepend_cmds = [substitute_variables(cmd, connection, proxy_port) for cmd in all_prepend_cmds]
    final_cmd = " && ".join(substituted_prepend_cmds + [quoted_ssh_command])

    return final_cmd, proxy_port

def build_sftp_command(app_config: _app_config.AppConfig, connection: _connection.Connection) -> str:
    ssh_base_cmd = app_config.sftp_path
    if connection.use_sudo:
        ssh_base_cmd = f'{app_config.sudo_path} {ssh_base_cmd}'

    if connection.use_sshpass and connection.password:
        ssh_base_cmd = f"{app_config.sshpass_path} -p {shlex.quote(connection.password)} {ssh_base_cmd}"

    ssh_cmd_parts = shlex.split(ssh_base_cmd) + ['-P', str(connection.port)]
    if connection.identity_file:
        ssh_cmd_parts += ['-i', connection.identity_file]

    if connection.proxy_jump and connection.proxy_jump in _globals.connections:
        jump_conn = _globals.connections[connection.proxy_jump]
        jump_host_string = jump_conn.host if not jump_conn.user else f"{jump_conn.user}@{jump_conn.host}"
        ssh_cmd_parts.extend(['-J', jump_host_string])

    combined_options = list(dict.fromkeys(app_config.ssh_additional_options + connection.ssh_additional_options))
    for option in combined_options:
        substituted_option = substitute_variables(option, connection)
        ssh_cmd_parts.extend(shlex.split(substituted_option))

    ssh_cmd_parts += [connection.host if not connection.user else f"{connection.user}@{connection.host}"]

    quoted_ssh_command = " ".join([shlex.quote(part) for part in ssh_cmd_parts])

    return quoted_ssh_command
