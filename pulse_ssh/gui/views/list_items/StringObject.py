#!/usr/bin/env python

from gi.repository import GObject  # type: ignore

class StringObject(GObject.Object):
    __gtype_name__ = 'StringObject'

    id = GObject.Property(type=str)
    name = GObject.Property(type=str)

    def __init__(self, id, name):
        super().__init__()

        self.set_property('id', id)
        self.set_property('name', name)
