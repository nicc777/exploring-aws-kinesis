import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
# Other imports here...


def get_logger(level=logging.INFO):
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    formatter = logging.Formatter('%(funcName)s:%(lineno)d -  %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)    
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(level)

    # Disable Boto3 Debug Logging - see https://stackoverflow.com/questions/1661275/disable-boto-logging-without-modifying-the-boto-files
    logging.getLogger('boto3').setLevel(logging.INFO)
    logging.getLogger('botocore').setLevel(logging.INFO)
    logging.getLogger('s3transfer').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)

    return logger


def get_client(client_name: str, region: str='eu-central-1', boto3_clazz=boto3):
    return boto3_clazz.client(client_name, region_name=region)


CACHE_TTL_DEFAULT = 600
cache = dict()

def get_utc_timestamp(with_decimal: bool = False):
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    now = datetime.utcnow()
    timestamp = (now - epoch).total_seconds()
    if with_decimal:
        return timestamp
    return int(timestamp)
    
    
def get_debug()->bool:
    try:
        return bool(int(os.getenv('DEBUG', '0')))
    except:
        pass
    return False
    

def get_cache_ttl(logger=get_logger())->int:
    try:
        return int(os.getenv('CACHE_TTL', '{}'.format(CACHE_TTL_DEFAULT)))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return CACHE_TTL_DEFAULT


def refresh_environment_cache(logger=get_logger()):
    global cache
    now = get_utc_timestamp(with_decimal=False)
    if 'Environment' in cache:
        if cache['Environment']['Expiry'] > now:
            return
    cache['Environment'] = {
        'Expiry': get_utc_timestamp() + get_cache_ttl(logger=logger),
        'Data': {
            'CACHE_TTL': get_cache_ttl(logger=logger),
            'DEBUG': get_debug(),
            # Other ENVIRONMENT variables can be added here... The environment will be re-read after the CACHE_TTL 
        }
    }
    logger.debug('cache: {}'.format((json.dumps(cache))))


def debug_log(message: str, variables_as_dict: dict=dict(), variable_as_list: list=list(), logger=get_logger(level=logging.INFO)):
    """
        See:
            https://docs.python.org/3/library/stdtypes.html#str.format
            https://docs.python.org/3/library/string.html#formatstrings

        For this function, the `message` is expected to contain key word variable place holders and the `variables` dict must hold a dictionary with the values matched to the keywords

        Example:

            >>> d = {'one': 1, 'number-two': 'two', 'SomeBool': True}
            >>> message = 'one = {one} and the number {number-two}. Yes, it is {SomeBool}'
            >>> message.format(**d)
            'one = 1 and the number two. Yes, it is True'

            >>> l = ('one', 2, True)
            >>> message = '{} and {}'
            >>> message.format(*l)
            'one and 2'

    """
    if cache['Environment']['Data']['DEBUG'] is True:
        try:
            caller = getframeinfo(stack()[1][0])
            caller_str = '{}():{}'.format(caller.function, caller.lineno)
            message = '[{}]  {}'.format(caller_str, message)
            if len(variables_as_dict) > 0:
                logger.debug(message.format(**variables_as_dict))
            else:
                logger.debug(message.format(*variable_as_list))
        except:
            pass


###############################################################################
###                                                                         ###
###                      A W S    I N T E G R A T I O N                     ###
###                                                                         ###
###############################################################################


def get_s3_object_payload(
    s3_bucket: str,
    s3_key: str,
    boto3_clazz=boto3,
    logger=get_logger()
)->str:
    key_json_data = ''
    try:
        client=get_client(client_name="s3", boto3_clazz=boto3_clazz)
        response = client.get_object(
            Bucket=s3_bucket,
            Key=s3_key
        )
        debug_log('response={}', variable_as_list=[response,], logger=logger)
        if 'Body' in response:
            key_json_data = response['Body'].read().decode('utf-8')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log('key_json_data={}', variable_as_list=[key_json_data,], logger=logger)
    return key_json_data


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


SUPPORTED_EVENTS = (
    'ObjectCreated:Put',
)

ACCEPTABLE_KEY_PREFIXES = (
    'cash_deposit_',
    'verify_cash_deposit_',
    'cash_withdrawal_',
    'incoming_payment_',
    'outgoing_payment_unverified_',
    'outgoing_payment_verified_',
    'outgoing_payment_rejected_',
    'inter_account_transfer_',
)


def extract_body_messages_from_event_record(event_record: dict, logger=get_logger())->dict:
    event_body_messages = dict()
    try:
        event_record_body = json.loads(event_record['body'])
        event_body_messages = json.loads(event_record_body['Message'])
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log('event_body_messages={}', variable_as_list=[event_body_messages,], logger=logger)
    return event_body_messages


def extract_s3_record_from_event_body_message_record(event_body_message_record: dict, logger=get_logger())->dict:
    s3_record = dict()
    try:
        if event_body_message_record['eventSource'] == 'aws:s3':
            if event_body_message_record['eventName'] in SUPPORTED_EVENTS:
                s3_record = event_body_message_record['s3']
                logger.info('ACCEPTED S3 RECORD: s3_record={}'.format(s3_record))
            else:
                logger.warning('Unsupported event type: {}'.format(event_body_message_record['eventName']))
        else:
            logger.error('Not an S3 event. Event Source: {}'.format(event_body_message_record['eventSource']))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        logger.error('REJECT S3 RECORD: event_body_message_record={}'.format(event_body_message_record))
    debug_log('s3_record={}', variable_as_list=[s3_record,], logger=logger)
    return s3_record


def extract_s3_event_messages(event: dict, logger=get_logger())->tuple:
    messages = list()
    try:
        for record in event['Records']:
            event_record_body_message = extract_body_messages_from_event_record(event_record=record, logger=logger)
            for s3_record in event_record_body_message['Records']:
                extracted_s3_record = extract_s3_record_from_event_body_message_record(event_body_message_record=s3_record, logger=logger)
                if extracted_s3_record:
                    if len(extracted_s3_record) > 0:
                        messages.append(extracted_s3_record)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    logger.info('ACCEPTED RECORDS QTY: {}'.format(len(messages)))
    return tuple(messages)


def validate_key_is_recognized(key: str, logger=get_logger())->bool:
    if key is None:
        logger.error('Key cannot be None')
        return False
    if isinstance(key, str) is False:
        logger.error('Key must be a string')
        return False
    if key.endswith('.event') is False:
        logger.error('Key has invalid extension')
        return False
    for acceptable_key_prefix in ACCEPTABLE_KEY_PREFIXES:
        if key.startswith(acceptable_key_prefix):
            return True
    logger.error('Key unrecognized')
    return False


def process_s3_record(record: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    """
        record={
            's3SchemaVersion': '1.0', 
            'configurationId': '...', 
            'bucket': {
                'name': 'lab4-new-events-qpwoeiryt', 
                'ownerIdentity': {
                    'principalId': 'A1OFXF1IHRJZE7'
                }, 
                'arn': 'arn:aws:s3:::lab4-new-events-qpwoeiryt'
            }, 
            'object': {
                'key': 'some_file.txt', 
                'size': 123, 
                'eTag': '854fce33df76ad3953e25b378a07f237', 
                'sequencer': '00636C82CFF1F68E3D'
            }
        }
    """
    try:
        if validate_key_is_recognized(key=record['object']['key'], logger=logger) is True:
            s3_payload_json = get_s3_object_payload(
                s3_bucket=record['bucket']['name'],
                s3_key=record['object']['key'],
                boto3_clazz=boto3_clazz,
                logger=logger
            )
            s3_payload_dict = json.loads(s3_payload_json)
            debug_log('s3_payload_dict={}', variable_as_list=[s3_payload_dict,], logger=logger)
        else:
            logger.warning('Skipping S3 record as it is not recognized as a valid event (Key Name Validation Failed)')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        return False
    return True

    
def handler(
    event,
    context,
    logger=get_logger(level=logging.INFO),
    boto3_clazz=boto3,
    run_from_main: bool=False
):
    refresh_environment_cache(logger=logger)
    if cache['Environment']['Data']['DEBUG'] is True and run_from_main is False:
        logger  = get_logger(level=logging.DEBUG)
    
    debug_log('event={}', variable_as_list=[event,], logger=logger)
    s3_records = extract_s3_event_messages(event=event, logger=logger)
    debug_log('s3_records={}', variable_as_list=[s3_records,], logger=logger)
    """
        s3_records=(
            {
                's3SchemaVersion': '1.0', 
                'configurationId': '...', 
                'bucket': {
                    'name': 'lab4-new-events-qpwoeiryt', 
                    'ownerIdentity': {
                        'principalId': 'A1OFXF1IHRJZE7'
                    }, 
                    'arn': 'arn:aws:s3:::lab4-new-events-qpwoeiryt'
                }, 
                'object': {
                    'key': 'some_file.txt', 
                    'size': 123, 
                    'eTag': '854fce33df76ad3953e25b378a07f237', 
                    'sequencer': '00636C82CFF1F68E3D'
                }
            },
        )
    """
    for s3_record in s3_records:
        if process_s3_record(record=s3_record, logger=logger, boto3_clazz=boto3_clazz) is True:
            logger.info('SUCCESSFULLY PROCESSED S3 RECORD: {}'.format(s3_record))

    
    return {"Result": "Ok", "Message": None}    # Adapt to suite the use case....


###############################################################################
###                                                                         ###
###                        M A I N    F U N C T I O N                       ###
###                                                                         ###
###############################################################################


if __name__ == '__main__':
    logger = logging.getLogger("my_lambda")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s:%(lineno)d -  %(levelname)s - %(message)s')

    ch = logging.StreamHandler()
    if get_debug() is True:
        ch.setLevel(logging.DEBUG)    
    else:
        ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    if get_debug() is True:
        logger.setLevel(logging.DEBUG)
    else:    
        logger.setLevel(logging.INFO)
    handler(event={}, context=None, logger=logger, run_from_main=True)