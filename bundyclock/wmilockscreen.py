import wmi
import logging

logger = logging.getLogger(__name__)


class LockScreen(object):
    def __init__(self, outputter):
        self.outputter = outputter

    def start(self):
        logger.debug('wmi lockscreen checker started')
        self.outputter.in_signal()

        conn = wmi.WMI()
        watcher = conn.watch_for(
            wmi_class="Win32_Process",
            delay_secs=5,
            Name='LogonUI.exe'
            )

        while True:
            logonui = watcher()
            if logonui.event_type == 'creation':
                logger.debug('screenIsLocked')
                self.outputter.out_signal()
            elif logonui.event_type == 'deletion':
                logger.debug('screenIsUnLocked')
                self.outputter.in_signal()
