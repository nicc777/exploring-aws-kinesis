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
    formatter = logging.Formatter('%(funcName)s:%(lineno)d -  %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)    
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(level)
    return logger


def read_config(file_path: str="events.json", logger=get_logger())->dict:
    config = dict()
    try:
        with open(file_path, "r") as f:
            config = json.loads(f.read())
            logger.debug('config from file: {}'.format(config))
    except:
        logger.error("EXCEPTION: {}".format(traceback.format_exc()))
    return config


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


def refresh_environment_cache(config_file_path: str="events.json", logger=get_logger()):
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
            'CONFIG': read_config(file_path=config_file_path, logger=logger)
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
    s3_key_version_id: str,
    client=get_client(client_name="s3"), 
    logger=get_logger()
)->str:
    key_json_data = ''
    try:
        response = client.get_object(
            Bucket=s3_bucket,
            Key=s3_key,
            VersionId=s3_key_version_id
        )
        logger.debug('response={}'.format(response))
        if 'Body' in response:
            key_json_data = response['Body'].read().decode('utf-8')
            logger.debug('body={}'.format(key_json_data))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return key_json_data


def publish_event_to_sns(
    topic_name: str,
    data: str,
    event_type: str,
    aws_account_id: str='000000000000',
    client=get_client(client_name="sns"), 
    logger=get_logger()
):
    try:
        
        response = client.publish(
            TopicArn='arn:aws:sns:{}:{}:{}'.format(os.getenv('AWS_REGION'), aws_account_id, topic_name),
            Message='{}'.format(data),
            Subject='S3PutEvent',
            MessageStructure='string',
            MessageAttributes={
                'EventType': {
                    'DataType': 'String',
                    'StringValue': '{}'.format(event_type)
                }
            }
        )
        debug_log(message='response={}', variable_as_list=[response,], logger=logger)
        logger.info('SNS Message for event type "{}" sent. MessageId={}'.format(event_type, response['MessageId']))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


###############################################################################
###                                                                         ###
###                        P R O C E S S    E V E N T                       ###
###                                                                         ###
###############################################################################


def get_routable_event(s3_key: str, config: dict, logger=get_logger())->dict:
    routable_event = dict()
    routable_event['MatchingEvent'] = False
    routable_event['RoutingData'] = dict()
    routable_event['EventType'] = ''
    matching_event = True
    matching_attributes = dict()
    for event_type, event_process_data in config.items():
        if 'S3KeyAttributes' in event_process_data and 'Routing' in event_process_data:
            if 'StartsWith' in event_process_data['S3KeyAttributes']:
                matching_attributes['S3KeyAttributes_StartsWith'] = False
                if s3_key.startswith(event_process_data['S3KeyAttributes']['StartsWith']) is True:
                    matching_attributes['S3KeyAttributes_StartsWith'] = True
        if 'Extension' in event_process_data['S3KeyAttributes']:
                matching_attributes['S3KeyAttributes_Extension'] = False
                if s3_key.endswith('.{}'.format(event_process_data['S3KeyAttributes']['Extension'])) is True:
                    matching_attributes['S3KeyAttributes_Extension'] = True
        for att_name, att_matched in matching_attributes.items():
            logger.info('Key "{}" matching: {} --> {}'.format(s3_key, att_name, att_matched))
            if att_matched is False:
                matching_event = False
        if matching_event is True:
            routable_event['MatchingEvent'] = True
            routable_event['RoutingData'] = event_process_data['Routing']
            routable_event['EventType'] = event_type
            break
    debug_log(message='routable_event={}', variable_as_list=[routable_event,], logger=logger)
    return routable_event



def process_s3_record(s3_record: dict, config: dict, logger=get_logger(), aws_account_id: str='000000000000'):
    logger.info('Processing S3 Record: {}'.format(s3_record))
    try:
        if 'object' in s3_record:
            if 'size' in s3_record['object']:
                if int(s3_record['object']['size']) < 10240:
                    routable_event = get_routable_event(s3_key=s3_record['object']['key'], config=config, logger=logger)
                    if routable_event['MatchingEvent'] is True:
                        json_data = get_s3_object_payload(
                            s3_bucket=s3_record['bucket']['name'],
                            s3_key=s3_record['object']['key'],
                            s3_key_version_id=s3_record['object']['versionId'],
                            logger=logger
                        )
                        if len(json_data) > 0 and len(json_data) < 10240:
                            logger.info('Event "{}" data loaded. Routing Data: {}'.format(routable_event['EventType'], routable_event['RoutingData']))
                            publish_event_to_sns(
                                topic_name=routable_event['RoutingData']['SnsTopic']['Name'],
                                data=json_data,
                                event_type=routable_event['EventType'],
                                aws_account_id=aws_account_id,
                                logger=get_logger()
                            )
                        else:
                            logger.info('Event Data Loaded, but not routing further due to length constraint validation failure')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def process_message(message: dict, config: dict, logger=get_logger(), aws_account_id: str='000000000000'):
    logger.info('Processing Message: {}'.format(message))
    if 'Records' in message:
        if isinstance(message['Records'], list):
            for record in message['Records']:
                if 'eventSource' in record and 'eventName' in record:
                    event_name = record['eventName']
                    event_source = record['eventSource']
                    logger.info('Received "{}" event from "{}"'.format(event_name, event_source))
                    if event_source == 'aws:s3' and event_name == 'ObjectCreated:Put' and 's3' in record:
                        logger.info('Processing S3 PUT Event')
                        process_s3_record(s3_record=record['s3'], config=config, logger=logger, aws_account_id=aws_account_id)
                    else:
                        logger.info('Ignoring Event')


def process_body(body: dict, config: dict, logger=get_logger(), aws_account_id: str='000000000000'):
    logger.info('Processing Body: {}'.format(body))
    if 'Message' in body:
        try:
            process_message(message=json.loads(body['Message']), config=config, logger=logger, aws_account_id=aws_account_id)
        except:
            logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def body_fix_up(body: str, logger=get_logger())->dict:
    result = dict()
    try:
        lines = body.split('\n')
        raw_msg_line = lines[5]
        raw_msg_line = raw_msg_line.replace(' ', '')
        json_str = raw_msg_line[11:-2]
        result = json.loads(json_str)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    return result


def process_event_record(event_record: dict, config: dict, logger=get_logger(), aws_account_id: str='000000000000'):
    body = dict()
    if 'body' in event_record:
        try:
            body = json.loads(event_record['body'])
        except:
            logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
            body = body_fix_up(body=event_record['body'], logger=logger)
    if len(body) > 0:
        process_body(body=body, config=config, logger=logger, aws_account_id=aws_account_id)


def process_event(event: dict, config: dict, logger=get_logger(), aws_account_id: str='000000000000'):
    if 'Records' in event:
        if isinstance(event['Records'], list):
            for record in event['Records']:
                process_event_record(event_record=record, config=config, logger=logger, aws_account_id=aws_account_id)


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
    config_file_path: str="events.json"
):
    refresh_environment_cache(config_file_path=config_file_path, logger=logger)
    if cache['Environment']['Data']['DEBUG'] is True and run_from_main is False:
        logger  = get_logger(level=logging.DEBUG)
    config = cache['Environment']['Data']['CONFIG']
    logger.info('config={}'.format(config))
    
    aws_account_id = context.invoked_function_arn.split(':')[4]

    debug_log('event={}', variable_as_list=[event], logger=logger)
    process_event(event=event, config=config, logger=logger, aws_account_id=aws_account_id)
    
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