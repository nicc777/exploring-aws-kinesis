import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
# Other imports here...
import copy
import redis
import chardet 
from decimal import Decimal


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
            'REDIS_HOST': '{}'.format(os.getenv('REDIS_HOST', 'localhost')),
            'REDIS_PORT': int(os.getenv('REDIS_PORT', '6379'))
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


def get_client(client_name: str, region: str='eu-central-1', boto3_clazz=boto3):
    return boto3_clazz.client(client_name, region_name=region)


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
            debug_log('type={}   key_json_data={}', variable_as_list=[type(key_json_data), key_json_data,], logger=logger)
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
            TableName=os.getenv('DYNAMODB_OBJECT_TABLE_NAME'),
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


###############################################################################
###                                                                         ###
###                    R E D I S    I N T E G R A T I O N                   ###
###                                                                         ###
###############################################################################


CONFIGURED_STATES = {
    'tx_processing_state': (
        'pending',
        'all-ok',
        'emergency-stop',
    )
}


def cache_create_state(
    host: str,
    port: int,
    state_type: str='tx_processing_state',
    state: str='pending',
    state_reason: str='No Reason Provided',
    logger=get_logger()
)->bool:
    try:
        r = redis.Redis(host=host, port=port, db=0)
        r.set('{}'.format(state_type), '{}'.format(state))
        r.set('{}_reason'.format(state_type), '{}'.format(state_reason))
        return True
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return False


def cache_get_state(
    host: str,
    port: int,
    state_type: str='tx_processing_state',
    create_default_state_if_none_found: bool=True,
    default_state_if_none_found: str='pending',
    default_state_reason_if_none_found: str='Fresh Start',
    logger=get_logger()
)->str:
    state = 'all-ok'
    try:
        r = redis.Redis(host=host, port=port, db=0)
        state = r.get(state_type)
        if state is None:
            if create_default_state_if_none_found is True:
                if cache_create_state(
                    host=host,
                    port=port,
                    state_type='{}'.format(state_type),
                    state='{}'.format(default_state_if_none_found),
                    state_reason='{}'.format(default_state_reason_if_none_found),
                    logger=logger
                ) is False:
                    logger.error('Failed to set initial "{}" state'.format(state_type))
                    state = 'fail'
                    return state
                state = r.get('{}'.format(state_type))
            else:
                return None
        
        state_encoding = chardet.detect(state)['encoding']
        logger.debug('Retrieved State: {}    -> encoding: {}'.format(state, state_encoding))
        state = state.decode(state_encoding)

        state_reason = r.get('{}_reason'.format(state_type))
        state_reason_encoding = chardet.detect(state_reason)['encoding']
        state_reason = state_reason.decode(state_reason_encoding)


        logger.info('CACHED STATE RETRIEVED: {} ({})'.format(state, state_reason))
        if state_type.startswith('account_state_') is False:
            if state not in CONFIGURED_STATES[state_type]:
                logger.error('Unrecognized value for state for "{}"'.format(state_type))
                state = 'fail'
                return state
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        state = 'fail'
    return state


###############################################################################
###                                                                         ###
###                     E V E N T    V A L I D A T I O N                    ###
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


###############################################################################
###                                                                         ###
###                     E V E N T    P R O C E S S I N G                    ###
###                                                                         ###
###############################################################################


TRANSACTION_STEPS_BY_TYPE = {
    'CashDeposit': {
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'UpdateBalanceRecords'          :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'VerifyCashDeposit': {
        'CalculateUpdatedBalances'      :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'RetrieveReferencedTransaction' :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'SetUpdatedBalances'            :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'UpdateBalanceRecords'          :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'CashWithdrawal': {
        'CalculateUpdatedBalances'      :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CheckForAvailableFunds'        :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'SetUpdatedBalances'            :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'UpdateBalanceRecords'          :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'IncomingPayment': {
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'UpdateBalanceRecords'          :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'UnverifiedOutgoingPayment': {
        'CalculateUpdatedBalances'      :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CheckForAvailableFunds'        :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'SetUpdatedBalances'            :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'SendToExternalInstitution'     :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateBalanceRecords'          :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': True  },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'VerifiedOutgoingPayment': {
        'RetrieveReferencedTransaction' :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'CommitTransactionEvent'        :   { 'BlockAccountStateOnFail': True,  'BlockGlobalTransactionProcessingOnFail': False,    'RollbackOnFail': False },
        'UpdateObjectStatus'            :   { 'BlockAccountStateOnFail': False, 'BlockGlobalTransactionProcessingOnFail': True,     'RollbackOnFail': False },
    },
    'RejectedOutgoingPayment': {},
    'InterAccountTransfer': {},
}


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
            debug_log('type={}   s3_payload_json={}', variable_as_list=[type(s3_payload_json), s3_payload_json,], logger=logger)
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
            s3_payload_dict['ReferenceAccount'] = tx_type_and_reference_account['ReferenceAccount']
            logger.info(
                'STEP COMPLETE: Transaction Type "{}" identified for reference account "{}"'.format(
                    tx_type_and_reference_account['TxType'],
                    tx_type_and_reference_account['ReferenceAccount']
                )
            )

            tx_processing_state = cache_get_state(
                host=cache['Environment']['Data']['REDIS_HOST'],
                port=cache['Environment']['Data']['REDIS_PORT'],
                state_type='tx_processing_state',
                logger=logger
            )
            if tx_processing_state != 'all-ok':
                logger.error('Cannot Continue - Reject Message')
                return False
            logger.info('STEP COMPLETE: Global Transaction Processing State is OK')

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

            account_processing_state = cache_get_state(
                host=cache['Environment']['Data']['REDIS_HOST'],
                port=cache['Environment']['Data']['REDIS_PORT'],
                state_type='account_state_{}'.format(tx_type_and_reference_account['ReferenceAccount']),
                default_state_if_none_found='all-ok',
                default_state_reason_if_none_found='Previous Account State Instance Not Found - Assuming New Account and ALL OK',
                logger=logger
            )
            if account_processing_state != 'all-ok':
                logger.error('Cannot Continue - Reject Message')
                return False
            logger.info('STEP COMPLETE: Account Processing State is OK')

            # TODO Set-up the transaction tracking for the account in the cache (Transaction Steps)

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

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        return False
    return True


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
        if process_s3_record(record=s3_record, logger=logger, boto3_clazz=boto3_clazz) is True:
            logger.info('SUCCESSFULLY PROCESSED S3 RECORD: {}'.format(s3_record))
        else:
            logger.info('FAILED TO PROCESS S3 RECORD: {}'.format(s3_record))
            raise Exception('FAILED TO PROCESS S3 RECORD')
    
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


cash_deposit_payload = {
    "EventTimeStamp": 1664611200,
    "TargetAccount": "100020",
    "Amount": "500",
    "LocationType": "Branch A",
    "Reference": "Open 100020",
    "Verified": True,
    "Currency": {
        "100-euro-bills": "5",
        "50-euro-bills": "0",
        "20-euro-bills": "0",
        "10-euro-bills": "0",
        "50-cents": "0",
        "20-cents": "0",
        "10-cents": "0",
        "5-cents": "0"
    }
}


class MockBotocoreResponseStreamingBody:

    def __init__(self, key_payload: str=''):
        self.key_payload = key_payload

    def read(self, *args, **kwargs):
        return self.key_payload


class MockAwsS3Client:
    
    def __init__(self, botocore_response_StreamingBody=MockBotocoreResponseStreamingBody()):
        self.botocore_response_StreamingBody = botocore_response_StreamingBody

    def get_object(self, *args, **kwargs):
        response = {
            'ResponseMetadata': {
                'RequestId': 'AAAAAAAAAAAAAAAA', 
                'HostId': '...', 
                'HTTPStatusCode': 200, 
                'HTTPHeaders': {
                    'x-amz-id-2': '...', 
                    'x-amz-request-id': 'AAAAAAAAAAAAAAAA', 
                    'date': 'Thu, 24 Nov 2022 05:52:59 GMT', 
                    'last-modified': 'Thu, 24 Nov 2022 05:52:56 GMT', 
                    'x-amz-expiration': 'expiry-date="Fri, 02 Dec 2022 00:00:00 GMT", rule-id="lab4-new-events-qpwoeiryt-archive-lifecycle-01"', 
                    'etag': '"f150258aeb1e6f51b0315424f99790ba"', 
                    'accept-ranges': 'bytes', 
                    'content-type': 'binary/octet-stream', 
                    'server': 'AmazonS3', 
                    'content-length': '318'
                }, 
                'RetryAttempts': 0
            }, 
            'AcceptRanges': 'bytes', 
            'Expiration': 'expiry-date="Fri, 02 Dec 2022 00:00:00 GMT", rule-id="lab4-new-events-qpwoeiryt-archive-lifecycle-01"', 
            'LastModified': None, 
            'ContentLength': 318, 
            'ETag': '"f150258aeb1e6f51b0315424f99790ba"', 
            'ContentType': 'binary/octet-stream', 
            'Metadata': {}, 
            'Body': self.botocore_response_StreamingBody
        }
        return response


class MockDynamoDbClient:

    def __init__(self, response: dict=dict()):
        self.response = {
            'ConsumedCapacity': {
                'TableName': 'lab4_event_objects_v1', 
                'CapacityUnits': 2.0
            }, 
            'ResponseMetadata': {
                'RequestId': '...', 
                'HTTPStatusCode': 200, 
                'HTTPHeaders': {
                    'server': 'Server', 
                    'date': 'Thu, 01 Dec 2022 06:44:52 GMT', 
                    'content-type': 'application/x-amz-json-1.0', 
                    'content-length': '78', 
                    'connection': 'keep-alive', 
                    'x-amzn-requestid': '...', 
                    'x-amz-crc32': '2469452655'
                }, 
                'RetryAttempts': 0
            }
        }
        if len(response) > 0:
            self.response = response

    def put_item(self, *args, **kwargs):
        return self.response


class MockBoto3:
    
    def __init__(self, s3_client=MockAwsS3Client(), dynamodb_client=MockDynamoDbClient()):
        self.s3_client = s3_client
        self.dynamodb_client = dynamodb_client

    def client(self, *args, **kwargs):
        for n in args:
            if n == 's3':
                return self.s3_client
            elif n == 'dynamodb':
                return self.dynamodb_client
        raise Exception('LOCAL MOCK FAIL: Unknown client requested.')


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

    key_payload_as_str = '{}'.format(json.dumps(cash_deposit_payload))
    key_payload_as_str_encoded = key_payload_as_str.encode('utf-8')
    s3_client = MockAwsS3Client(
        botocore_response_StreamingBody=MockBotocoreResponseStreamingBody(
            key_payload=key_payload_as_str_encoded
        )
    )

    handler(
        event=example_event_1, 
        context=None, 
        logger=logger, 
        boto3_clazz=MockBoto3(s3_client=s3_client),
        run_from_main=True
    )
