import logging
import logging.handlers
import time
from datetime import datetime


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
ch = logging.TimedRotatingFileHandler('/data/logs/github_sync.log', when='midnight', interval=1, backupCount=0, encoding=None, delay=False, utc=True, atTime=None, errors=None)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s:%(lineno)d - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.info('Logging Configured')
logger.debug('Debug Enabled')


def get_utc_timestamp(with_decimal: bool=False): # pragma: no cover
    epoch = datetime(1970,1,1,0,0,0) 
    now = datetime.utcnow() 
    timestamp = (now - epoch).total_seconds() 
    if with_decimal: 
        return timestamp 
    return int(timestamp) 



while True:
    logger.info('MAIN LOOP')

    time.sleep(30)

