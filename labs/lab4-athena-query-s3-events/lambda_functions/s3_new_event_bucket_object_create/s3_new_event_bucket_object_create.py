import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
from decimal import Decimal
import copy
# Other imports here...
import hashlib


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


def get_session(region: str='eu-central-1', boto3_clazz=boto3):
    return boto3_clazz.Session(region_name=region)


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


def create_dynamodb_record(
    record_data: dict,
    boto3_clazz=boto3,
    logger=get_logger()
)->bool:
    try:
        client=get_client(client_name='dynamodb', region='eu-central-1', boto3_clazz=boto3_clazz)
        response = client.put_item(
            TableName='lab4_event_objects_v1',
            Item=record_data,
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        return True
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return False


def send_sqs_fifo_message(
    body: dict,
    message_group_id: str,
    transaction_type: str='unknown',
    boto3_clazz=boto3,
    logger=get_logger()
)->bool:
    try:
        json_body = json.dumps(body)
        json_body_checksum = hashlib.sha256(json_body.encode('utf-8')).hexdigest()
        session = get_session(boto3_clazz=boto3_clazz)
        sqs = session.resource('sqs')
        queue = sqs.get_queue_by_name(QueueName='AccountTransactionQueue.fifo')
        response = queue.send_message(
            MessageBody=json_body,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=json_body_checksum,
            MessageAttributes={
                'TransactionType': {
                    'StringValue': transaction_type,
                    'DataType': 'String'
                }
            }
        )
        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        return True
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return False


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


def determine_tx_type_and_reference_account(data: dict, logger=get_logger())->dict:
    debug_log('data={}', variable_as_list=[data,], logger=logger)
    result = dict()
    result['TxType'] = 'unknown'
    result['ReferenceAccount'] = 'unknown'
    try:
        for key_starts_with_value, account_reference_field_name in ACCOUNT_FIELD_NAME_BASED_ON_TRANSACTION_TYPE.items():
            if data['EventSourceDataResource']['S3Key'].startswith(key_starts_with_value):
                logger.info('Transaction Type Match: "{}"   Reference Field Name: "{}"'.format(key_starts_with_value, account_reference_field_name))
                result['TxType'] = TX_ACCOUNT_TYPE_ID_MAP[key_starts_with_value]
                result['ReferenceAccount'] = data[account_reference_field_name]

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log('result={}', variable_as_list=[result,], logger=logger)
    return result


def update_object_table(
    record: dict, 
    transaction_data: dict,
    tx_type_and_reference_account: dict,
    event_type: str='InitialEvent',
    boto3_clazz=boto3,
    logger=get_logger()
):
    try:
        reference_account_number = tx_type_and_reference_account['ReferenceAccount']
        if reference_account_number is None:
            logger.error('Invalid Account Number')
            return
        if isinstance(reference_account_number, str) is False:
            logger.error('Invalid Account Number Object Type')
            return
        tx_date = Decimal(datetime.utcfromtimestamp(transaction_data['EventTimeStamp']).strftime('%Y%m%d'))
        tx_time = Decimal(datetime.utcfromtimestamp(transaction_data['EventTimeStamp']).strftime('%H%M%S'))
        zero = Decimal('0')
        if tx_date.compare(zero) <= 0:
            logger.error('Invalid tx_date value')
            return
        if tx_time.compare(zero) <= 0:
            logger.error('Invalid tx_date value')
            return

        
        object_state_key = {
            'PK'                : { 'S'     : 'KEY#{}'.format(record['object']['key'])              },
            'SK'                : { 'S'     : 'STATE'                                               },
        }
        object_state_data = {
            'TransactionDate'   : { 'N'     : '{}'.format(tx_date)                                  },
            'TransactionTime'   : { 'N'     : '{}'.format(tx_time)                                  },
            'InEventBucket'     : { 'BOOL'  : True                                                  },
            'InArchiveBucket'   : { 'BOOL'  : False                                                 },
            'InRejectedBucket'  : { 'BOOL'  : False                                                 },
            'AccountNumber'     : { 'S'     : '{}'.format(reference_account_number)                 },
            'Processed'         : { 'BOOL'  : False                                                 },
        }
        object_state = {**object_state_key, **object_state_data}
        

        object_event_key = {
            'PK'                : { 'S'     : 'KEY#{}'.format(record['object']['key'])              },
            'SK'                : { 'S'     : 'EVENT#{}'.format(transaction_data['EventTimeStamp']) },
        }
        object_event_data = {
            'TransactionDate'   : { 'N'     : '{}'.format(tx_date)                                  },
            'TransactionTime'   : { 'N'     : '{}'.format(tx_time)                                  },
            'EventType'         : { 'S'     : event_type                                        },
            'AccountNumber'     : { 'S'     : '{}'.format(reference_account_number)                 },
            'ErrorState'        : { 'BOOL'  : False                                                 },
            'ErrorReason'       : { 'S'     : 'no-error'                                            },
        }
        object_event = {**object_event_key, **object_event_data}


        create_dynamodb_record(
            record_data=object_state,
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        logger.info('OBJECT STATE RECORD CREATED')
        create_dynamodb_record(
            record_data=object_event,
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        logger.info('OBJECT STATE EVENT RECORD CREATED')

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def update_object_table_add_event(
    record: dict, 
    transaction_data: dict,
    tx_type_and_reference_account: dict,
    event_type: str='InitialEvent',
    is_error: bool=False,
    error_message: str='no-error',
    boto3_clazz=boto3,
    logger=get_logger()
):
    try:
        reference_account_number = tx_type_and_reference_account['ReferenceAccount']
        if reference_account_number is None:
            logger.error('Invalid Account Number')
            return
        if isinstance(reference_account_number, str) is False:
            logger.error('Invalid Account Number Object Type')
            return
        tx_date = Decimal(datetime.utcfromtimestamp(transaction_data['EventTimeStamp']).strftime('%Y%m%d'))
        tx_time = Decimal(datetime.utcfromtimestamp(transaction_data['EventTimeStamp']).strftime('%H%M%S'))
        zero = Decimal('0')
        if tx_date.compare(zero) <= 0:
            logger.error('Invalid tx_date value')
            return
        if tx_time.compare(zero) <= 0:
            logger.error('Invalid tx_date value')
            return

        object_event_key = {
            'PK'                : { 'S'     : 'KEY#{}'.format(record['object']['key'])              },
            'SK'                : { 'S'     : 'EVENT#{}'.format(transaction_data['EventTimeStamp']) },
        }
        object_event_data = {
            'TransactionDate'   : { 'N'     : '{}'.format(tx_date)                                  },
            'TransactionTime'   : { 'N'     : '{}'.format(tx_time)                                  },
            'EventType'         : { 'S'     : event_type                                            },
            'AccountNumber'     : { 'S'     : '{}'.format(reference_account_number)                 },
            'ErrorState'        : { 'BOOL'  : is_error                                              },
            'ErrorReason'       : { 'S'     : error_message                                         },
        }
        object_event = {**object_event_key, **object_event_data}


        logger.info('OBJECT STATE RECORD CREATED')
        create_dynamodb_record(
            record_data=object_event,
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        logger.info('OBJECT STATE EVENT RECORD CREATED')

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def extract_request_id(key: str, logger=get_logger())->str:
    request_id = None
    try:
        for key_prefix in ACCEPTABLE_KEY_PREFIXES:
            if key.startswith(key_prefix):
                request_id = copy.deepcopy(key)
                request_id = request_id.replace(key_prefix, '')
                request_id = request_id.replace('.event', '')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return request_id


def process_s3_record(
    record: dict,
    logger=get_logger(),
    boto3_clazz=boto3
)->bool:
    logger.info('PROCESSING RECORD: {}'.format(record))
    try:
        if int(record['object']['size']) > 1024:
            logger.warning('Skipping S3 record as it is larger than the acceptable maximum size of 1KiB')
            return False
        if validate_key_is_recognized(key=record['object']['key'], logger=logger) is True:
            s3_payload_json = get_s3_object_payload(
                s3_bucket=record['bucket']['name'],
                s3_key=record['object']['key'],
                boto3_clazz=boto3_clazz,
                logger=logger
            )
            s3_payload_dict = json.loads(s3_payload_json)
            debug_log('s3_payload_dict={}', variable_as_list=[s3_payload_dict,], logger=logger)
            logger.info('STEP COMPLETE: S3 Payload Retrieved and Converted')

            request_id = extract_request_id(key=record['object']['key'], logger=logger)
            if request_id is None:
                logger.error('Unable to determine request ID - rejecting event.')
                return False
            s3_payload_dict['RequestId'] = request_id
            logger.info('STEP COMPLETE: S3 Payload Enriched with Request ID')
            

            s3_payload_dict['EventSourceDataResource'] = dict()
            s3_payload_dict['EventSourceDataResource']['S3Key'] = record['object']['key']
            s3_payload_dict['EventSourceDataResource']['S3Bucket'] = record['bucket']['name']
            logger.info('STEP COMPLETE: S3 Payload Enriched with Event Source Data')


            tx_type_and_reference_account = determine_tx_type_and_reference_account(data=s3_payload_dict, logger=logger)
            s3_payload_dict['TransactionType'] = tx_type_and_reference_account['TxType']
            logger.info(
                'STEP COMPLETE: Transaction Type "{}" identified for reference account "{}"'.format(
                    tx_type_and_reference_account['TxType'],
                    tx_type_and_reference_account['ReferenceAccount']
                )
            )


            update_object_table(
                record=record, 
                transaction_data=s3_payload_dict,
                tx_type_and_reference_account=tx_type_and_reference_account,
                event_type='InitialEvent',
                boto3_clazz=boto3_clazz,
                logger=logger
            )
            logger.info('STEP COMPLETE: Event Object Table Updated')


            if tx_type_and_reference_account['TxType'] == 'unknown':
                logger.error(
                    'Transaction Type not recognized and/or not supported. The Transaction will NOT be send for further processing. S3 bucket "{}" key "{}"'.format(
                        record['object']['key'],
                        record['bucket']['name']
                    )
                )
                update_object_table_add_event(
                    record=record, 
                    transaction_data=s3_payload_dict,
                    tx_type_and_reference_account=tx_type_and_reference_account,
                    event_type='TxAbortEvent',
                    is_error=True,
                    error_message='Transaction Type Not Recognized',
                    boto3_clazz=boto3_clazz,
                    logger=logger
                )
                logger.info('STEP COMPLETE: Event Object Table Updated with Event')
                return False


            if tx_type_and_reference_account['ReferenceAccount'] == 'unknown':
                logger.error(
                    'Reference Account Number not recognized and/or not supported. The Transaction will NOT be send for further processing. S3 bucket "{}" key "{}"'.format(
                        record['object']['key'],
                        record['bucket']['name']
                    )
                )
                update_object_table_add_event(
                    record=record, 
                    transaction_data=s3_payload_dict,
                    tx_type_and_reference_account=tx_type_and_reference_account,
                    event_type='TxAbortEvent',
                    is_error=True,
                    error_message='Reference Account Number Not Recognized',
                    boto3_clazz=boto3_clazz,
                    logger=logger
                )
                logger.info('STEP COMPLETE: Event Object Table Updated with Event')
                return False


            update_object_table_add_event(
                record=record, 
                transaction_data=s3_payload_dict,
                tx_type_and_reference_account=tx_type_and_reference_account,
                event_type='InitialEvent',
                is_error=False,
                error_message='no-error',
                boto3_clazz=boto3_clazz,
                logger=logger
            )
            logger.info('STEP COMPLETE: Event Object Table Updated with Event')


            if send_sqs_fifo_message(
                body=s3_payload_dict,
                message_group_id=tx_type_and_reference_account['ReferenceAccount'],
                boto3_clazz=boto3_clazz,logger=logger
            ) is True:
                logger.info('STEP COMPLETE: S3 Payload Send to Transactional SQS FIFO Queue')
            else:
                logger.error('STEP FAILED: S3 Payload Send to Transactional SQS FIFO Queue')
                return False

            logger.info('RECORD EVENT PREPARED AND READY FOR PROCESSING')

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
    for s3_record in s3_records:
        if process_s3_record(record=s3_record, logger=logger, boto3_clazz=boto3_clazz) is True:
            logger.info('SUCCESSFULLY PROCESSED S3 RECORD: {}'.format(s3_record))
        else:
            logger.info('FAILED TO PROCESS S3 RECORD: {}'.format(s3_record))

    
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