#!/usr/bin/env python

from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional

@dataclass
class AppConfig:
    font_family: str = "Monospace"
    font_size: int = 12
    theme: str = "WhiteOnBlack"
    custom_css: str = "* { \n    border-radius: 3px;\n}"
    cursor_shape: str = "block"
    split_at_root: bool = False
    on_disconnect_behavior: str = "wait_for_key"
    shell_program: str = "bash"
    color_scheme: str = "default"
    scrollback_lines: int = 10000
    scroll_on_output: bool = True
    scroll_on_keystroke: bool = True
    scroll_on_insert: bool = True
    sidebar_on_right: bool = False
    scrollbar_visible: bool = True
    audible_bell: bool = False
    encryption_enabled: bool = False
    encryption_canary: Optional[str] = None
    ssh_forward_agent: bool = False
    ssh_compression: bool = False
    ssh_x11_forwarding: bool = False
    ssh_verbose: bool = False
    ssh_force_pty: bool = False
    ssh_unique_sock_proxy: bool = False
    ssh_additional_options: List[str] = field(default_factory=list)
    local_cmds: Dict[str, str] = field(default_factory=dict)
    remote_cmds: Dict[str, str] = field(default_factory=dict)
    ssh_path: str = "/usr/bin/ssh"
    sftp_path: str = "/usr/bin/sftp"
    scp_path: str = "/usr/bin/scp"
    sshpass_path: str = "/usr/bin/sshpass"
    sudo_path: str = "/usr/bin/sudo"
