import Foundation
from AppKit import NSObject
from PyObjCTools import AppHelper
from .platformctx import PunchStrategy
from .ledgers.factory import get_ledger as ledger_factory
from .systrayapp import SystrayApp

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

        self.app = SystrayApp(ledger=self.ledger, actioncb=self.action)

    def action(self, query):
        if query == 'quit':
            self.ledger.out_signal()
            AppHelper.stopEventLoop()

    def run(self):
        self.app.run_detached()
        try:
            logger.info('Starting eventloop')
            AppHelper.runEventLoop()
        except KeyboardInterrupt:
            self.ledger.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
