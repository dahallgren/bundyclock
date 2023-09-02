"""
Created on Apr 4, 2013

Copyright (c) 2018 Dan Hallgren  <dan.hallgren@gmail.com>
"""
import dbus
import logging
import os
import pystray
import signal
from pkg_resources import resource_string, resource_filename
from PIL import Image
from time import sleep
from .platformctx import PunchStrategy
from .ledgers import ledger_factory


logger = logging.getLogger(__name__)


class LockScreen(object):
    """ Logger for lock/unlock screen """
    def __init__(self, ledger):
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        from gi.repository import GObject
        self.loop = GObject.MainLoop()
        self.bus = dbus.SessionBus()
        self.ledger = ledger

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
            except dbus.exceptions.DBusException:
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
            self.ledger.out_signal()
        else:
            logger.debug('gnome: unlock screen')
            self.ledger.in_signal()

    def locked_handler(self, sender=None):
        """ hanlde unity lock screen """
        logger.debug('Unity: lock screen')
        self.ledger.out_signal()

    def unlocked_handler(self, sender=None):
        """ handle unity unlock screen """
        logger.debug('Unity unlock screen')
        self.ledger.in_signal()

    def start(self):
        """ start main loop """
        try:
            self.loop.run()
        except KeyboardInterrupt:
            self.ledger.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
        logger.debug('lockscreen loop stopped')

    def stop(self):
        self.loop.quit()


class LinuxStrategy(PunchStrategy):
    def __init__(self, **kwargs):
        self.config = kwargs
        self.ledger = ledger_factory(**self.config)
        self.ledger.in_signal()

        self.app = pystray.Icon(
            'bundyclock',
            icon=Image.open(resource_filename(__name__, 'service_files/bundyclock.png')),
            menu=pystray.Menu(
                pystray.MenuItem('take a break', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('show time today', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('quit', self.after_click),
            )
        )

        # Register sigterm handler
        signal.signal(signal.SIGTERM, self.sigterm_handler)

    def after_click(self, icon, query):
        if str(query) == "quit":
            logger.info("quit by user")
            self.lockscreen.stop()
            icon.stop()
        elif str(query) == 'show time today':
            self.ledger.update_in_out()
            today_time = self.ledger.get_today()
            self.app.notify(f"Start: {today_time.intime}. Time elapsed: {today_time.total}", "Bundyclock")
        elif str(query) == "take a break":
            self.ledger.take_a_break()

    def sigterm_handler(self, *args, **kwargs):
        """ Gracefully shutdown, put last entry to time logger"""
        self.ledger.out_signal()
        self.lockscreen.stop()
        self.app.stop()
        logger.info("Killed by sigterm, shutting down")

    def setup_lockscreen_loop(self, icon):
        self.lockscreen = LockScreen(self.ledger)
        icon.visible = True
        self.lockscreen.start()

    def run(self):
        self.app.run(self.setup_lockscreen_loop)
