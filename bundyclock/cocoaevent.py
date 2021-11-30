import Foundation
from AppKit import NSObject
from PyObjCTools import AppHelper
import logging

logger = logging.getLogger(__name__)

class GetScreensaver(NSObject):
    outputter = None

    def screenIsLocked_(self, islocked):
        logger.debug('screenIsLocked')
        self.outputter.out_signal()
        # print(islocked)

    def screenIsUnlocked(self):
        logger.debug('screenIsUnLocked')
        self.outputter.in_signal()


class LockScreen(object):
    def __init__(self, outputter):
        self.outputter = outputter
        self.nc = Foundation.NSDistributedNotificationCenter.defaultCenter()
        self.get_screensaver = GetScreensaver.new()
        self.get_screensaver.outputter = outputter
        self.nc.addObserver_selector_name_object_(self.get_screensaver, 'screenIsLocked:', 'com.apple.screenIsLocked', None)
        self.nc.addObserver_selector_name_object_(self.get_screensaver, 'screenIsUnlocked', 'com.apple.screenIsUnlocked', None)

    def start(self):
        try:
            logger.info('Starting eventloop')
            AppHelper.runConsoleEventLoop()
        except KeyboardInterrupt:
            self.outputter.out_signal()
            logger.exception("KeyboardInterrrupt, shutting down")
