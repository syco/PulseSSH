#!/usr/bin/env python

from gi.repository import GObject

class ClusterListItem(GObject.Object):
    def __init__(self, cluster_data):
        super().__init__()
        self.name = cluster_data.name
        self.icon_name = "drive-multidisk-symbolic"
        self.cluster_data = cluster_data
