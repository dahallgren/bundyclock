"""
Created on Apr 4, 2013

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>
"""
import os
import signal

from time import sleep

import dbus
from dbus.mainloop.glib import DBusGMainLoop

import logging

logger = logging.getLogger(__name__)


class LockScreen(object):
    """ Logger for lock/unlock screen """
    def __init__(self, outputter):
        DBusGMainLoop(set_as_default=True)
        from gi.repository import GObject
        self.loop = GObject.MainLoop()
        self.bus = dbus.SessionBus()
        self.outputter = outputter

        self.outputter.in_signal()

        self.screen_saver_proxy, is_unity = self._get_screen_saver_proxy()

        if is_unity is True:
            self.screen_saver_proxy.connect_to_signal('Locked', self.locked_handler, sender_keyword='sender')
            self.screen_saver_proxy.connect_to_signal('Unlocked', self.unlocked_handler, sender_keyword='sender')
            logger.info('Enabling unity screen saver watcher')
        else:
            self.screen_saver_proxy.connect_to_signal("ActiveChanged",
                                                      self.gnome_handler,
                                                      dbus_interface='org.gnome.ScreenSaver')
            logger.info('Enabling gnome screen saver watcher')

        # Register sigterm handler
        signal.signal(signal.SIGTERM, self.sigterm_handler)

    def _get_screen_saver_proxy(self):
        """ get dbus proxy object """
        timeout = 20
        ssp = None
        unity = False

        # When using systemd user service, we need to retry a couple of times before the bus is ready.
        while not ssp and timeout != 0:

            try:
                if 'ubuntu' in os.environ.get('DESKTOP_SESSION'):
                    unity = True
            except TypeError:
                logger.warning("Failed to get DESKTOP_SESSION env, retrying")
                timeout -= 1
                sleep(1)
                continue

            try:
                if unity:
                    ssp = self.bus.get_object('com.canonical.Unity', '/com/canonical/Unity/Session')
                else:
                    ssp = self.bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            except dbus.exceptions.DBusException as e:
                logger.info('Failed to get dbus object, retrying')
                timeout -= 1
                sleep(1)

        if not ssp:
            raise Exception("Can't connect to screen saver proxy")

        return ssp, unity

    def gnome_handler(self, dbus_screen_active):
        """ handle gnome screen saver signals """
        if dbus_screen_active:
            logger.debug('gnome: lock screen')
            self.outputter.out_signal()
        else:
            logger.debug('gnome: unlock screen')
            self.outputter.in_signal()

    def locked_handler(self, sender=None):
        """ hanlde unity lock screen """
        logger.debug('Unity: lock screen')
        self.outputter.out_signal()

    def unlocked_handler(self, sender=None):
        """ handle unity unlock screen """
        logger.debug('Unity unlock screen')
        self.outputter.in_signal()

    def sigterm_handler(self, *args, **kwargs):
        """ Gracefully shutdown, put last entry to time logger"""
        self.outputter.out_signal()
        logger.info("Killed by sigterm, shutting down")

    def start(self):
        """ start main loop """
        try:
            self.loop.run()
        except KeyboardInterrupt:
            self.outputter.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
