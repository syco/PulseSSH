#!/usr/bin/env python

from gi.repository import GObject  # type: ignore
import pulse_ssh.data.Cluster as _cluster

class ClusterListItem(GObject.Object):
    __gtype_name__ = 'ClusterListItem'

    name = GObject.Property(type=str)

    def __init__(self, cluster_data: _cluster.Cluster):
        super().__init__()
        self.set_property('name', cluster_data.name)
        self.icon_name = "view-group-symbolic"
        self.cluster_data = cluster_data

    def get_name(self):
        return self.get_property('name')
