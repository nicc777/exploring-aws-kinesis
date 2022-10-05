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


def _extract_employee_id_from_path(event: dict) -> str:
    employee_id = None
    if 'rawPath' in event:
        # Expecting /access-card-app/employee/<<employee-id>>/access-card-status
        path_elements = event['rawPath'].split('/')
        if len(path_elements) != 5:
            logger.error('Path has wrong number of parts. Expected 5, but got {}'.format(
                len(path_elements)))
            return employee_id
        potential_employee_id = path_elements[3]
        logger.info('Integer range validation of id "{}"'.format(
            potential_employee_id))
        try:
            if int(potential_employee_id) > 100000000000 and int(potential_employee_id) < 999999999999:
                employee_id = '{}'.format(potential_employee_id)
            else:
                logger.error('Employee ID has invalid numeric range.')
        except:
            logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return employee_id


def handler(
    event,
    context,
    logger=get_logger(level=logging.INFO),
    boto3_clazz=boto3,
    run_from_main: bool = False
):
    result = dict()
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
    employee_id = _extract_employee_id_from_path(event=event)
    if employee_id is not None:
        logger.info('Requesting status for employee ID {}'.format(employee_id))
        result = get_employee_access_card_record(
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
    handler(event={}, context=None, logger=logger, run_from_main=True)
