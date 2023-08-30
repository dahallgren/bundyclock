import Foundation
from AppKit import NSObject
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

    def run(self):
        try:
            logger.info('Starting eventloop')
            AppHelper.runConsoleEventLoop()
        except KeyboardInterrupt:
            self.ledger.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
