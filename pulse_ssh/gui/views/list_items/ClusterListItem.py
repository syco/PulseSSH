#!/usr/bin/env python

from gi.repository import GObject  # type: ignore
import pulse_ssh.data.Cluster as _cluster

class ClusterListItem(GObject.Object):
    def __init__(self, cluster_data: _cluster.Cluster):
        super().__init__()
        self.name = cluster_data.name
        self.icon_name = "view-group-symbolic"
        self.cluster_data = cluster_data
