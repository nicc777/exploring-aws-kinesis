import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
# Other imports here...


###############################################################################
###                                                                         ###
###                          B A S I C    S E T U P                         ###
###                                                                         ###
###############################################################################


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
    return logger


def get_client(client_name: str, region: str='eu-central-1', boto3_clazz=boto3):
    return boto3_clazz.client(client_name, region_name=region)


# ADD the header as per section ``Module header functions``

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


###############################################################################
###                                                                         ###
###                     E V E N T    V A L I D A T I O N                    ###
###                                                                         ###
###############################################################################


###############################################################################
###                                                                         ###
###                     E V E N T    P R O C E S S I N G                    ###
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

ACCOUNT_FIELD_NAME_BASED_ON_TRANSACTION_TYPE = {
    # "Event Key Prefix"            : "Field Name"
    'cash_deposit_'                 : 'TargetAccount',
    'verify_cash_deposit_'          : 'TargetAccount',
    'cash_withdrawal_'              : 'SourceAccount',
    'incoming_payment_'             : 'TargetAccount',
    'outgoing_payment_unverified_'  : 'SourceAccount',
    'outgoing_payment_verified_'    : 'SourceAccount',
    'outgoing_payment_rejected_'    : 'SourceAccount',
    'inter_account_transfer_'       : 'SourceAccount',
}


TX_ACCOUNT_TYPE_ID_MAP = {
    'cash_deposit_'                 : 'CashDeposit',
    'verify_cash_deposit_'          : 'VerifyCashDeposit',
    'cash_withdrawal_'              : 'CashWithdrawal',
    'incoming_payment_'             : 'IncomingPayment',
    'outgoing_payment_unverified_'  : 'UnverifiedOutgoingPayment',
    'outgoing_payment_verified_'    : 'VerifiedOutgoingPayment',
    'outgoing_payment_rejected_'    : 'RejectedOutgoingPayment',
    'inter_account_transfer_'       : 'InterAccountTransfer',
}


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


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################

    
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
    
    debug_log('event={}', variable_as_list=[event], logger=logger)

    s3_records = extract_s3_event_messages(event=event, logger=logger)
    debug_log('s3_records={}', variable_as_list=[s3_records,], logger=logger)
    for s3_record in s3_records:
        debug_log('s3_record={}', variable_as_list=[s3_record,], logger=logger)
    
    return {"Result": "Ok", "Message": None}    # Adapt to suite the use case....


###############################################################################
###                                                                         ###
###                        M A I N    F U N C T I O N                       ###
###                                                                         ###
###############################################################################


example_message_1 = {
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "eu-central-1",
            "eventTime": "2022-11-24T05:52:55.504Z",
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "AWS:AAAAAAAAAAAAAAAAAAAAA"
            },
            "requestParameters": {
                "sourceIPAddress": "105.242.239.113"
            },
            "responseElements": {
                "x-amz-request-id": "XXXXXXXXXXXXXXXX",
                "x-amz-id-2": "..."
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "...",
                "bucket": {
                    "name": "lab4-new-events-qpwoeiryt",
                    "ownerIdentity": {
                        "principalId": "AAAAAAAAAAAAAA"
                    },
                    "arn": "arn:aws:s3:::lab4-new-events-qpwoeiryt"
                },
                "object": {
                    "key": "cash_deposit_r0000002.event",
                    "size": 318,
                    "eTag": "f150258aeb1e6f51b0315424f99790ba",
                    "sequencer": "00637F06B748921D1B"
                }
            }
        }
    ]
}

example_body_1 = {
    "Type": "Notification",
    "MessageId": "38b7b564-3142-5c4b-9423-ee9d39ba3c45",
    "TopicArn": "arn:aws:sns:eu-central-1:342872205792:S3NewEventStoreNotification",
    "Subject": "Amazon S3 Notification",
    "Message": '{}'.format(json.dumps(example_message_1)),
    "Timestamp": "2022-11-24T05:52:56.065Z",
    "SignatureVersion": "1",
    "Signature": "...",
    "SigningCertURL": "...",
    "UnsubscribeURL": "..."
}

example_event_1 = {
    'Records': [
        {
            'messageId': '0bae8bd5-6fd4-4262-ae37-eb36ac519f1c', 
            'receiptHandle': '...', 
            'body': '{}'.format(json.dumps(example_body_1)), 
            'attributes': {
                'ApproximateReceiveCount': '1', 
                'SentTimestamp': '1669269176107', 
                'SenderId': 'AIDAISDDSWNBEXIA6J64K', 
                'ApproximateFirstReceiveTimestamp': '1669269176110'
            }, 
            'messageAttributes': {}, 
            'md5OfBody': 'c6ee7a53b14abc6004d1aa288757fe56', 
            'eventSource': 'aws:sqs', 
            'eventSourceARN': 'arn:aws:sqs:eu-central-1:342872205792:S3NewEventStoreNotificationQueue', 
            'awsRegion': 'eu-central-1'
        }
    ]
}


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

    handler(event=example_event_1, context=None, logger=logger, run_from_main=True)
