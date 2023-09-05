import Foundation
import pystray
from AppKit import NSObject
from pkg_resources import resource_filename
from PIL import Image
from PyObjCTools import AppHelper
from .ledgers import ledger_factory
from .platformctx import PunchStrategy

import logging

logger = logging.getLogger(__name__)


class GetScreensaver(NSObject):
    ledger = None

    def screenIsLocked_(self, islocked):
        logger.debug('screenIsLocked')
        self.ledger.out_signal()

    def screenIsUnlocked(self):
        logger.debug('screenIsUnLocked')
        self.ledger.in_signal()


class LockScreen(PunchStrategy):
    def __init__(self, **kwargs):
        self.config = kwargs
        self.ledger = ledger_factory(**self.config)

        self.nc = Foundation.NSDistributedNotificationCenter.defaultCenter()
        self.get_screensaver = GetScreensaver.new()
        self.get_screensaver.ledger = self.ledger
        self.nc.addObserver_selector_name_object_(self.get_screensaver, 'screenIsLocked:', 'com.apple.screenIsLocked', None)
        self.nc.addObserver_selector_name_object_(self.get_screensaver, 'screenIsUnlocked', 'com.apple.screenIsUnlocked', None)

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

    def after_click(self, icon, query):
        if str(query) == "quit":
            logger.info("quit by user")
            icon.stop()
        elif str(query) == 'show time today':
            self.ledger.update_in_out()
            today_time = self.ledger.get_today()
            self.app.notify(f"Start: {today_time.intime}. Time elapsed: {today_time.total}\n"
                            f"Breaks {today_time.num_breaks} - {today_time.break_time}",
                            "Bundyclock")
        elif str(query) == "take a break":
            self.ledger.take_a_break()

    def run(self):
        self.app.run_detached()
        try:
            logger.info('Starting eventloop')
            AppHelper.runEventLoop()
        except KeyboardInterrupt:
            self.ledger.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
