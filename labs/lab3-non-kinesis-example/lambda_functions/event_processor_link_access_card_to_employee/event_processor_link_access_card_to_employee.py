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


def validate_campus(dirty_data: str, logger=get_logger())->bool:
    if dirty_data is None:
        logger.error('RequestId is None')
        return False
    if isinstance(dirty_data, str) is False:
        logger.error('RequestId is not a str')
        return False
    if len(dirty_data) < 3 or len(dirty_data) > 128:
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
        'Campus': validate_campus,
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


def process_permission_record_and_extract_permissions_if_current_at_the_time_of_event(permission_record: dict, event_timestamp: Decimal, logger=get_logger())->list:
    """
        permission_record={
            'PK'                    : 'EMP#100000000021',
            'SK'                    : 'PERSON#PERSONAL_DATA#PERMISSIONS#1666679226',
            'CardIdx'               : '100000000087',
            'CognitoSubjectId'      : 'bbba18b6-7c46-4652-a2a4-f7b014af42ce',
            'EndTimestamp'          : '-1',                                             # Decimal
            'ScannedBuildingIdx'    : '???',
            'StartTimestamp'        : '1234567890',                                     # Decimal
            'SystemPermissions'     : 'aa,bb,cc,...',
        }
    """
    permissions = list()
    debug_log(message='permission_record={}', variable_as_list=[permission_record,], logger=logger)
    debug_log(message='event_timestamp={}', variable_as_list=[event_timestamp,], logger=logger)
    try:
        record_is_active_at_time_of_event = False
        if permission_record['EndTimestamp'].compare(Decimal('-1')) == Decimal(0):
            # Still active permission - check StartTimestamp < event_timestamp
            logger.info('Processing still active permission. Ensuring permission start timestamp {} is before the event timestamp {}'.format(str(permission_record['StartTimestamp']), str(event_timestamp)))
            if permission_record['StartTimestamp'].compare(event_timestamp) == Decimal(-1):
                record_is_active_at_time_of_event = True
                logger.info('Found a valid permission in the event time range')
            else:
                logger.info('Found an invalid permission in the event time range')
        elif permission_record['EndTimestamp'].compare(Decimal('-1')) != Decimal(0):
            # No longer active permission - check StartTimestamp < event_timestamp AND EndTimestamp > event_timestamp
            logger.info('Processing now in-active permission. Ensuring permission start timestamp {} is before the event timestamp {} and the the end timestamp {} is after'.format(
                str(permission_record['StartTimestamp']), 
                str(event_timestamp)),
                str(permission_record['EndTimestamp'])
            )
            if permission_record['StartTimestamp'].compare(event_timestamp) == Decimal(-1) and permission_record['EndTimestamp'].compare(event_timestamp) == Decimal(1):
                record_is_active_at_time_of_event = True
                logger.info('Found a valid permission in the event time range')
            else:
                logger.info('Found an invalid permission in the event time range')
        if record_is_active_at_time_of_event is True:
            permissions = permission_record['SystemPermissions'].split(',')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return permissions

###############################################################################
###                                                                         ###
###                      A W S    I N T E G R A T I O N                     ###
###                                                                         ###
###############################################################################


def db_get_user_permissions_by_cognito_id(
    cognito_id: str,
    client=get_client(client_name='dynamodb', region='eu-central-1'),
    logger=get_logger(),
    next_token: dict=None
)->tuple:
    permissions = list()
    try:
        response = dict()
        if next_token is not None:
            response = client.query(
                TableName='lab3-access-card-app',
                IndexName='CognitoIdx',
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=False,
                KeyConditions={
                    'CognitoSubjectId': {
                        'AttributeValueList': [{'S': '{}'.format(cognito_id),},],
                        'ComparisonOperator': 'EQ'
                    },
                    'SK': {
                        'AttributeValueList': [
                            {'S': 'PERSON#PERSONAL_DATA#PERMISSIONS#',},],
                        'ComparisonOperator': 'BEGINS_WITH'
                    }
                },
                ExclusiveStartKey=next_token
            )
        else:
            response = client.query(
                TableName='lab3-access-card-app',
                IndexName='CognitoIdx',
                Select='ALL_ATTRIBUTES',
                Limit=10,
                ConsistentRead=False,
                KeyConditions={
                    'CognitoSubjectId': {
                        'AttributeValueList': [{'S': '{}'.format(cognito_id),},],
                        'ComparisonOperator': 'EQ'
                    },
                    'SK': {
                        'AttributeValueList': [
                            {'S': 'PERSON#PERSONAL_DATA#PERMISSIONS#',},],
                        'ComparisonOperator': 'BEGINS_WITH'
                    }
                }
            )

        logger.debug('response={}'.format(json.dumps(response, default=str)))
        if 'Items' in response:
            if len(response['Items']) > 0:
                for item in response['Items']:
                    record = dict()
                    for key, data in item.items():
                        for data_key, data_value in data.items():
                            if data_key.lower() == 's':
                                record[key] = data_value
                            if data_key.lower() == 'n':
                                record[key] = Decimal(data_value)
                            if data_key.lower() == 'bool':
                                record[key] = data_value
                    debug_log(message='record={}', variable_as_list=[record,], logger=logger)
                    permissions.append(record)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return tuple(permissions)


def get_card_issued_status(
    card_id: str,
    client=get_client(client_name='dynamodb', region='eu-central-1'),
    logger=get_logger()
)->dict:
    card_status_data = dict()
    try:
        logger.info('Retrieving card status from cognito for card {}'.format(card_id))
        response = client.query(
            TableName='lab3-access-card-app',
            IndexName='CardIssuedIdx',
            Select='ALL_ATTRIBUTES',
            Limit=1,
            ConsistentRead=False,
            KeyConditions={
                'CardIdx': {
                    'AttributeValueList': [{'S': '{}'.format(card_id),},],
                    'ComparisonOperator': 'EQ'
                },
                'SK': {
                    'AttributeValueList': [{'S': 'CARD#STATUS',},],
                    'ComparisonOperator': 'BEGINS_WITH'
                }
            }
        )
        logger.debug('response={}'.format(json.dumps(response, default=str)))
        for item in response['Items']:
            for key, data in item.items():
                for data_key, data_value in data.items():
                    if data_key.lower() == 's':
                        card_status_data[key] = data_value
                    if data_key.lower() == 'n':
                        card_status_data[key] = Decimal(data_value)
                    if data_key.lower() == 'bool':
                        card_status_data[key] = data_value
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log(message='card_status_data={}', variable_as_list=[card_status_data,], logger=logger)
    return card_status_data


def get_employee_profile(
    employee_id: str,
    client=get_client(client_name='dynamodb', region='eu-central-1'),
    logger=get_logger()
)->dict:
    employee_profile = dict()
    try:
        logger.info('Retrieving card status from cognito for card {}'.format(employee_id))
        response = client.query(
            TableName='lab3-access-card-app',
            Select='ALL_ATTRIBUTES',
            Limit=1,
            ConsistentRead=False,
            KeyConditions={
                'PK': {
                    'AttributeValueList': [{'S': 'EMP#{}'.format(employee_id),},],
                    'ComparisonOperator': 'EQ'
                },
                'SK': {
                    'AttributeValueList': [{'S': 'PERSON#PERSONAL_DATA',},],
                    'ComparisonOperator': 'BEGINS_WITH'
                }
            }
        )
        logger.debug('response={}'.format(json.dumps(response, default=str)))
        for item in response['Items']:
            for key, data in item.items():
                for data_key, data_value in data.items():
                    if data_key.lower() == 's':
                        employee_profile[key] = data_value
                    if data_key.lower() == 'n':
                        employee_profile[key] = Decimal(data_value)
                    if data_key.lower() == 'bool':
                        employee_profile[key] = data_value
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log(message='employee_profile={}', variable_as_list=[employee_profile,], logger=logger)
    return employee_profile


###############################################################################
###                                                                         ###
###                         M A I N    H A N D L E R                        ###
###                                                                         ###
###############################################################################


def user_has_permissions(event_data: dict, event_timestamp: Decimal, logger:get_logger())->bool:
    user_permission_records = db_get_user_permissions_by_cognito_id(
        cognito_id=event_data['LinkedBy']['CognitoId'],
        logger=logger
    )
    debug_log(message='user_permission_records={}', variable_as_list=[user_permission_records,], logger=logger)
    final_active_permissions = list()
    for permission_record in user_permission_records:
        active_permissions_from_record = process_permission_record_and_extract_permissions_if_current_at_the_time_of_event(permission_record=permission_record, event_timestamp=event_timestamp, logger=logger)
        for active_permission in active_permissions_from_record:
            if active_permission not in final_active_permissions:
                final_active_permissions.append(active_permission)
    logger.info('Final active permissions at the time of event: {}'.format(final_active_permissions))
    for required_permission in REQUIRED_PERMISSIONS:
        if required_permission in final_active_permissions:
            return True
    return False


def card_is_in_correct_state(
    event_data: dict,
    logger=get_logger()
)->bool:
    card_state = dict()
    try:
        card_state = get_card_issued_status(
            card_id=event_data['CardId'],
            logger=logger
        )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    if 'IsAvailableForIssue' in card_state:
        logger.info('Card status: {}'.format(card_state['IsAvailableForIssue']))
        if isinstance(card_state['IsAvailableForIssue'], bool):
            return card_state['IsAvailableForIssue']
    logger.warning('Unable to determine card status - assuming not available for issue')
    return False


def employee_is_in_correct_state(
    event_data: dict,
    logger=get_logger()
)->str:
    employee_profile = dict()
    try:
        employee_profile = get_employee_profile(
            employee_id=event_data['EmployeeId'],
            logger=logger
        )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    if 'PersonStatus' in employee_profile:
        logger.info('Employee status: {}'.format(employee_profile['PersonStatus']))
        if isinstance(employee_profile['PersonStatus'], str):
            if employee_profile['PersonStatus'] in ('onboarding', 'active'):
                return employee_profile['PersonStatus']
    logger.warning('Unable to determine employee status - assuming not active or onboarding')
    return 'inactive'


def process_event_record_body(event_data: dict, logger=get_logger()):
    """
        Example event_data dict:

            {
                "EmployeeId": "100000000103", 
                "CardId": "100000000139", 
                "CompleteOnboarding": true, 
                "LinkedBy": {
                    "Username": "some_user@example.tld", 
                    "CognitoId": "fe8c1444-8404-4365-bf70-0c4d30313c8d"
                }, 
                "LinkedTimestamp": 1667369409, 
                "RequestId": "c85c616418716a95c81c14d7c033cba157694129c86f9e188668b210f14023b9", 
                "Campus": "campus03"
            }
    """
    logger.info('Processing event_data={}'.format(event_data))

    # 1) Validate message structure
    if validate_record_structure_and_data(event_data=event_data, logger=logger) is False:
        logger.error('Record validation failed. Not processing the record any further.')
        return
    else:
        logger.info('Validation passed')
    event_timestamp = Decimal(event_data['LinkedTimestamp'])

    # 2) Ensure the LinkedBy identity has sufficient permissions for this actions
    if user_has_permissions(event_data=event_data, event_timestamp=event_timestamp, logger=logger) is False:
        logger.error('Linking user did not have the required permissions at the time of event')
        return
    logger.info('Permission test passed')

    # 3) Ensure card is currently in the correct state
    if card_is_in_correct_state(event_data=event_data, logger=logger) is False:
        logger.error('Card is not available for issue')
        return
    logger.info('Card status test passed')

    # 4) Ensure person is currently in correct state
    employee_current_status = employee_is_in_correct_state(
        event_data=event_data,
        logger=logger
    )
    if employee_current_status == 'inactive':
        logger.error('Employee is in-active - can not link card')
        return
    logger.info('Employee status test passed')

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


TEST_EVENTS = {
    'BasicTest01': {
        'Records': [
            {
                'messageId': 'a6c2cb8a-3bf0-4257-8786-49c684d3040e', 
                'receiptHandle': 'abc', 
                'body': '{"EmployeeId": "100000000104", "CardId": "100000000139", "CompleteOnboarding": true, "LinkedBy": {"Username": "nicc777@gmail.com", "CognitoId": "fe8c1444-8404-4365-bf70-0c4d30313c8d"}, "LinkedTimestamp": 1667367563, "RequestId": "04e0ea3a3ffef1f6c242a284166e707aae2dd573387718e188a32c0f57483f2f", "Campus": "campus02"}',  
                'attributes': {
                    'ApproximateReceiveCount': '1', 
                    'SentTimestamp': '1667297326109', 
                    'SenderId': 'abc', 
                    'ApproximateFirstReceiveTimestamp': '1667297326119'
                }, 
                'messageAttributes': {
                    'EventType': {
                        'stringValue': 'LinkAccessCardToEmployee', 
                        'stringListValues': [], 
                        'binaryListValues': [], 
                        'dataType': 'String'
                    }
                }, 
                'md5OfMessageAttributes': 'cc3477bbe92dc4262d5566531ab0ac7e', 
                'md5OfBody': '36fde7ecbfcc4c2ab12953d44d8319cc', 
                'eventSource': 'aws:sqs', 
                'eventSourceARN': 'arn:aws:sqs:eu-central-1:012345678901:LinkAccessCardEvent', 
                'awsRegion': 'eu-central-1'
            }
        ]
    }
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
    handler(event=TEST_EVENTS['BasicTest01'], context=None, logger=logger, run_from_main=True)
