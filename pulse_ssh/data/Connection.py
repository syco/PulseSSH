#!/usr/bin/env python

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Dict
from typing import List
from typing import Optional
import uuid

@dataclass
class Connection:
    name: str
    type: str = "ssh"
    host: str = ""
    port: int = 22
    user: str = ""
    password: Optional[str] = None
    identity_file: Optional[str] = None
    key_passphrase: Optional[str] = None
    folder: Optional[str] = None
    pre_local_cmds: List[str] = field(default_factory=list)
    post_local_cmds: List[str] = field(default_factory=list)
    post_remote_cmds: List[str] = field(default_factory=list)
    remote_scripts: List[str] = field(default_factory=list)
    post_manual_local_cmds: Dict[str, str] = field(default_factory=dict)
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    ssh_forward_agent: bool = False
    ssh_compression: bool = False
    ssh_x11_forwarding: bool = False
    ssh_verbose: bool = False
    ssh_force_pty: bool = False
    ssh_additional_options: List[str] = field(default_factory=list)
    ssh_unique_sock_proxy: bool = False
    use_sudo: bool = False
    use_sshpass: bool = False

    def get_cloned_connection(self) -> "Connection":
        new_conn_dict = asdict(self)
        new_conn_dict['uuid'] = str(uuid.uuid4())

        for f in fields(self):
            if f.default_factory is list:
                new_conn_dict[f.name] = list(new_conn_dict[f.name])
        return Connection(**new_conn_dict)
