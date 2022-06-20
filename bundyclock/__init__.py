import logging
import sys

LOG_FORMAT = "%(asctime)s  %(name)s  %(levelname)s: %(message)s"

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=LOG_FORMAT)
