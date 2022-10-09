from cmath import log
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
    formatter = logging.Formatter(
        '%(funcName)s:%(lineno)d -  %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(level)
    return logger


def get_client(client_name: str, region: str = 'eu-central-1', boto3_clazz=boto3):
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


def get_debug() -> bool:
    try:
        return bool(int(os.getenv('DEBUG', '0')))
    except:
        pass
    return False


def get_cache_ttl(logger=get_logger()) -> int:
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


def debug_log(message: str, variables_as_dict: dict = dict(), variable_as_list: list = list(), logger=get_logger(level=logging.INFO)):
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
###                 A W S    A P I    I N T E G R A T I O N                 ###
###                                                                         ###
###############################################################################


def get_employee_access_card_record(
    employee_id,
    client=get_client(client_name="dynamodb"),
    logger=get_logger(level=logging.INFO)
) -> dict:
    result = dict()
    result['AccessCardLinked'] = False
    result['EmployeeStatus'] = 'unknown'
    result['Name'] = None
    result['Surname'] = None
    result['AccessCardData'] = dict()
    try:
        response = client.query(
            TableName='lab3-access-card-app',
            Select='ALL_ATTRIBUTES',
            Limit=2,
            ConsistentRead=True,
            ReturnConsumedCapacity='TOTAL',
            KeyConditionExpression='PK = :pk and begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': {'S': 'EMP#{}'.format(employee_id), },
                ':sk': {'S': 'PERSON#PERSONAL_DATA', }
            }
        )
        logger.debug('response={}'.format(json.dumps(response, default=str)))
        if 'Items' in response:
            if len(response['Items']) > 0:
                for item in response['Items']:
                    if item['SK']['S'] == 'PERSON#PERSONAL_DATA':
                        result['EmployeeStatus'] = item['PersonStatus']['S'].title()
                        result['Name'] = item['PersonName']['S'].title()
                        result['Surname'] = item['PersonSurname']['S'].title()
                    elif item['SK']['S'] == 'PERSON#PERSONAL_DATA#ACCESS_CARD':
                        card_issue_timestamp = int(item['CardIssuedTimestamp']['N'])
                        result['AccessCardData'][card_issue_timestamp] = dict()
                        result['AccessCardData'][card_issue_timestamp]['CardId'] = item['CardIdx']['S']
                        result['AccessCardData'][card_issue_timestamp]['IssuedBy'] = item['CardIssuedBy']['S']
                        result['AccessCardData'][card_issue_timestamp]['CardStatus'] = item['CardStatus']['S']
        # Check if last card issued is status ISSUED
        if len(result['AccessCardData']) > 0:
            issue_timestamps = list(result['AccessCardData'].keys())
            issue_timestamps.sort(reverse=True)
            if result['AccessCardData'][issue_timestamps[0]]['CardStatus'] == 'issued':
                result['AccessCardLinked'] = True
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        result = dict()
    logger.debug('result={}'.format(json.dumps(result, default=str)))
    return result


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


def _extract_employee_id_from_path(event: dict, logger=get_logger()) -> str:
    employee_id = None
    if 'rawPath' in event:
        # Expecting /access-card-app/employee/<<employee-id>>/access-card-status
        path_elements = event['rawPath'].split('/')
        if len(path_elements) < 5 or len(path_elements) > 6:
            logger.error('Path has wrong number of parts. Expected 5 or 6, but got {}'.format(len(path_elements)))
            return employee_id
        potential_employee_id = -1
        if len(path_elements) == 5:
            potential_employee_id = path_elements[3]
        else:
            potential_employee_id = path_elements[4]
        logger.info('Integer range validation of id "{}"'.format(potential_employee_id))
        
    return employee_id


def _extract_json_body_as_dict(event: dict, logger=get_logger())->dict:
    data = dict()
    try:
        if event['requestContext']['http']['method'] == 'GET':
            logger.error('Cannot extract body from a GET request')
            return data
        data = json.loads(event['body'])
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log(message='data={}'.format(data), variable_as_list=[data, ], logger=logger)
    return data


def _validate_basic_request_data_is_valid(employee_id: str, body_data: dict, logger=get_logger())->bool:
    try:
        if int(employee_id) < 10000000000 or int(employee_id) > 99999999999:
            logger.error('Employee ID basic validation failed')
            return False
        if 'CardId' not in body_data:
            logger.error('CardId not found in request body')
            return False
        if 'CompleteOnboarding' not in body_data:
            logger.error('CompleteOnboarding not found in request body')
            return False
        if 'LinkedBy' not in body_data:
            logger.error('LinkedBy not found in request body')
            return False
        if int(body_data['CardId']) < 10000000000 or int(body_data['CardId']) > 99999999999:
            logger.error('CardId basic validation failed')
            return False
        if int(body_data['LinkedBy']) < 10000000000 or int(body_data['LinkedBy']) > 99999999999:
            logger.error('LinkedBy basic validation failed')
            return False
        if isinstance(body_data['CompleteOnboarding'], bool) is False:
            logger.error('CompleteOnboarding basic validation failed')
            return False
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        return False
    return True


def handler(
    event,
    context,
    logger=get_logger(level=logging.INFO),
    boto3_clazz=boto3,
    run_from_main: bool = False
):
    result = dict()
    result['event-bucket-name'] = None
    result['event-key'] = None
    result['event-created-timestamp'] = None
    result['event-request-id'] = None
    result['request-id'] = None

    create_timestamp = get_utc_timestamp(with_decimal=False)

    return_object = {
        'statusCode': 200,
        'headers': {
            'content-type': 'application/json',
        },
        'body': json.dumps(result),
        'isBase64Encoded': False,
    }
    refresh_environment_cache(logger=logger)
    if cache['Environment']['Data']['DEBUG'] is True and run_from_main is False:
        logger = get_logger(level=logging.DEBUG)
    debug_log('event={}', variable_as_list=[event], logger=logger)

    # Process the request
    body_data = _extract_json_body_as_dict(event=event, logger=logger)
    employee_id = _extract_employee_id_from_path(event=event, logger=logger)
    if _validate_basic_request_data_is_valid(employee_id=employee_id, body_data=body_data, logger=logger) is False:
        return_object = {
            'statusCode': 400,
            'headers': {
                'content-type': 'text/plain',
            },
            'body': 'Bad Request',
            'isBase64Encoded': False,
        }
        logger.error('Failed basic employee ID validation - returning error 400 to client')
        return return_object



    if employee_id is not None:
        logger.info('Attempting to link card to employee ID {}'.format(employee_id))
        current_employee_access_card_record = get_employee_access_card_record(
            employee_id=employee_id,
            logger=logger
        )
    else:
        return_object = {
            'statusCode': 400,
            'headers': {
                'content-type': 'text/plain',
            },
            'body': 'Invalid Employee ID Syntax',
            'isBase64Encoded': False,
        }
        logger.error(
            'Failed basic employee ID validation - returning error 400 to client')
        return return_object

    return_object['body'] = json.dumps(result)
    debug_log('return_object={}', variable_as_list=[
              return_object, ], logger=logger)
    return return_object


###############################################################################
###                                                                         ###
###                        M A I N    F U N C T I O N                       ###
###                                                                         ###
###############################################################################


if __name__ == '__main__':
    logger = logging.getLogger("my_lambda")
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(funcName)s:%(lineno)d -  %(levelname)s - %(message)s')

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
    

    employee_id = '100000000150'
    card_id = '10000000099'
    event = {
        "version": "2.0",
        "routeKey": "POST /access-card-app/employee/{employeeId}/link-card",
        "rawPath": "/sandbox/access-card-app/employee/{}/link-card".format(employee_id),
        "rawQueryString": "",
        "headers": {
            "accept": "*/*",
            "authorization": "...",
            "content-length": "63",
            "content-type": "application/json",
            "host": "internal-api.example.tld",
            "user-agent": "curl/7.81.0",
            "x-amzn-trace-id": "...",
            "x-forwarded-for": "nnn.nnn.nnn.nnn",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https"
        },
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "5b5g16o1yc",
            "authorizer": {
                "jwt": {
                    "claims": {
                        "auth_time": "1665240605",
                        "client_id": "...",
                        "event_id": "...",
                        "exp": "1665244205",
                        "iat": "1665240605",
                        "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_...",
                        "jti": "....",
                        "origin_jti": "...",
                        "scope": "openid",
                        "sub": "943f64ad-6c94-4662-885c-83158d4c61da",
                        "token_use": "access",
                        "username": "user@example.tld",
                        "version": "2"
                    },
                    "scopes": None
                }
            },
            "domainName": "internal-api.example.tld",
            "domainPrefix": "internal-api",
            "http": {
                "method": "POST",
                "path": "/sandbox/access-card-app/employee/{}/link-card".format(employee_id),
                "protocol": "HTTP/1.1",
                "sourceIp": "nnn.nnn.nnn.nnn",
                "userAgent": "curl/7.81.0"
            },
            "requestId": "ZsNp0inLliAEPmg=",
            "routeKey": "POST /access-card-app/employee/<<employeeId>>/link-card",
            "stage": "sandbox",
            "time": "08/Oct/2022:14:57:28 +0000",
            "timeEpoch": 1665241048234
        },
        "pathParameters": {
            "employeeId": "100000000003"
        },
        "body": '{{"CardId": "{}", "CompleteOnboarding": false, "LinkedBy": "TEST"}}'.format(card_id),
        "isBase64Encoded": False
    }

    result1 = handler(event=event, context=None, logger=logger, run_from_main=True)
    print('------------------------------------------------------------------------------------------------------------------------')
    print('{}'.format(json.dumps(result1)))

