#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import GObject  # type: ignore
from gi.repository import Gtk  # type: ignore

class PasswordDialog(Adw.Window):
    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, (int, str))
    }

    def __init__(self, parent, title, message, confirm=False):
        super().__init__(transient_for=parent, modal=True)
        self.set_title(title)
        self.set_default_size(400, -1)

        self.confirm = confirm

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        content.append(Gtk.Label(label=message, wrap=True, xalign=0))

        self.password_entry = Adw.PasswordEntryRow(title="Password", activates_default=True)
        content.append(self.password_entry)

        if confirm:
            self.confirm_entry = Adw.PasswordEntryRow(title="Confirm Password", activates_default=True)
            content.append(self.confirm_entry)
            self.password_entry.connect("changed", self._check_match)
            self.confirm_entry.connect("changed", self._check_match)

        self.info_bar = Adw.Banner()
        self.info_bar.set_button_label(None)
        self.info_bar.set_revealed(False)
        content.append(self.info_bar)

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", lambda w: self.emit("response", Gtk.ResponseType.CANCEL, ""))

        self.ok_button = Gtk.Button.new_with_mnemonic("_OK")
        self.ok_button.add_css_class("suggested-action")
        self.ok_button.connect("clicked", self._on_ok_clicked)
        self.set_default_widget(self.ok_button)
        if confirm:
            self.ok_button.set_sensitive(False)

        header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        header_bar.pack_start(cancel_button)
        header_bar.pack_end(self.ok_button)

        toolbar_view = Adw.ToolbarView(content=content)
        toolbar_view.add_top_bar(header_bar)
        self.set_content(toolbar_view)

    def _on_ok_clicked(self, _):
        self.emit("response", Gtk.ResponseType.OK, self.password_entry.get_text())
        self.close()

    def _check_match(self, _):
        p1 = self.password_entry.get_text()
        p2 = self.confirm_entry.get_text()
        if not p1:
            self.info_bar.set_revealed(False)
            self.ok_button.set_sensitive(False)
            return

        if p1 == p2:
            self.info_bar.set_revealed(False)
            self.ok_button.set_sensitive(True)
        else:
            self.info_bar.set_title("Passwords do not match.")
            self.info_bar.set_revealed(True)
            self.ok_button.set_sensitive(False)
