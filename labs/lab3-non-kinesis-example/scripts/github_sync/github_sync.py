import logging
import logging.handlers
import time


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.handlers.SysLogHandler(address='localhost')

logger.addHandler(handler)

logger.debug('this is debug')
logger.critical('this is critical')

while True:
    logger.info('MAIN LOOP')

    time.sleep(30)

