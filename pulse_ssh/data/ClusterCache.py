#!/usr/bin/env python

from dataclasses import dataclass
from typing import List
import pulse_ssh.gui.VteTerminal as _vte_terminal

@dataclass
class ClusterCache:
    def __init__(self, name: str, terminals: List[_vte_terminal.VteTerminal]):
        self.name = name
        self.terminals = terminals
