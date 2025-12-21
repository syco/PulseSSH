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
    tree_colors_enabled: bool = True
    tree_color_folder: Optional[str] = None
    tree_color_ssh: Optional[str] = None
    tree_color_mosh: Optional[str] = None
    tree_color_sftp: Optional[str] = None
    tree_color_ftp: Optional[str] = None
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
    use_adw_window: bool = False
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
    ssh_remote_cmds: Dict[str, str] = field(default_factory=dict)
    ssh_local_cmds: Dict[str, str] = field(default_factory=dict)
    mosh_local_echo: str = "adaptive"
    sftp_forward_agent: bool = False
    sftp_compression: bool = False
    sftp_verbose: bool = False
    sftp_additional_options: List[str] = field(default_factory=list)
    ftp_active: bool = False
    ftp_passive: bool = False
    ftp_trace: bool = False
    ftp_verbose: bool = False
    ssh_path: str = "ssh"
    mosh_path: str = "mosh"
    sftp_path: str = "sftp"
    ftp_path: str = "ftp"
    sshpass_path: str = "sshpass"
    sudo_path: str = "sudo"
