"""
Created on Apr 4, 2013

@author: dan
"""
import os
import signal

from time import sleep

import dbus
from dbus.mainloop.glib import DBusGMainLoop


class LockScreen(object):
    """ Logger for lock/unlock screen """
    def __init__(self, outputter):
        DBusGMainLoop(set_as_default=True)
        import gobject
        self.loop = gobject.MainLoop()
        self.bus = dbus.SessionBus()
        self.outputter = outputter

        self.outputter.in_signal()

        self.screen_saver_proxy, is_unity = self._get_screen_saver_proxy()

        if is_unity is True:
            self.screen_saver_proxy.connect_to_signal('Locked', self.locked_handler, sender_keyword='sender')
            self.screen_saver_proxy.connect_to_signal('Unlocked', self.unlocked_handler, sender_keyword='sender')
            print('Enabling unity screen saver watcher')
        else:
            self.screen_saver_proxy.connect_to_signal("ActiveChanged",
                                                      self.gnome_handler,
                                                      dbus_interface='org.gnome.ScreenSaver')
            print('Enabling gnome screen saver watcher')

        # Register sigterm handler
        signal.signal(signal.SIGTERM, self.sigterm_handler)

    def _get_screen_saver_proxy(self):
        """ get dbus proxy object """
        timeout = 10
        ssp = None
        unity = False

        if 'ubuntu' in os.environ.get('DESKTOP_SESSION'):
            unity = True

        # When using systemd user service, we need to retry a couple of times before the bus is ready.
        while not ssp and timeout != 0:
            try:
                if unity:
                    ssp = self.bus.get_object('com.canonical.Unity', '/com/canonical/Unity/Session')
                else:
                    ssp = self.bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            except dbus.exceptions.DBusException as e:
                print('Failed to get dbus object, retrying')
                timeout -= 1
                sleep(1)

        if not ssp:
            raise Exception("Can't connect to screen saver proxy")

        return ssp, unity

    def gnome_handler(self, dbus_screen_active):
        """ handle gnome screen saver signals """
        if int(bool(dbus_screen_active)):
            self.outputter.out_signal()
        else:
            self.outputter.in_signal()

    def locked_handler(self, sender=None):
        """ hanlde unity lock screen """
        self.outputter.out_signal()

    def unlocked_handler(self, sender=None):
        """ handle unity unlock screen """
        self.outputter.in_signal()

    def sigterm_handler(self):
        """ Gracefully shutdown, put last entry to time logger"""
        self.outputter.out_signal()
        print("Killed by sigterm, shutting down")

    def start(self):
        """ start main loop """
        try:
            self.loop.run()
        except KeyboardInterrupt:
            self.outputter.out_signal()
            print("KeyboardInterrrupt, shutting down")
