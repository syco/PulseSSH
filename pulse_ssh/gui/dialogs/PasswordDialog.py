#!/usr/bin/env python

import gi
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')

from gi.repository import Adw  # type: ignore
from gi.repository import Gdk  # type: ignore
from gi.repository import GObject  # type: ignore
from gi.repository import Gtk  # type: ignore
import re

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

        self.requirements_box = self._create_requirements_box()
        content.append(self.requirements_box)

        if confirm:
            self.confirm_entry = Adw.PasswordEntryRow(title="Confirm Password", activates_default=True)
            content.append(self.confirm_entry)
            self.password_entry.connect("changed", self._update_state)
            self.confirm_entry.connect("changed", self._update_state)
            self.requirements_box.set_visible(True)
        else:
            self.password_entry.connect("changed", self._update_state)
            self.requirements_box.set_visible(False)

        self.info_bar = Adw.Banner()
        self.info_bar.set_button_label(None)
        self.info_bar.set_revealed(False)
        content.append(self.info_bar)

        cancel_button = Gtk.Button.new_with_mnemonic("_Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)

        self.ok_button = Gtk.Button.new_with_mnemonic("_OK")
        self.ok_button.add_css_class("suggested-action")
        self.ok_button.connect("clicked", self._on_ok_clicked)
        self.set_default_widget(self.ok_button)
        self.ok_button.set_sensitive(not confirm)

        header_bar = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        header_bar.pack_start(cancel_button)
        header_bar.pack_end(self.ok_button)

        toolbar_view = Adw.ToolbarView(content=content)
        toolbar_view.add_top_bar(header_bar)
        self.set_content(toolbar_view)

        evk = Gtk.EventControllerKey()
        evk.connect("key-pressed", self.on_key_pressed)
        self.add_controller(evk)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._on_cancel_clicked(None)
            return True

    def _create_requirements_box(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("card")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)

        self.req_checks = {}
        requirements = {
            "length": "At least 8 characters",
            "lower": "A lowercase letter",
            "upper": "An uppercase letter",
            "number": "A number",
            "symbol": "A symbol"
        }

        for key, text in requirements.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            icon = Gtk.Image(icon_name="emblem-important-symbolic")
            label = Gtk.Label(label=text, xalign=0)
            row.append(icon)
            row.append(label)
            box.append(row)
            self.req_checks[key] = icon

        card.append(box)
        return card

    def _on_ok_clicked(self, _):
        self.emit("response", Gtk.ResponseType.OK, self.password_entry.get_text())
        self.close()

    def _on_cancel_clicked(self, _):
        self.emit("response", Gtk.ResponseType.CANCEL, "")
        self.close()

    def _update_state(self, _):
        p1 = self.password_entry.get_text()

        if self.confirm:
            self.requirements_box.set_visible(bool(p1))

        checks = {
            "length": len(p1) >= 8,
            "lower": bool(re.search(r'[a-z]', p1)),
            "upper": bool(re.search(r'[A-Z]', p1)),
            "number": bool(re.search(r'\d', p1)),
            "symbol": bool(re.search(r'[^a-zA-Z\d]', p1))
        }

        all_reqs_met = all(checks.values())

        for key, is_met in checks.items():
            icon_name = "emblem-ok-symbolic" if is_met else "emblem-important-symbolic"
            self.req_checks[key].set_from_icon_name(icon_name)

        if self.confirm:
            p2 = self.confirm_entry.get_text()
            if not p1:
                self.info_bar.set_revealed(False)
                self.ok_button.set_sensitive(False)
                return

            if p1 == p2:
                self.info_bar.set_revealed(False)
                self.ok_button.set_sensitive(all_reqs_met)
            else:
                self.info_bar.set_title("Passwords do not match.")
                self.info_bar.set_revealed(True)
                self.ok_button.set_sensitive(False)
        else:
            self.info_bar.set_revealed(False)
