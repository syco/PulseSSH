#!/usr/bin/env python

from dataclasses import dataclass

@dataclass
class CacheConfig:
    window_width: int = 800
    window_height: int = 600
    window_maximized: bool = False
    sidebar_visible: bool = True