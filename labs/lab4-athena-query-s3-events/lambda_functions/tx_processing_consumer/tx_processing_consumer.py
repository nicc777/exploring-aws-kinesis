import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
from decimal import Decimal
# Other imports here...
import copy


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


def create_dynamodb_record(
    table_name: str,
    record_data: dict,
    boto3_clazz=boto3,
    logger=get_logger()
)->bool:
    try:
        client=get_client(client_name='dynamodb', region='eu-central-1', boto3_clazz=boto3_clazz)
        response = client.put_item(
            TableName=table_name,
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


def get_dynamodb_record_by_key(
    key: dict,
    boto3_clazz=boto3,
    logger=get_logger()
)->dict:
    record = dict()
    try:
        client=get_client(client_name='dynamodb', region='eu-central-1', boto3_clazz=boto3_clazz)
        response = client.get_item(
            TableName=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
            Key=key,
            ConsistentRead=True,
            ReturnConsumedCapacity='TOTAL'
        )
        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        if 'Item' in response:
            for field_name, field_data in response['Item'].items():
                for field_data_type, field_data_value in field_data.items():
                    if field_data_type == 'S':
                        record[field_name] = '{}'.format(field_data_value)
                    if field_data_type == 'N':
                        record[field_name] = Decimal(field_data_value)
                    if field_data_type == 'BOOL':
                        record[field_name] = field_data_value        
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    if 'Balance' not in record:
            record['Balance'] = Decimal('0')
    debug_log(message='record={}', variable_as_list=[record,], logger=logger)
    return record


def get_dynamodb_record_by_indexed_query(
    key: dict,
    index_name: str,
    use_consistent_read: bool=False,
    boto3_clazz=boto3,
    logger=get_logger(),
    next_token: dict=None
)->list:
    records = list()
    try:
        client=get_client(client_name='dynamodb', region='eu-central-1', boto3_clazz=boto3_clazz)
        
        response = dict()
        if next_token is None:
            response = client.query(
                TableName=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
                IndexName=index_name,
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=use_consistent_read,
                KeyConditions=key,
                ReturnConsumedCapacity='TOTAL'
            )
        else:
            response = client.query(
                TableName=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
                IndexName=index_name,
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=use_consistent_read,
                KeyConditions=key,
                ReturnConsumedCapacity='TOTAL',
                ExclusiveStartKey=next_token
            )

        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        if 'Items' in response:
            for item in response['Items']:
                record = dict()
                for field_name, field_data in item:
                    for field_data_type, field_data_value in field_data.items():
                        if field_data_type == 'S':
                            record[field_name] = '{}'.format(field_data_value)
                        if field_data_type == 'N':
                            record[field_name] = Decimal(field_data_value)
                        if field_data_type == 'BOOL':
                            record[field_name] = field_data_value   
                records.append(record)

        if 'LastEvaluatedKey' in response:
            records += get_dynamodb_record_by_indexed_query(key=key,index_name=index_name,use_consistent_read=use_consistent_read,boto3_clazz=boto3_clazz,logger=logger,next_token=response['LastEvaluatedKey'])
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    if 'Balance' not in records:
            records['Balance'] = Decimal('0')
    debug_log(message='record={}', variable_as_list=[records,], logger=logger)
    return records


def get_dynamodb_record_by_primary_index_query_with_filter(
    key: dict,
    query_filter: dict,
    use_consistent_read: bool=False,
    boto3_clazz=boto3,
    logger=get_logger(),
    next_token: dict=None
)->list:
    records = list()
    debug_log(message='key={}', variable_as_list=[key,], logger=logger)
    debug_log(message='query_filter={}', variable_as_list=[query_filter,], logger=logger)
    try:
        client=get_client(client_name='dynamodb', region='eu-central-1', boto3_clazz=boto3_clazz)
        response = dict()
        if next_token is None:
            response = client.query(
                TableName=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=use_consistent_read,
                KeyConditions=key,
                ReturnConsumedCapacity='TOTAL',
                QueryFilter=query_filter
            )
        else:
            response = client.query(
                TableName=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=use_consistent_read,
                KeyConditions=key,
                ReturnConsumedCapacity='TOTAL',
                ExclusiveStartKey=next_token,
                QueryFilter=query_filter
            )

        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        if 'Items' in response:
            for item in response['Items']:
                record = dict()
                for field_name, field_data in item.items():
                    for field_data_type, field_data_value in field_data.items():
                        if field_data_type == 'S':
                            record[field_name] = '{}'.format(field_data_value)
                        if field_data_type == 'N':
                            record[field_name] = Decimal(field_data_value)
                        if field_data_type == 'BOOL':
                            record[field_name] = field_data_value   
                logger.info('Retrieved record: {}'.format(record))
                records.append(record)

        if 'LastEvaluatedKey' in response:
            records += get_dynamodb_record_by_primary_index_query_with_filter(key=key,query_filter=query_filter,use_consistent_read=use_consistent_read,boto3_clazz=boto3_clazz,logger=logger,next_token=response['LastEvaluatedKey'])
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log(message='records={}', variable_as_list=[records,], logger=logger)
    return records


def send_sqs_tx_cleanup_message(
    body: dict,
    boto3_clazz=boto3,
    logger=get_logger()
)->bool:
    try:
        json_body = json.dumps(body)
        session = get_session(boto3_clazz=boto3_clazz)
        sqs = session.resource('sqs')
        queue = sqs.get_queue_by_name(QueueName='AccountTransactionCleanupQueue')
        response = queue.send_message(
            MessageBody=json_body
        )
        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        return True
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return False


###############################################################################
###                                                                         ###
###                 E V E N T    S T A T E     U P D A T E S                ###
###                                                                         ###
###############################################################################

def update_object_sate(
    tx_data: dict,
    logger=get_logger(),
    boto3_clazz=boto3
):
    try:
        tx_date = _helper_tx_date(timestamp=tx_data['EventTimeStamp'])
        tx_time = _helper_tx_time(timestamp=tx_data['EventTimeStamp'])
        object_state_key = {
            'PK'                : { 'S'     : 'KEY#{}'.format(tx_data['EventSourceDataResource']['S3Key'])  },
            'SK'                : { 'S'     : 'STATE'                                                       },
        }
        object_state_data = {
            'TransactionDate'   : { 'N'     : '{}'.format(tx_date)                                          },
            'TransactionTime'   : { 'N'     : '{}'.format(tx_time)                                          },
            'InEventBucket'     : { 'BOOL'  : True                                                          },
            'InArchiveBucket'   : { 'BOOL'  : False                                                         },
            'InRejectedBucket'  : { 'BOOL'  : False                                                         },
            'AccountNumber'     : { 'S'     : '{}'.format(tx_data['ReferenceAccount'])                      },
            'Processed'         : { 'BOOL'  : True                                                          },
        }
        object_state = {**object_state_key, **object_state_data}
        create_dynamodb_record(
            table_name=os.getenv('DYNAMODB_OBJECT_TABLE_NAME'),
            record_data=object_state,
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        logger.info('OBJECT STATE RECORD UPDATED')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))

def update_object_table_add_event(
    origin_event_key: str, 
    event_timestamp: str,
    tx_date: Decimal,
    tx_time: Decimal,
    reference_account_number: str,
    event_type: str='ProcessingEvent',
    is_error: bool=False,
    error_message: str='no-error',
    boto3_clazz=boto3,
    logger=get_logger()
):
    try:
        object_event_key = {
            'PK'                : { 'S'     : 'KEY#{}'.format(origin_event_key)                         },
            'SK'                : { 'S'     : 'EVENT#{}'.format(get_utc_timestamp(with_decimal=False))  },
        }
        object_event_data = {
            'TransactionDate'   : { 'N'     : '{}'.format(tx_date)                                      },
            'TransactionTime'   : { 'N'     : '{}'.format(tx_time)                                      },
            'EventType'         : { 'S'     : event_type                                                },
            'AccountNumber'     : { 'S'     : '{}'.format(reference_account_number)                     },
            'ErrorState'        : { 'BOOL'  : is_error                                                  },
            'ErrorReason'       : { 'S'     : error_message                                             },
        }
        object_event = {**object_event_key, **object_event_data}

        create_dynamodb_record(
            table_name=os.getenv('DYNAMODB_OBJECT_TABLE_NAME'),
            record_data=object_event,
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        logger.info('OBJECT STATE EVENT RECORD CREATED')

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


###############################################################################
###                                                                         ###
###               T R A N S A C T I O N    P R O C E S S I N G              ###
###                                                                         ###
###############################################################################


def _helper_tx_date(timestamp: int)->str:
    return Decimal(datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d'))


def _helper_tx_time(timestamp: int)->str:
    return Decimal(datetime.utcfromtimestamp(timestamp).strftime('%H%M%S'))


def _helper_event_types_as_tuple(
    is_pending: bool=True,
    is_verified: bool=False
)->tuple:
    event_types = list()
    if is_pending is True:
        event_types.append('PENDING')
    if is_verified is True:
        event_types.append('VERIFIED')
    return tuple(event_types)


def _helper_get_balance(
    account_ref: str,
    type: str='Available',
    boto3_clazz=boto3,
    logger=get_logger()
)->Decimal:
    try:
        key = {
            'PK'        : { 'S': '{}'.format(account_ref)                   },
            'SK'        : { 'S': 'SAVINGS#BALANCE#{}'.format(type.upper())  },
        }
        balance = get_dynamodb_record_by_key(key=key, boto3_clazz=boto3_clazz, logger=logger)['Balance']
        if isinstance(balance, Decimal) is True:
            return balance
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return Decimal('0')


def _helper_calculate_updated_balances(
    account_ref: str,
    amount: Decimal,
    effect_on_actual_balance: str=None,
    effect_on_available_balance: str=None,
    boto3_clazz=boto3,
    logger=get_logger()
)->dict:
    balances = dict()
    balances['Available'] = _helper_get_balance(account_ref=account_ref, type='Available', boto3_clazz=boto3_clazz, logger=logger)
    balances['Actual'] = _helper_get_balance(account_ref=account_ref, type='Actual', boto3_clazz=boto3_clazz, logger=logger)
    effect = dict()
    effect['Available'] = effect_on_available_balance
    effect['Actual'] = effect_on_actual_balance

    for balance_type in ('Available', 'Actual'):
        logger.info('[account_reference={}] {} Balance PRE: {}'.format(account_ref, balance_type, balances[balance_type]))
        if effect[balance_type] == 'Increase':
            balances[balance_type] += amount
            logger.info('[account_reference={}] {} Balance INCREASED with {} to {}'.format(account_ref, balance_type, amount, balances[balance_type]))
        elif effect[balance_type] == 'Decrease':
            balances[balance_type] -= amount
            logger.info('[account_reference={}] {} Balance DECREASED with {} to {}'.format(account_ref, balance_type, amount, balances[balance_type]))
        else:
            logger.info('[account_reference={}] Available Balance REMAINS unchanged at {}'.format(account_ref, balances[balance_type]))

    logger.info('[account_reference={}] FINAL balances on account {}: {}'.format(account_ref, account_ref, balances))
    return balances


def _helper_commit_transaction_events(
    tx_data: dict, 
    event_types: tuple,
    effect_on_actual_balance: str='None',
    effect_on_available_balance: str='None',
    boto3_clazz=boto3,
    logger=get_logger()
):
    tx_date_value = _helper_tx_date(timestamp=tx_data['EventTimeStamp'])
    tx_time_value = _helper_tx_time(timestamp=tx_data['EventTimeStamp'])
    previous_request_id = "n/a"
    if 'PreviousRequestIdReference' in tx_data:
        previous_request_id = tx_data['PreviousRequestIdReference']
    for event_type in event_types:
        event_key = {
            'PK'        : { 'S': tx_data['ReferenceAccount']                                                                                                                },
            'SK'        : { 'S': 'TRANSACTIONS#{}#{}#{}'.format(event_type, tx_data['EventSourceDataResource']['S3Bucket'], tx_data['EventSourceDataResource']['S3Key'])    },
        }
        event_data = {
            'TransactionDate'           : { 'N': '{}'.format(tx_date_value)                                 },
            'TransactionTime'           : { 'N': '{}'.format(tx_time_value)                                 },
            'EventKey'                  : { 'S': '{}'.format(tx_data['EventSourceDataResource']['S3Key'])   },
            'EventRawData'              : { 'S': '{}'.format(json.dumps(tx_data))                           },
            'Amount'                    : { 'N': '{}'.format(tx_data['Amount'])                             },
            'TransactionType'           : { 'S': '{}'.format(tx_data['TransactionType'])                    },
            'RequestId'                 : { 'S': '{}'.format(tx_data['RequestId'])                          },
            'PreviousRequestIdReference': { 'S': '{}'.format(previous_request_id)                           },
            'EffectOnActualBalance'     : { 'S': '{}'.format(effect_on_actual_balance)                      },
            'EffectOnAvailableBalance'  : { 'S': '{}'.format(effect_on_available_balance)                   },
        }
        create_dynamodb_record(
            table_name=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
            record_data={**event_key, **event_data},
            boto3_clazz=boto3_clazz,
            logger=logger
        )


def _helper_commit_updated_balances(
    tx_data: dict, 
    updated_balances: dict=None,
    effect_on_actual_balance: str='None',
    effect_on_available_balance: str='None',
    boto3_clazz=boto3,
    logger=get_logger()
):
    tx_date_value = _helper_tx_date(timestamp=tx_data['EventTimeStamp'])
    tx_time_value = _helper_tx_time(timestamp=tx_data['EventTimeStamp'])

    if updated_balances is None:
        updated_balances = _helper_calculate_updated_balances(
            account_ref=tx_data['ReferenceAccount'],
            amount=Decimal(tx_data['Amount']),
            effect_on_actual_balance=effect_on_actual_balance,
            effect_on_available_balance=effect_on_available_balance,
            boto3_clazz=boto3_clazz,
            logger=logger
        )

    for balance_type in ('Available', 'Actual'):
        actual_balance_data = {
            'PK'                        : { 'S': tx_data['ReferenceAccount']                                },
            'SK'                        : { 'S': 'SAVINGS#BALANCE#{}'.format(balance_type.upper())          },
            'LastTransactionDate'       : { 'N': '{}'.format(tx_date_value)                                 },
            'LastTransactionTime'       : { 'N': '{}'.format(tx_time_value)                                 },
            'EventKey'                  : { 'S': '{}'.format(tx_data['EventSourceDataResource']['S3Key'])   },
            'Balance'                   : { 'N': '{}'.format(str(updated_balances[balance_type]))           },
        }
        create_dynamodb_record(
            table_name=os.getenv('DYNAMODB_ACCOUNTS_TABLE_NAME'),
            record_data=actual_balance_data,
            boto3_clazz=boto3_clazz,
            logger=logger
        )


def cash_deposit(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'Increase'
    effect_on_available_balance     = 'None'
    is_pending                      = True
    is_verified                     = False

    if 'Verified' in tx_data:
        if isinstance(tx_data['Verified'], bool):
            if tx_data['Verified'] is True:
                effect_on_available_balance = 'Increase'
                is_pending = False
                is_verified = True

    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def verify_cash_deposit(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'None'
    effect_on_available_balance     = 'Increase'
    is_pending                      = False
    is_verified                     = True

    account_balances = _helper_calculate_updated_balances(
        account_ref=tx_data['ReferenceAccount'],
        amount=Decimal(tx_data['Amount']),
        effect_on_actual_balance='None',
        effect_on_available_balance='None',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Retrieve the original transaction - we need that to calculate the net effect on balances.
    previous_record = dict()
    verified_amount = Decimal(tx_data['Amount'])
    try:
        key = {
            'PK': {
                'AttributeValueList': [
                    {
                        'S': tx_data['ReferenceAccount'],
                    },
                ],
                'ComparisonOperator': 'EQ'
            }
        }
        filter = {
                'RequestId': {
                    'AttributeValueList': [
                        {
                            'S': '{}'.format(tx_data['PreviousRequestIdReference']),
                        },
                    ],
                    'ComparisonOperator': 'EQ'
                }
            }
        previous_record = json.loads(
            get_dynamodb_record_by_primary_index_query_with_filter(
                key=key,
                query_filter=filter,
                use_consistent_read=True,
                boto3_clazz=boto3_clazz,
                logger=logger
            )[0]['EventRawData']
        )
        logger.info('Previous unverified transaction data: {}'.format(previous_record))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='EXCEPTION: {}'.format(traceback.format_exc()),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    if len(previous_record) > 0:
        original_amount = Decimal(previous_record['Amount'])
        if verified_amount.compare(original_amount) != Decimal('0'):
            account_balances['Actual'] = account_balances['Actual'] - original_amount + verified_amount
            effect_on_actual_balance = 'Adjusted'
            logger.warning('Amounts differ - Actual balance adjusted to reflect verified amount')
        account_balances['Available'] = account_balances['Available'] + verified_amount
        logger.info('NEW Actual Balance: {}'.format(account_balances['Actual']))
        logger.info('NEW Available Balance: {}'.format(account_balances['Available']))
    else:
        logger.error('Failed to process transaction as previous pending transaction could not be found')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='No previous pending record was found',
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    # Commit to DB
    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        updated_balances=account_balances,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def cash_withdrawal(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'Decrease'
    effect_on_available_balance     = 'Decrease'
    is_pending                      = False
    is_verified                     = True    

    # Check funds available
    account_balances = _helper_calculate_updated_balances(
        account_ref=tx_data['ReferenceAccount'],
        amount=Decimal(tx_data['Amount']),
        effect_on_actual_balance='None',
        effect_on_available_balance='None',
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    available = account_balances['Available']
    withdraw_amount = Decimal(tx_data['Amount'])
    logger.info('Requesting to withdraw {} from available balance of {}'.format(str(withdraw_amount), str(available)))

    # if int(available.compare(withdraw_amount)) < 0:   # Negative balances not allowed - reject transaction
    if int(available.compare(withdraw_amount)) < 0:
        logger.error('Insufficient Funds')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='Insufficient funds in Source account {} - Available {} but amount requested was {}'.format(tx_data['ReferenceAccount'], account_balances['Available'], withdraw_amount),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False
    logger.info('Funds are available')

    # Adjust balances
    account_balances['Actual'] = account_balances['Actual'] - withdraw_amount    
    account_balances['Available'] = account_balances['Available'] - withdraw_amount    

    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        updated_balances=account_balances,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return False


def incoming_payment(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    """
        tx_data = {
            "EventTimeStamp": 1668399202, 
            "TargetAccount": "1234567890", 
            "Amount": "180.00", 
            "SourceInstitution": 
            "ABC Bank", 
            "SourceAccount": "5550101010", 
            "Reference": "Test Transaction", 
            "EventSourceDataResource": {
                "S3Key": "incoming_payment_test0018.event", 
                "S3Bucket": "lab4-new-events-qpwoeiryt"
            }, 
            "TransactionType": "IncomingPayment",
            "ReferenceAccount": "1234567890",
            "RequestId": "test0018"
        }
    """
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'Increase'
    effect_on_available_balance     = 'Increase'
    is_pending                      = False
    is_verified                     = True


    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified),  # event_types = ('VERIFIED',)
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def outgoing_payment_unverified(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'Decrease'
    effect_on_available_balance     = 'Decrease'
    is_pending                      = True
    is_verified                     = False

    # Check funds available
    account_balances = _helper_calculate_updated_balances(
        account_ref=tx_data['ReferenceAccount'],
        amount=Decimal(tx_data['Amount']),
        effect_on_actual_balance='None',
        effect_on_available_balance='None',
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    available = account_balances['Available']
    outgoing_payment_amount = Decimal(tx_data['Amount'])
    logger.info('Requesting to send payment of {} from available balance of {}'.format(str(outgoing_payment_amount), str(available)))

    # if available.compare(outgoing_payment_amount) < Decimal('0') is True:   # Negative balances not allowed - reject transaction
    if int(available.compare(outgoing_payment_amount)) < 0:
        logger.error('Insufficient Funds')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='Insufficient funds in Source account {} - Available {} but amount requested was {}'.format(tx_data['ReferenceAccount'], account_balances['Available'], outgoing_payment_amount),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False
    logger.info('Funds are available')

    # Adjust balances
    account_balances['Actual'] = account_balances['Actual'] - outgoing_payment_amount    
    account_balances['Available'] = account_balances['Available'] - outgoing_payment_amount  

    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        updated_balances=account_balances,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def outgoing_payment_verified(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'None'
    effect_on_available_balance     = 'None'
    is_pending                      = False
    is_verified                     = True

    # Get amount from previous pending transaction
    previous_record = dict()
    try:
        key = {
            'PK': {
                'AttributeValueList': [
                    {
                        'S': tx_data['ReferenceAccount'],
                    },
                ],
                'ComparisonOperator': 'EQ'
            }
        }
        filter = {
                'RequestId': {
                    'AttributeValueList': [
                        {
                            'S': '{}'.format(tx_data['PreviousRequestIdReference']),
                        },
                    ],
                    'ComparisonOperator': 'EQ'
                }
            }
        previous_record = json.loads(
            get_dynamodb_record_by_primary_index_query_with_filter(
                key=key,
                query_filter=filter,
                use_consistent_read=True,
                boto3_clazz=boto3_clazz,
                logger=logger
            )[0]['EventRawData']
        )
        logger.info('Previous unverified transaction data: {}'.format(previous_record))
        tx_data['Amount'] = previous_record['Amount']
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='EXCEPTION: {}'.format(traceback.format_exc()),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    if len(previous_record) == 0:
        logger.error('No previous pending record was found')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='No previous pending record was found',
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def outgoing_payment_rejected(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance        = 'Increase'
    effect_on_available_balance     = 'Increase'
    is_pending                      = False
    is_verified                     = True

    # Get amount from previous pending transaction
    previous_record = dict()
    try:
        key = {
            'PK': {
                'AttributeValueList': [
                    {
                        'S': tx_data['ReferenceAccount'],
                    },
                ],
                'ComparisonOperator': 'EQ'
            }
        }
        filter = {
                'RequestId': {
                    'AttributeValueList': [
                        {
                            'S': '{}'.format(tx_data['PreviousRequestIdReference']),
                        },
                    ],
                    'ComparisonOperator': 'EQ'
                }
            }
        previous_record = json.loads(
            get_dynamodb_record_by_primary_index_query_with_filter(
                key=key,
                query_filter=filter,
                use_consistent_read=True,
                boto3_clazz=boto3_clazz,
                logger=logger
            )[0]['EventRawData']
        )
        logger.info('Previous unverified transaction data: {}'.format(previous_record))
        tx_data['Amount'] = previous_record['Amount']
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='EXCEPTION: {}'.format(traceback.format_exc()),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    if len(previous_record) == 0:
        logger.error('No previous pending record was found')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='No previous pending record was found',
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False

    _helper_commit_transaction_events(
        tx_data=tx_data, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending, is_verified=is_verified), 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    _helper_commit_updated_balances(
        tx_data=tx_data, 
        effect_on_actual_balance=effect_on_actual_balance,
        effect_on_available_balance=effect_on_available_balance,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


def inter_account_transfer(tx_data: dict, logger=get_logger(), boto3_clazz=boto3)->bool:
    logger.info('Processing Started')
    debug_log('tx_data={}', variable_as_list=[tx_data,], logger=logger)

    effect_on_actual_balance_outgoing        = 'Decrease'
    effect_on_available_balance_outgoing     = 'Decrease'
    is_pending_outgoing                      = False
    is_verified_outgoing                     = True

    effect_on_actual_balance_incoming        = 'Increase'
    effect_on_available_balance_incoming     = 'Increase'
    is_pending_incoming                      = False
    is_verified_incoming                     = True

    tx_data_outgoing = copy.deepcopy(tx_data)
    tx_data_incoming = copy.deepcopy(tx_data)
    tx_data_incoming['ReferenceAccount'] = copy.deepcopy(tx_data_outgoing['TargetAccount'])
    logger.info('Processing transfer from account {} to account {}'.format(tx_data_outgoing['ReferenceAccount'],tx_data_incoming['ReferenceAccount']))

    # Check funds available
    logger.info('STEP: Check funds available on OUTGOING account {}'.format(tx_data_outgoing['ReferenceAccount']))
    account_balances_outgoing = _helper_calculate_updated_balances(
        account_ref=tx_data_outgoing['ReferenceAccount'],
        amount=Decimal(tx_data['Amount']),
        effect_on_actual_balance='None',
        effect_on_available_balance='None',
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    available_outgoing = account_balances_outgoing['Available']
    outgoing_transfer_amount = Decimal(tx_data['Amount'])
    logger.info('Requesting transfer of {} from available balance of {} on account reference {}'.format(str(outgoing_transfer_amount), str(available_outgoing), tx_data_outgoing['ReferenceAccount']))

    # if available_outgoing.compare(outgoing_transfer_amount) < Decimal('0') is True:   # Negative balances not allowed - reject transaction
    if int(available_outgoing.compare(outgoing_transfer_amount)) < 0:
        logger.error('Insufficient Funds')
        update_object_table_add_event(
            origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
            event_timestamp=tx_data['EventTimeStamp'],
            tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
            tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
            reference_account_number=tx_data['ReferenceAccount'],
            event_type='ProcessingEvent',
            is_error=True,
            error_message='Insufficient funds in Source account {} - Available {} but amount requested was {}'.format(tx_data_outgoing['ReferenceAccount'], account_balances_outgoing['Available'], outgoing_transfer_amount),
            boto3_clazz=boto3_clazz,
            logger=logger
        )
        return False
    logger.info('Funds are available')

    # Adjust balances
    logger.info('STEP: Adjusting account balances on OUTGOING account {}'.format(tx_data_outgoing['ReferenceAccount']))
    account_balances_outgoing['Actual'] = account_balances_outgoing['Actual'] - outgoing_transfer_amount    
    account_balances_outgoing['Available'] = account_balances_outgoing['Available'] - outgoing_transfer_amount  

    # Process OUTGOING
    logger.info('STEP: Committing transaction EVENT on OUTGOING account {}'.format(tx_data_outgoing['ReferenceAccount']))
    _helper_commit_transaction_events(
        tx_data=tx_data_outgoing, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending_outgoing, is_verified=is_verified_outgoing), 
        effect_on_actual_balance=effect_on_actual_balance_outgoing,
        effect_on_available_balance=effect_on_available_balance_outgoing,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('STEP: Committing transaction UPDATE_BALANCES on OUTGOING account {}'.format(tx_data_outgoing['ReferenceAccount']))
    _helper_commit_updated_balances(
        tx_data=tx_data, 
        updated_balances=account_balances_outgoing,
        effect_on_actual_balance=effect_on_actual_balance_outgoing,
        effect_on_available_balance=effect_on_available_balance_outgoing,
        boto3_clazz=boto3_clazz,
        logger=logger
    )


    # Process INCOMING
    logger.info('STEP: Committing transaction EVENT on INCOMING account {}'.format(tx_data_incoming['ReferenceAccount']))
    _helper_commit_transaction_events(
        tx_data=tx_data_incoming, 
        event_types=_helper_event_types_as_tuple(is_pending=is_pending_incoming, is_verified=is_verified_incoming),  # event_types = ('VERIFIED',)
        effect_on_actual_balance=effect_on_actual_balance_incoming,
        effect_on_available_balance=effect_on_available_balance_incoming,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('STEP: Committing transaction UPDATE_BALANCES on INCOMING account {}'.format(tx_data_incoming['ReferenceAccount']))
    _helper_commit_updated_balances(
        tx_data=tx_data_incoming, 
        effect_on_actual_balance=effect_on_actual_balance_incoming,
        effect_on_available_balance=effect_on_available_balance_incoming,
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    # Add event object processing record
    update_object_table_add_event(
        origin_event_key=tx_data['EventSourceDataResource']['S3Key'],
        event_timestamp=tx_data['EventTimeStamp'],
        tx_date=_helper_tx_date(timestamp=tx_data['EventTimeStamp']),
        tx_time=_helper_tx_time(timestamp=tx_data['EventTimeStamp']),
        reference_account_number=tx_data['ReferenceAccount'],
        event_type='ProcessingEvent',
        is_error=False,
        error_message='no-error',
        boto3_clazz=boto3_clazz,
        logger=logger
    )

    logger.info('Processing Done')
    return True


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


TX_TYPE_HANDLER_MAP = {
    'CashDeposit': cash_deposit,
    'VerifyCashDeposit': verify_cash_deposit,
    'CashWithdrawal': cash_withdrawal,
    'IncomingPayment': incoming_payment,
    'UnverifiedOutgoingPayment': outgoing_payment_unverified,
    'VerifiedOutgoingPayment': outgoing_payment_verified,
    'RejectedOutgoingPayment': outgoing_payment_rejected,
    'InterAccountTransfer': inter_account_transfer,
}

    
def handler(
    event,
    context,
    logger=get_logger(level=logging.INFO),
    boto3_clazz=boto3,
    run_from_main: bool=False
):
    if os.getenv('DYNAMODB_RESTORE_IN_PROGRESS', '0') != '0':
        logger.error('ABANDON PROCESSING - DynamoDB Restore in Progress')
        raise Exception('Processing Abandoned due to DB Restore in progress.')
    refresh_environment_cache(logger=logger)
    if cache['Environment']['Data']['DEBUG'] is True and run_from_main is False:
        logger  = get_logger(level=logging.DEBUG)
    
    debug_log('event={}', variable_as_list=[event], logger=logger)
    """
        event={
            "Records": [
                {
                    "messageId": "...",
                    "receiptHandle": "...",
                    "body": "...data...",
                    "attributes": {
                        ...
                    },
                    "messageAttributes": {},
                    "md5OfBody": "...",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:eu-central-1:342872205792:AccountTransactionQueue.fifo",
                    "awsRegion": "eu-central-1"
                }
            ]
        }

        body:       NOTE: Exact Fields Depends on TransactionType

            {
                "EventTimeStamp": 1668399202, 
                "TargetAccount": "1234567890", 
                "Amount": "180.00", 
                "SourceInstitution": 
                "ABC Bank", 
                "SourceAccount": "5550101010", 
                "Reference": "Test Transaction", 
                "EventSourceDataResource": {                            <==> Enriched Data - present in all events
                    "S3Key": "incoming_payment_test0018.event",         <==> Enriched Data - present in all events
                    "S3Bucket": "lab4-new-events-qpwoeiryt"             <==> Enriched Data - present in all events
                },                                                      <==> Enriched Data - present in all events
                "TransactionType": "IncomingPayment",                   <==> Enriched Data - present in all events
                "ReferenceAccount": "1234567890",                       <==> Enriched Data - present in all events
                "RequestId": "test0018"                                 <==> Enriched Data - present in all events
            }        

    """
    try:
        for record in event['Records']:
            tx_data = json.loads(record['body'])
            if 'TransactionType' in tx_data:
                if tx_data['TransactionType'] in TX_TYPE_HANDLER_MAP:
                    logger.info('Processing Transaction. tx_data={}'.format(tx_data))
                    if TX_TYPE_HANDLER_MAP[tx_data['TransactionType']](tx_data=tx_data, logger=logger, boto3_clazz=boto3_clazz) is True:
                        logger.info('Transaction Processed for Event: {}'.format(tx_data['EventSourceDataResource']))
                    else:
                        logger.error('Transaction Processing Returned Failure.')
                    update_object_sate(
                        tx_data=tx_data,
                        logger=logger,
                        boto3_clazz=boto3_clazz
                    )
                else:
                    logger.error('Field TransactionType has unrecognized value. Cannot proceed with transaction processing. tx_data={}'.format(tx_data))
            else:
                logger.error('Expected field TransactionType but not present. Cannot proceed with transaction processing. tx_data={}'.format(tx_data))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


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