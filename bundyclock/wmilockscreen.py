import wmi
import logging
from .platformctx import PunchStrategy
from .ledgers.factory import get_ledger as ledger_factory
from .systrayapp import SystrayApp

logger = logging.getLogger(__name__)


class LockScreen(PunchStrategy):
    def __init__(self, **kwargs):
        self.config = kwargs
        self.ledger = ledger_factory(**self.config)
        self.gui_icon = SystrayApp(ledger=self.ledger, actioncb=self.action)

    def action(self, query):
        pass

    def run(self):
        logger.debug('wmi lockscreen checker started')
        self.ledger.in_signal()

        conn = wmi.WMI()
        watcher = conn.watch_for(
            wmi_class="Win32_Process",
            delay_secs=5,
            Name='LogonUI.exe'
            )

        # start gui main loop
        self.gui_icon.run_detached()

        while True:
            try:
                logonui = watcher(2000)
                if logonui.event_type == 'creation':
                    logger.info('screenIsLocked')
                    self.ledger.out_signal()
                elif logonui.event_type == 'deletion':
                    logger.info('screenIsUnLocked')
                    self.ledger.in_signal()
            except wmi.x_wmi_timed_out:
                pass

            if not self.gui_icon._thread.is_alive():
                logger.debug('gui is dead, quitting')
                break
