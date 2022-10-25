import boto3
import traceback
import os
import json
import logging
from datetime import datetime
import sys
from inspect import getframeinfo, stack
# Other imports here...


# Required user permissions for this function. The "LinkedBy" user must have any one of the permissions listed here
REQUIRED_PERMISSIONS = ('admin', 'link_access_card_to_employee')


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
###                 V A L I D A T I O N    F U N C T I O N S                ###
###                                                                         ###
###############################################################################


def validate_employee_id(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('EmployeeId is None')
        return False
    if isinstance(dirty_data, str) is False:
        logger.error('EmployeeId is not a str')
        return False
    try:                                                        
        if int(dirty_data) < 10000000000 or int(dirty_data) > 99999999999:
            logger.error('EmployeeId is out of numerical range')
            return False
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return True


def validate_card_id(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('CardId is None')
        return False
    if isinstance(dirty_data, str) is False:
        logger.error('CardId is not a str')
        return False
    try:                                                        
        if int(dirty_data) < 10000000000 or int(dirty_data) > 99999999999:
            logger.error('CardId is out of numerical range')
            return False
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return True


def validate_complete_onboarding(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('CompleteOnboarding is None')
        return False
    if isinstance(dirty_data, bool) is False:
        logger.error('CompleteOnboarding is not a bool')
        return False
    return True


def validate_linked_by(dirty_data: dict, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('LinkedBy is None')
        return False
    if isinstance(dirty_data, dict) is False:
        logger.error('LinkedBy is not a str')
        return False
    try:                                                        
        if 'Username' not in dirty_data or 'CognitoId' not in dirty_data:
            logger.error('LinkedBy does not contain expected keys Username and/or CognitoId')
            return False

        if dirty_data['Username'] is None:
            logger.error('LinkedBy Username is None')
            return False
        if isinstance(dirty_data['Username'], str) is False:
            logger.error('LinkedBy Username must be a str')
            return False
        if len(dirty_data['Username']) < 12 or len(dirty_data['Username']) > 128:
            logger.error('LinkedBy Username invalid length')
            return False

        if dirty_data['CognitoId'] is None:
            logger.error('LinkedBy CognitoId is None')
            return False
        if isinstance(dirty_data['CognitoId'], str) is False:
            logger.error('LinkedBy CognitoId must be a str')
            return False
        if len(dirty_data['CognitoId']) < 12 or len(dirty_data['CognitoId']) > 128:
            logger.error('LinkedBy CognitoId invalid length')
            return False
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return True


def validate_linked_timestamp(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('LinkedTimestamp is None')
        return False
    if isinstance(dirty_data, int) is False:
        logger.error('LinkedTimestamp is not a bool')
        return False
    if dirty_data < 0:
        logger.error('LinkedTimestamp is not a positive integer')
        return False
    return True


def validate_request_id(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('RequestId is None')
        return False
    if isinstance(dirty_data, str) is False:
        logger.error('RequestId is not a str')
        return False
    if len(dirty_data) < 10 or len(dirty_data) > 256:
        logger.error('RequestId invalid length')
        return False
    return True


def validate_record_structure_and_data(event_data: dict, logger=get_logger())->bool:
    FIELD_VALIDATOR_FUNCTIONS = {
        'EmployeeId': validate_employee_id, 
        'CardId': validate_card_id, 
        'CompleteOnboarding': validate_complete_onboarding, 
        'LinkedBy': validate_linked_by, 
        'LinkedTimestamp': validate_linked_timestamp,  
        'RequestId': validate_request_id,
    }
    if event_data is None:
        logger.error('event_data is None')
        return False
    if isinstance(event_data, dict) is False:
        logger.error('event_data is not a dict')
        return False
    for key in ( 'EmployeeId', 'CardId', 'CompleteOnboarding', 'LinkedBy', 'LinkedTimestamp', 'RequestId'):
        if key not in event_data:
            logger.error('Expected key "{}" was not present'.format(key))
            if FIELD_VALIDATOR_FUNCTIONS[key](dirty_data=event_data[key], logger=logger) is False:
                return False
    return True


###############################################################################
###                                                                         ###
###                      A W S    I N T E G R A T I O N                     ###
###                                                                         ###
###############################################################################


def db_get_user_permissions_by_cognito_id(
    cognito_id: str,
    client=get_client(client_name='dynamodb', region='eu-central-1'),
    logger=get_logger()
)->tuple:
    permissions = list()
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

        response = client.scan(
            TableName='string',
            IndexName='string',
            AttributesToGet=[
                'string',
            ],
            Limit=123,
            Select='ALL_ATTRIBUTES'|'ALL_PROJECTED_ATTRIBUTES'|'SPECIFIC_ATTRIBUTES'|'COUNT',
            ScanFilter={
                'string': {
                    'AttributeValueList': [
                        {
                            'S': 'string',
                            'N': 'string',
                            'B': b'bytes',
                            'SS': [
                                'string',
                            ],
                            'NS': [
                                'string',
                            ],
                            'BS': [
                                b'bytes',
                            ],
                            'M': {
                                'string': {'... recursive ...'}
                            },
                            'L': [
                                {'... recursive ...'},
                            ],
                            'NULL': True|False,
                            'BOOL': True|False
                        },
                    ],
                    'ComparisonOperator': 'EQ'|'NE'|'IN'|'LE'|'LT'|'GE'|'GT'|'BETWEEN'|'NOT_NULL'|'NULL'|'CONTAINS'|'NOT_CONTAINS'|'BEGINS_WITH'
                }
            },
            ConditionalOperator='AND'|'OR',
            ExclusiveStartKey={
                'string': {
                    'S': 'string',
                    'N': 'string',
                    'B': b'bytes',
                    'SS': [
                        'string',
                    ],
                    'NS': [
                        'string',
                    ],
                    'BS': [
                        b'bytes',
                    ],
                    'M': {
                        'string': {'... recursive ...'}
                    },
                    'L': [
                        {'... recursive ...'},
                    ],
                    'NULL': True|False,
                    'BOOL': True|False
                }
            },
            ReturnConsumedCapacity='INDEXES'|'TOTAL'|'NONE',
            TotalSegments=123,
            Segment=123,
            ProjectionExpression='string',
            FilterExpression='string',
            ExpressionAttributeNames={
                'string': 'string'
            },
            ExpressionAttributeValues={
                'string': {
                    'S': 'string',
                    'N': 'string',
                    'B': b'bytes',
                    'SS': [
                        'string',
                    ],
                    'NS': [
                        'string',
                    ],
                    'BS': [
                        b'bytes',
                    ],
                    'M': {
                        'string': {'... recursive ...'}
                    },
                    'L': [
                        {'... recursive ...'},
                    ],
                    'NULL': True|False,
                    'BOOL': True|False
                }
            },
            ConsistentRead=True|False
        )

        logger.debug('response={}'.format(json.dumps(response, default=str)))
        if 'Items' in response:
            if len(response['Items']) > 0:
                for item in response['Items']:
                    pass
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return tuple(permissions)


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


def user_has_permissions(event_data: dict, logger:get_logger())->bool:
    user_permissions = db_get_user_permissions_by_cognito_id(
        cognito_id=event_data['LinkedBy']['CognitoId'],
        logger=logger
    )
    permission_match = False
    for p in user_permissions:
        if p in REQUIRED_PERMISSIONS:
            permission_match = True
    if permission_match is False:
        logger.error('User {} does not have permission to link access cards'.format(event_data['LinkedBy']['Username']))
        return False
    return True


def process_event_record_body(event_data: dict, logger=get_logger()):
    """
        Example event_data dict:

            {
                "EmployeeId": "10000000103",
                "CardId": "10000000189",
                "CompleteOnboarding": false,
                "LinkedBy": {
                    "Username": "username@example.tld",
                    "CognitoId": "aa77e5bd-244c-4120-b0d0-85b059b5003f"
                },
                "LinkedTimestamp": 1665834703,
                "RequestId": "20837024a2a1a0375c23c3fc427e912ac9c3bd8239d939e0dec4b836633f9eba"
            }
    """
    logger.info('Processing event_data={}'.format(event_data))

    # 1) Validate message structure
    if validate_record_structure_and_data(event_data=event_data, logger=logger) is False:
        logger.error('Record validation failed. Not processing the record any further.')
        return
    else:
        logger.info('Validation passed')

    # 2) Ensure the LinkedBy identity has sufficient permissions for this actions
    if user_has_permissions(event_data=event_data, logger=logger) is False:
        return

    # 3) Ensure card is currently in the correct state

    # 4) Ensure person is currently in correct state

    # 5) DynamoDB - Upsert employee record

    # 6) DynamoDB - Upsert card record ( SK => CARD#STATUS#issued )

    # 7) DynamoDB - Upsert event audit record ( SK => CARD#EVENT )

    # TODO complete


def extract_event_record(event_record: str, logger=get_logger())->dict:
    try:        
        event_data = json.loads(event_record['body'])
        debug_log(message='event_data={}', variable_as_list=[event_data,], logger=logger)
        return event_data
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return None


def process_events(event: dict, logger=get_logger()):
    if event is None:
        logger.error('event was None')
        return
    if isinstance(event, dict) is False:
        logger.error('event expected to be a dict but was {}'.format(type(event)))
        return
    try:
        for event_record in event['Records']:
            logger.info('Processing event_record={}'.format(event_record))
            event_data = extract_event_record(event_record=event_record, logger=logger)
            if event_data is not None:
                process_event_record_body(event_data=event_data, logger=logger)
            else:
                logger.error('event_data was None - cannot process this record')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))

    
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

    process_events(event=event, logger=logger)
    
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