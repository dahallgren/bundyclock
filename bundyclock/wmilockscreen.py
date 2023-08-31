import wmi
import logging
import pystray
from pkg_resources import resource_filename
from PIL import Image
from queue import Queue, Empty
from .platformctx import PunchStrategy
from .ledgers import ledger_factory

logger = logging.getLogger(__name__)


class LockScreen(PunchStrategy):
    def __init__(self, **kwargs):
        self.config = kwargs
        self.ledger = ledger_factory(**self.config)
        self.queue = Queue()

        self.gui_icon = pystray.Icon(
            'bundyclock',
            icon=Image.open(resource_filename(__name__, 'service_files/bundyclock.png')),
            title="Bundyclock",
            menu=pystray.Menu(
                pystray.MenuItem('take a break', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('show time today', self.after_click),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('quit', self.after_click),
            )
        )

    def after_click(self, icon, query):
        if str(query) == "show time today":
            self.queue.put("notify_today")
        elif str(query) == "quit":
            logger.info("quit by user")
            icon.stop()
        elif str(query) == "take a break":
            self.queue.put('take_a_break')

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

            try:
                message = self.queue.get(block=False)
                logger.debug(f"got message: {message}")
            except Empty:
                message = None
            if message == "notify_today":
                self.ledger.update_in_out()
                today_time = self.ledger.get_today()
                self.gui_icon.notify(f"Start: {today_time.intime}. Time elapsed: {today_time.total}", "Bundyclock")
            elif message == "take_a_break":
                self.ledger.take_a_break()
