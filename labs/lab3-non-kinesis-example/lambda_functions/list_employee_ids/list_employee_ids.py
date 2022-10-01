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
    'PersonName',
    'PersonSurname',
    'PersonDepartment',
    'PersonStatus',
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


# def dynamodb_data_formatting(
#     data: list,
#     last_evaluation_key: dict=dict(),
#     logger=get_logger()
# )->dict:
#     debug_log(message='data={}', variable_as_list=[data,], logger=logger)
#     EXCLUDE_FIELDS = (
#         'PK',
#         'SK',
#     )
#     result = dict()
#     result['Employees'] = list()
#     result['RecordCount'] = 0
#     result['LastEvaluatedKey'] = dict()
#     result['QueryStatus'] = 'ERROR'
#     result['Message'] = 'Functionality Not Yet Implemented'
#     try:
#         for record in data:
#             debug_log(message='   Evaluating record: {}', variable_as_list=[record,], logger=logger)
#             final_record  = dict()
#             for field_name, field_value in record.items():
#                 if field_name not in EXCLUDE_FIELDS:
#                     final_record[field_name] = field_value
#             result['Employees'].append(final_record)
#         result['LastEvaluatedKey'] = last_evaluation_key
#         qty = len(result['Employees'])
#         result['RecordCount'] = qty
#         result['QueryStatus'] = 'Ok'
#         result['Message'] = '{} Records Included'.format(qty)
#     except:
#         logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
#         result['QueryStatus'] = 'ERROR'
#         result['Message'] = 'Processing Error'    
#     debug_log(message='result={}', variable_as_list=[result,], logger=logger)
#     return result


# def compile_final_attributes_to_get_list(fields_to_retrieve: list, logger=get_logger())->list:
#     ATTRIBUTE_MAP = {
#         'EmployeeSystemId': 'SK',
#         'EmployeeId': 'employee-id',
#         'Department': 'department',
#         'EmployeeStatus': 'employee-status',
#         'EmployeeFirstName': 'first-name',
#         'EmployeeLastName': 'last-name',
#     }
#     MINIMAL_LIST = ['employee-id', 'employee-status', 'first-name', 'last-name']
#     final_list = list()

#     if fields_to_retrieve is None:
#         logger.error('fields_to_retrieve was None - returning MINIMAL_LIST')
#         return MINIMAL_LIST
#     if isinstance(fields_to_retrieve, list) is False:
#         logger.error('fields_to_retrieve is not a list type - returning MINIMAL_LIST')
#         return MINIMAL_LIST
#     if len(fields_to_retrieve) == 0:
#         logger.error('fields_to_retrieve was empty - returning MINIMAL_LIST')
#         return MINIMAL_LIST

#     for requested_field in fields_to_retrieve:
#         if requested_field in ATTRIBUTE_MAP:
#             final_list.append(ATTRIBUTE_MAP[requested_field])
#         else:
#             logger.warning('Unrecognized field name "{}" - ignoring'.format(requested_field))

#     if len(final_list) == 0:
#         logger.warning('final_list was empty - returning MINIMAL_LIST')
#         return MINIMAL_LIST

#     return final_list


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
    logger.info('initial start_key={}'.format(start_key))
    logger.info('final  max_items={}'.format(max_items))
    logger.info('final  attributes_to_get={}'.format(attributes_to_get))
    if start_key is not None:
        if isinstance(start_key, dict):
            for k,v in start_key.items():
                final_start_key = {
                    "PK": {
                        "S": k
                    },
                    "SK": {
                        "S": v
                    }
                }
    logger.info('final start_key={}'.format(start_key))
    try:
        client = get_client('dynamodb', boto3_clazz=boto3_clazz)
        response = dict()
        if len(final_start_key) == 0:
            response = client.scan(
                TableName='lab3-access-card-app',
                AttributesToGet=attributes_to_get,
                Limit=max_items,
                Select='SPECIFIC_ATTRIBUTES',
                ScanFilter={
                    'PK': {
                        'AttributeValueList': [{'S': 'EMP#'},],
                        'ComparisonOperator': 'BEGINS_WITH'
                    }
                },
                ReturnConsumedCapacity='TOTAL',
                ConsistentRead=False
            )
        else:
            response = client.scan(
                TableName='lab3-access-card-app',
                AttributesToGet=attributes_to_get,
                Limit=max_items,
                ExclusiveStartKey=final_start_key,
                Select='SPECIFIC_ATTRIBUTES',
                ScanFilter={
                    'PK': {
                        'AttributeValueList': [{'S': 'EMP#'},],
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
                response['LastEvaluatedKey']['PK']['S']: response['LastEvaluatedKey']['SK']['S'] 
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
    fields_to_retrieve: list=DEFAULT_FIELDS_TO_RETRIEVE,
    max_items: int=25,
    start_key: dict=dict(),
    status_filter: list=['active', 'onboarding'],
    boto3_clazz=boto3,
    logger=get_logger()
)->tuple:
    start_time = get_utc_timestamp(with_decimal=False)
    if max_items > 100:
        max_items = 100
    if max_items < 10:
        max_items = 10
    result = list()
    run = True
    rounds = 0
    attributes_to_get = DEFAULT_FIELDS_TO_RETRIEVE
    # attributes_to_get = compile_final_attributes_to_get_list(fields_to_retrieve=fields_to_retrieve, logger=logger)
    while run:
        debug_log(message='rounds={}', variable_as_list=(rounds,), logger=logger)

        query_result_records, new_start_key = query_employees(
            attributes_to_get=attributes_to_get,
            max_items=max_items,
            start_key=start_key,
            boto3_clazz=boto3_clazz,
            logger=logger
        )

        debug_log(message='query_result_records={}', variable_as_list=(query_result_records,), logger=logger)
        debug_log(message='len(query_result_records[result])={}', variable_as_list=(len(query_result_records['result']),), logger=logger)

        final_query_result_records = list()
        if 'employee-status' in attributes_to_get:
            for record in query_result_records['result']:
                if (len(result) + len(final_query_result_records)) < max_items:
                    if record['employee-status'] in status_filter:
                        logger.info('Employee ID "{}" matched status "{}" to be included'.format(record['employee-id'], record['employee-status']))
                        final_query_result_records.append(record)
                    else:
                        logger.info('EXCLUDING Employee ID "{}" with status "{}" - excluded by requested statuses'.format(record['employee-id'], record['employee-status']))
        else:
            final_query_result_records = query_result_records['result']

        debug_log(message='query_result_records length={} new_start_key={}', variable_as_list=(len(query_result_records), new_start_key,), logger=logger)
        result += final_query_result_records
        start_key = new_start_key
        if len(result) >= max_items:
            logger.info('Maximum records reached. Returning collected data')
            run = False

        rounds += 1
        current_time = get_utc_timestamp(with_decimal=False)
        duration = current_time - start_time
        if duration > 20:
            logger.warning('Maximum Query Time Reached - breaking loop. Rounds={}'.format(rounds))
            run = False
        elif rounds > 1 and len(result) == 0:
            logger.warning('Looping without adding records - breaking loop')
            run = False
    logger.info('rounds={}'.format(rounds))
    return (result, start_key)


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


def query_string_parser(
    event: dict,
    logger=get_logger()
)->dict:
    query_parameters = dict()
    query_parameters['StartKey'] = dict()
    query_parameters['Limit'] = 25
    query_parameters['StatusFields'] = ['active', 'onboarding',]

    ALLOWED_STATUS_FIELD_VALUES = [
        'active',
        'onboarding'
    ]

    try:
        debug_log(message='DEFAULT query_parameters={}', variable_as_list=(query_parameters,), logger=logger)
        if 'queryStringParameters' not in event:
            return query_parameters
        if len(event['queryStringParameters']) == 0:
            return query_parameters

        # Parse the Limit
        if 'qty' in event['queryStringParameters']:
            if int(event['queryStringParameters']['qty']) > 9:
                query_parameters['Limit'] = int(event['queryStringParameters']['qty'])
        if query_parameters['Limit'] > 100:
            query_parameters['Limit'] = 100
        logger.info('Limit={}'.format(query_parameters['Limit']))

        # Parse the start key
        if 'start_key' in event['queryStringParameters']:
            if isinstance(event['queryStringParameters']['start_key'], str):
                if len(event['queryStringParameters']['start_key']) > 0 and ',' in event['queryStringParameters']['start_key']:
                    items = event['queryStringParameters']['start_key'].split(',')
                    query_parameters['StartKey'][items[0]] = items[1]
        logger.info('StartKey={}'.format(query_parameters['StartKey']))

        # Parse Status fields
        if 'status' in event['queryStringParameters']:
            if isinstance(event['queryStringParameters']['status'], str):
                if len(event['queryStringParameters']['status']) > 0:
                    query_parameters['StatusFields'] = list()
                    for requested_status in  event['queryStringParameters']['status'].split(','):
                        if requested_status in ALLOWED_STATUS_FIELD_VALUES:
                            query_parameters['StatusFields'].append(requested_status)
        logger.info('StatusFields={}'.format(query_parameters['StatusFields']))

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    
    debug_log(message='FINAL query_parameters={}', variable_as_list=(query_parameters,), logger=logger)
    return query_parameters

    
def handler(
    event,
    context,
    logger=get_logger(level=logging.INFO),
    boto3_clazz=boto3,
    run_from_main: bool=False,
    number_of_records: int=25,
    fields_to_retrieve: list=DEFAULT_FIELDS_TO_RETRIEVE,
    start_key: dict=dict(),
    status_filter: list=['active', 'onboarding']
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
    parsed_query_string_values = query_string_parser(
        event=event,
        logger=logger
    )

    if len(start_key) == 0 and len(parsed_query_string_values['StartKey']) > 0:
        start_key = parsed_query_string_values['StartKey']
    if parsed_query_string_values['Limit'] != number_of_records:
        number_of_records = parsed_query_string_values['Limit']
    if len(parsed_query_string_values['StatusFields']) == 1:
        status_filter = parsed_query_string_values['StatusFields']

    logger.info('Query Parameter: start_key         = {}'.format(start_key))
    logger.info('Query Parameter: number_of_records = {}'.format(number_of_records))
    logger.info('Query Parameter: status_filter     = {}'.format(status_filter))

    dynamodb_result, last_evaluation_key = query_employees_helper(
        fields_to_retrieve=fields_to_retrieve,
        max_items=number_of_records,
        start_key=start_key,
        status_filter=status_filter,
        boto3_clazz=boto3_clazz,
        logger=logger
    )
    debug_log(message='dynamodb_result={}', variable_as_list=[dynamodb_result,], logger=logger)


    # query_data = dynamodb_data_formatting(data=dynamodb_result, logger=logger, last_evaluation_key=last_evaluation_key)
    # debug_log(message='query_data={}', variable_as_list=[query_data,], logger=logger)
    # return_object['body'] = json.dumps(query_data)

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

    event = {
        'version': '2.0', 
        'routeKey': 'GET /access-card-app/employees', 
        'rawPath': '/sandbox/access-card-app/employees', 
        'rawQueryString': 'start_key=access-card%23profile%23100000000203,8a05af74c47bfbf5efe8737a43413bfe407db898d572095332a659800d6a5e83AC&qty=12&status=onboarding', 
        'headers': {
            'accept': '*/*', 
            'content-length': '0', 
            'host': 'aaaaaaaaaa.execute-api.eu-central-1.amazonaws.com', 
            'user-agent': 'curl/7.81.0', 
            'x-amzn-trace-id': 'aaaaaaaaaa', 
            'x-forwarded-for': 'nnn.nnn.nnn.nnn', 
            'x-forwarded-port': '443', 
            'x-forwarded-proto': 'https'
        }, 
        'queryStringParameters': {
            'qty': '12', 
            'start_key': 'access-card#profile#100000000203,8a05af74c47bfbf5efe8737a43413bfe407db898d572095332a659800d6a5e83AC', 
            'status': 'onboarding'
        }, 
        'requestContext': {
            'accountId': '000000000000', 
            'apiId': 'aaaaaaaaaa', 
            'domainName': 'aaaaaaaaaa.execute-api.eu-central-1.amazonaws.com', 
            'domainPrefix': 'aaaaaaaaaa', 
            'http': {
                'method': 'GET', 
                'path': '/sandbox/access-card-app/employees', 
                'protocol': 'HTTP/1.1', 
                'sourceIp': 'nnn.nnn.nnn.nnn', 
                'userAgent': 'curl/7.81.0'
            }, 
            'requestId': 'Y842FhTEliAEJVw=', 
            'routeKey': 'GET /access-card-app/employees', 
            'stage': 'sandbox', 
            'time': '24/Sep/2022:06:20:48 +0000', 
            'timeEpoch': 1664000448395
        }, 
        'isBase64Encoded': False
    }

    result1 = handler(event=event, context=None, logger=logger, run_from_main=True, number_of_records=5, start_key=start_key, fields_to_retrieve=fields_to_retrieve)
    print('------------------------------------------------------------------------------------------------------------------------')
    print('{}'.format(json.dumps(result1)))

    # result2 = handler(event={'Message': None}, context=None, logger=logger, run_from_main=True)
    # print('------------------------------------------------------------------------------------------------------------------------')
    # print('{}'.format(json.dumps(result2)))


    """
        Typical query with all query parameters present:

            curl https://b5w5zwr0vj.execute-api.eu-central-1.amazonaws.com/sandbox/access-card-app/employees\?start_key\=access-card#profile#100000000203,8a05af74c47bfbf5efe8737a43413bfe407db898d572095332a659800d6a5e83AC\&qty\=12\&status\=onboarding

        API Gateway event payload for the above request:

            {
                "version": "2.0",
                "routeKey": "GET /access-card-app/employees",
                "rawPath": "/sandbox/access-card-app/employees",
                "rawQueryString": "start_key=access-card%23profile%23100000000203,8a05af74c47bfbf5efe8737a43413bfe407db898d572095332a659800d6a5e83AC&qty=12&status=onboarding",
                "headers": {
                    "accept": "*/*",
                    "content-length": "0",
                    "host": "aaaaaaaaaa.execute-api.eu-central-1.amazonaws.com",
                    "user-agent": "curl/7.81.0",
                    "x-amzn-trace-id": "aaaaaaaaaa",
                    "x-forwarded-for": "nnn.nnn.nnn.nnn",
                    "x-forwarded-port": "443",
                    "x-forwarded-proto": "https"
                },
                "queryStringParameters": {
                    "qty": "12",
                    "start_key": "access-card#profile#100000000203,8a05af74c47bfbf5efe8737a43413bfe407db898d572095332a659800d6a5e83AC",
                    "status": "onboarding"
                },
                "requestContext": {
                    "accountId": "000000000000",
                    "apiId": "aaaaaaaaaa",
                    "domainName": "aaaaaaaaaa.execute-api.eu-central-1.amazonaws.com",
                    "domainPrefix": "aaaaaaaaaa",
                    "http": {
                        "method": "GET",
                        "path": "/sandbox/access-card-app/employees",
                        "protocol": "HTTP/1.1",
                        "sourceIp": "nnn.nnn.nnn.nnn",
                        "userAgent": "curl/7.81.0"
                    },
                    "requestId": "Y842FhTEliAEJVw=",
                    "routeKey": "GET /access-card-app/employees",
                    "stage": "sandbox",
                    "time": "24/Sep/2022:06:20:48 +0000",
                    "timeEpoch": 1664000448395
                },
                "isBase64Encoded": false
            }
    """

