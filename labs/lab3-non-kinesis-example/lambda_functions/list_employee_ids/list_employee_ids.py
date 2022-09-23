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


DEFAULT_FIELDS_TO_RETRIEVE = [
    'EmployeeSystemId',
    'EmployeeId',
    'Department',
    'EmployeeStatus',
    'EmployeeFirstName',
    'EmployeeLastName',
]


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


def dynamodb_data_formatting(
    data: list,
    last_evaluation_key: dict=dict(),
    logger=get_logger()
)->dict:
    debug_log(message='data={}', variable_as_list=[data,], logger=logger)
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
    result = dict()
    result['Employees'] = list()
    result['RecordCount'] = 0
    result['LastEvaluatedKey'] = dict()
    result['QueryStatus'] = 'ERROR'
    result['Message'] = 'Functionality Not Yet Implemented'
    try:
        for record in data:
            debug_log(message='   Evaluating record: {}', variable_as_list=[record,], logger=logger)
            final_record  = dict()
            for field_name, field_value in record.items():
                if field_name not in EXCLUDE_FIELDS:
                    final_field_name = field_name
                    if field_name in RECORD_NAME_MAP:
                        final_field_name = RECORD_NAME_MAP[field_name]
                        final_record[final_field_name] = field_value
            result['Employees'].append(final_record)
        result['LastEvaluatedKey'] = last_evaluation_key
        qty = len(result['Employees'])
        result['RecordCount'] = qty
        result['QueryStatus'] = 'Ok'
        result['Message'] = '{} Records Included'.format(qty)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        result['QueryStatus'] = 'ERROR'
        result['Message'] = 'Processing Error'    
    debug_log(message='result={}', variable_as_list=[result,], logger=logger)
    return result


def compile_final_attributes_to_get_list(fields_to_retrieve: list, logger=get_logger())->list:
    ATTRIBUTE_MAP = {
        'EmployeeSystemId': 'subject-id',
        'EmployeeId': 'employee-id',
        'Department': 'department',
        'EmployeeStatus': 'employee-status',
        'EmployeeFirstName': 'first-name',
        'EmployeeLastName': 'last-name',
    }
    MINIMAL_LIST = ['employee-id', 'employee-status', 'first-name', 'last-name']
    final_list = list()

    if fields_to_retrieve is None:
        logger.error('fields_to_retrieve was None - returning MINIMAL_LIST')
        return MINIMAL_LIST
    if isinstance(fields_to_retrieve, list) is False:
        logger.error('fields_to_retrieve is not a list type - returning MINIMAL_LIST')
        return MINIMAL_LIST
    if len(fields_to_retrieve) == 0:
        logger.error('fields_to_retrieve was empty - returning MINIMAL_LIST')
        return MINIMAL_LIST

    for requested_field in fields_to_retrieve:
        if requested_field in ATTRIBUTE_MAP:
            final_list.append(ATTRIBUTE_MAP[requested_field])
        else:
            logger.warning('Unrecognized field name "{}" - ignoring'.format(requested_field))

    if len(final_list) == 0:
        logger.warning('final_list was empty - returning MINIMAL_LIST')
        return MINIMAL_LIST

    return final_list


###############################################################################
###                                                                         ###
###                 A W S    A P I    I N T E G R A T I O N                 ###
###                                                                         ###
###############################################################################


def query_employees(
    attributes_to_get: list,
    max_items: int=25,
    start_key: dict=dict(),
    boto3_clazz=boto3,
    logger=get_logger()
)->tuple:
    result = list()
    final_result = list()
    if max_items > 100:
        logger.warning('max_items was {} which is more than the absolute max. of 100.'.format(max_items))
        max_items = 100
    final_start_key = dict()
    if start_key is not None:
        if isinstance(start_key, dict):
            for k,v in start_key.items():
                if k.startswith('employee#profile#'):
                    final_start_key = {
                        "subject-topic": {
                            "S": k
                        },
                        "subject-id": {
                            "S": v
                        }
                    }
    try:
        client = get_client('dynamodb', boto3_clazz=boto3_clazz)
        response = dict()
        if len(final_start_key) == 0:
            response = client.scan(
                TableName='access-card-app',
                AttributesToGet=attributes_to_get,
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
            response = client.scan(
                TableName='access-card-app',
                AttributesToGet=attributes_to_get,
                Limit=max_items,
                ExclusiveStartKey=final_start_key,
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
                    for field_data_type, field_data_value in field_data.items():
                        record[field_name] = '{}'.format(field_data_value) 
                result.append(record)
                debug_log(message='record length now {} - Added record {}', variable_as_list=[len(result), record,], logger=logger)
        if 'LastEvaluatedKey' in response:
            start_key = {
                response['LastEvaluatedKey']['subject-topic']['S']: response['LastEvaluatedKey']['subject-id']['S'] 
            }
            final_result = (
                {
                    'result': result,
                }, 
                start_key
            )
        else:
            final_result = (
                {
                    'result': result,
                }, 
                dict()
            )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log(message='final_result={}', variable_as_list=(final_result,), logger=logger)
    return tuple(final_result)


def query_employees_helper(
    fields_to_retrieve: list,
    max_items: int=25,
    start_key: dict=dict(),
    boto3_clazz=boto3,
    logger=get_logger()
)->tuple:
    if max_items > 100:
        max_items = 100
    if max_items < 10:
        max_items = 10
    result = list()
    run = True
    rounds = 0
    attributes_to_get = compile_final_attributes_to_get_list(fields_to_retrieve=fields_to_retrieve, logger=logger)
    while run:
        query_max_items = max_items - len(result) + 1
        if query_max_items > 0:
            query_result_records, new_start_key = query_employees(
                attributes_to_get=attributes_to_get,
                max_items=query_max_items,
                start_key=start_key,
                boto3_clazz=boto3_clazz,
                logger=logger
            )
            debug_log(message='query_result_records length={} new_start_key={}', variable_as_list=(len(query_result_records), new_start_key,), logger=logger)
            result += query_result_records['result']
            start_key = new_start_key
            if len(result) >= max_items:
                logger.info('Maximum records reached. Returning collected data')
                run = False

        rounds += 1
        if rounds > 10:
            logger.warning('Maximum Rounds Reached - breaking loop')
            run = False
        elif rounds > 1 and len(result) == 0:
            logger.warning('Looping without adding records - breaking loop')
            run = False
    return (result, start_key)


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
    run_from_main: bool=False,
    number_of_records: int=25,
    fields_to_retrieve: list=DEFAULT_FIELDS_TO_RETRIEVE,
    start_key: dict=dict() 
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
    
    # TODO Extract the start key data from the query string
    # TODO override the number_of_records if it was set in the query string
    # TODO override fields_to_retrieve from query string request
    dynamodb_result, last_evaluation_key = query_employees_helper(
        fields_to_retrieve=fields_to_retrieve,
        max_items=number_of_records,
        start_key=start_key,
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    debug_log(message='dynamodb_result={}', variable_as_list=[dynamodb_result,], logger=logger)


    query_data = dynamodb_data_formatting(data=dynamodb_result, logger=logger, last_evaluation_key=last_evaluation_key)
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

    # fields_to_retrieve = list()
    fields_to_retrieve = ['EmployeeId', 'EmployeeFirstName', 'EmployeeLastName']
    start_key = dict() 
    # start_key = {"employee#profile#100000000189": "491fb2e94211a095bd388f9a250022d22c9f3b5adde478514cd6b5a70a63d84e-E"}

    result1 = handler(event={'Message': None}, context=None, logger=logger, run_from_main=True, number_of_records=5, start_key=start_key, fields_to_retrieve=fields_to_retrieve)
    print('------------------------------------------------------------------------------------------------------------------------')
    print('{}'.format(json.dumps(result1)))

    # result2 = handler(event={'Message': None}, context=None, logger=logger, run_from_main=True)
    # print('------------------------------------------------------------------------------------------------------------------------')
    # print('{}'.format(json.dumps(result2)))


