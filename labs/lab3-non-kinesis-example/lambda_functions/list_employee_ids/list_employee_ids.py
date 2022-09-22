import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
import base64
from urllib.parse import parse_qs


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


def debug_log(
    message: str,
    variables_as_dict: dict=dict(),
    variable_as_list: list=list(),
    logger=get_logger(level=logging.INFO),
    debug_override: bool=False
):
    if cache['Environment']['Data']['DEBUG'] is True or debug_override is True:
        caller = getframeinfo(stack()[1][0])
        caller_str = '{}():{}'.format(caller.function, caller.lineno)
        try:
            message = '[{}]  {}'.format(caller_str, message)
            if len(variables_as_dict) > 0:
                logger.debug(message.format(**variables_as_dict))
            else:
                logger.debug(message.format(*variable_as_list))
        except:
            pass


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


def extract_post_data(event)->str:
    if 'requestContext' in event:
        if 'http' in event['requestContext']:
            if 'method' in event['requestContext']['http']:
                if event['requestContext']['http']['method'].upper() in ('POST', 'PUT', 'DELETE'):  # see https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods
                    if 'isBase64Encoded' in event and 'body' in event:
                        if event['isBase64Encoded'] is True:
                            body = base64.b64decode(event['body'])
                            if isinstance(body, bytes):
                                body = body.decode('utf-8')
                            return body
                    if 'body' in event:
                        body = event['body']
                        if isinstance(body, bytes):
                            body = body.decode('utf-8')
                        else:
                            body = '{}'.format(body)
                        return body
    return ""


def decode_data(event, body: str):
    if 'headers' in event:
        if 'content-type' in event['headers']:
            if 'json' in event['headers']['content-type'].lower():
                return json.loads(body)
            if 'x-www-form-urlencoded' in event['headers']['content-type'].lower():
                return parse_qs(body)
    return body


###############################################################################
###                                                                         ###
###                 A W S    A P I    I N T E G R A T I O N                 ###
###                                                                         ###
###############################################################################


def query_employees(
    max_items: int=100,
    start_key: dict=dict(),
    boto3_clazz=boto3,
    logger=get_logger()
)->dict:
    result = dict()
    result['Records'] = list()
    result['RecordCount'] = 0
    result['LastEvaluatedKey'] = dict()
    result['QueryStatus'] = 'ERROR'
    result['Message'] = 'Functionality Not Yet Implemented'

    RECORD_NAME_MAP = {
        "subject-id": "EmployeeSystemId",
        "department": "Department",
        "employee-id": "EmployeeId",
        "employee-status": "EmployeeStatus",
        "first-name": "EmployeeFirstName",
        "last-name": "EmployeeLastName"
    }

    EXCLUDE_FIELDS = (
        'subject-topic',
    )

    if max_items > 100:
        logger.warning('max_items was {} which is more than the absolute max. of 100.'.format(max_items))
        max_items = 100

    try:
        client = get_client('dynamodb', boto3_clazz=boto3_clazz)
        response = dict()
        if len(start_key) == 0:
            response = client.scan(
                TableName='access-card-app',
                AttributesToGet=[
                    'subject-id',
                    'subject-topic',
                    'department',
                    'employee-id',
                    'employee-status',
                    'first-name',
                    'last-name',
                ],
                Limit=max_items,
                Select='SPECIFIC_ATTRIBUTES',
                ScanFilter={
                    'subject-topic': {
                        'AttributeValueList': [{'S': 'employee#profile#'},],
                        'ComparisonOperator': 'BEGINS_WITH'
                    }
                },
                ReturnConsumedCapacity='TOTAL',
                ConsistentRead=False
            )
        else:
            start_key_data = dict()
            for start_key_name, start_key_value in start_key.items():
                start_key_data[start_key_name] = dict()
                start_key_data[start_key_name]['S'] = start_key_value
            response = client.scan(
                TableName='access-card-app',
                AttributesToGet=[
                    'subject-id',
                    'subject-topic',
                    'department',
                    'employee-id',
                    'employee-status',
                    'first-name',
                    'last-name',
                ],
                Limit=max_items,
                ExclusiveStartKey=start_key_data,
                Select='SPECIFIC_ATTRIBUTES',
                ScanFilter={
                    'subject-topic': {
                        'AttributeValueList': [{'S': 'employee#profile#'},],
                        'ComparisonOperator': 'BEGINS_WITH'
                    }
                },
                ReturnConsumedCapacity='TOTAL',
                ConsistentRead=False
            )
        debug_log(message='response={}', variable_as_list=[response,])
        if 'Items' in response:
            for item in response['Items']:
                record = dict()
                for field_name, field_data in item.items():
                    if field_name not in EXCLUDE_FIELDS:
                        final_field_name = field_name
                        if field_name in RECORD_NAME_MAP:
                            final_field_name = RECORD_NAME_MAP[field_name]
                        for field_data_type, field_data_value in field_data.items():
                            record[final_field_name] = '{}'.format(field_data_value)
                result['Records'].append(record)
        if 'LastEvaluatedKey' in response:
            for next_key, next_data in response['LastEvaluatedKey'].items():
                result['LastEvaluatedKey'][next_key] = '{}'.format(next_data['S'])
        result['QueryStatus'] = 'OK'
        result['Message'] = 'Query Executed.'
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        result['QueryStatus'] = 'ERROR'
        result['Message'] = 'Processing Error'

    return result


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
    result = dict()
    return_object = {
        'statusCode': 200,
        'headers': {
            'content-type': 'application/json',
        },
        'body': result,
        'isBase64Encoded': False,
    }
    refresh_environment_cache(logger=logger)
    if cache['Environment']['Data']['DEBUG'] is True and run_from_main is False:
        logger  = get_logger(level=logging.DEBUG)
    
    debug_log(message='event={}', variable_as_list=[event,], logger=logger)
    
    query_data = query_employees(
        max_items=10,
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    debug_log(message='query_data={}', variable_as_list=[query_data,], logger=logger)
    return_object['body'] = query_data

    debug_log('return_object={}', variable_as_list=[return_object,], logger=logger)
    return return_object


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

    result1 = handler(event={'Message': None}, context=None, logger=logger, run_from_main=True)
    print('------------------------------------------------------------------------------------------------------------------------')
    print('{}'.format(json.dumps(result1)))

    result2 = handler(event={'Message': None}, context=None, logger=logger, run_from_main=True)
    print('------------------------------------------------------------------------------------------------------------------------')
    print('{}'.format(json.dumps(result2)))


