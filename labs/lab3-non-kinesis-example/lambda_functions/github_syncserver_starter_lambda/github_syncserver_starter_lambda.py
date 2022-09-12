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
import boto3


SUPPORTED_REPOSITORIES = tuple(os.getenv('SUPPORTED_REPOSITORIES', 'nothing').replace(' ', '').split(','))
SUPPORTED_SENDER_LOGINS = tuple(os.getenv('GITHUB_AUTHORIZED_SENDERS', 'nothing').replace(' ', '').split(','))


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


def is_github_sync_server_running(ec2_instances: list)->bool:
    debug_log('ec2_instances={}', variable_as_list=[ec2_instances,], logger=logger)
    for record in ec2_instances:
        if 'Tags' in record:
            if 'aws:ec2launchtemplate:id' in record['Tags']:
                if record['Tags']['aws:ec2launchtemplate:id'] == os.getenv('LAUNCH_TEMPLATE_ID'):
                    logger.info('FOUND RUNNING INSTANCE: instance id "{}"'.format(record['InstanceId']))
                    return True
                else:
                    logger.info('Instance id "{}" is not a type of GitHub Sync Server'.format(record['InstanceId']))
    return False


###############################################################################
###                                                                         ###
###                 A W S    A P I    I N T E G R A T I O N                 ###
###                                                                         ###
###############################################################################


def get_sqs_queue_size(
    logger=get_logger(),
    boto3_clazz=boto3
)->int:
    client = get_client(client_name='sqs', boto3_clazz=boto3_clazz)
    result = 0
    try:    
        response = client.get_queue_attributes(
            QueueUrl=os.getenv('SQS_URL'),
            AttributeNames=[
                'ApproximateNumberOfMessages',
            ]
        )
        debug_log('response={}', variable_as_list=[json.dumps(response, default=str),], logger=logger)
        if 'Attributes' in response:
            debug_log('Attributes: {}', variable_as_list=[response['Attributes'],], logger=logger)
            if 'ApproximateNumberOfMessages' in response['Attributes']:
                result = int(response['Attributes']['ApproximateNumberOfMessages'])
                logger.info('result set to: {}'.format(result))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log('result={}', variable_as_list=[result,], logger=logger)
    return result


def get_running_ec2_instances(
    logger=get_logger(),
    boto3_clazz=boto3,
    next_token: str=None
)->list:
    result = list()
    client = get_client(client_name='ec2', boto3_clazz=boto3_clazz)
    logger.debug('get_running_ec2_instances() called')
    try:
        response = dict()
        if next_token is not None:
            response = client.describe_instances(NextToken=next_token)
        else:
            response = client.describe_instances()
        debug_log('response={}', variable_as_list=[json.dumps(response, default=str),], logger=logger)
        
        for r in response['Reservations']:
            for instance in r['Instances']:
                record = dict()
                if instance['State']['Name'] in ('running', 'pending',):
                    record['InstanceId'] = instance['InstanceId']
                    record['State'] = instance['State']['Name']
                    record['Tags'] = dict()
                    for tag in instance['Tags']:
                        record['Tags'][tag['Key']] = tag['Value']
                    result.append(record)
        logger.info('Running instances qty: {}'.format(len(result)))

        if 'NextToken' in response:
            result += get_running_ec2_instances(
                logger=logger,
                boto3_clazz=boto3_clazz,
                next_token=response['NextToken']
            )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    debug_log('result={}', variable_as_list=[result,], logger=logger)
    return result


def get_launch_template_versions(
    logger=get_logger(),
    boto3_clazz=boto3,
    next_token: str=None
)->list:
    result = list()
    client = get_client(client_name='ec2', boto3_clazz=boto3_clazz)
    try:    
        response = dict()
        if next_token is not None:
            response = client.describe_launch_template_versions(
                LaunchTemplateId=os.getenv('LAUNCH_TEMPLATE_ID'),
                NextToken=next_token
            )
        else:
            response = client.describe_launch_template_versions(
                LaunchTemplateId=os.getenv('LAUNCH_TEMPLATE_ID')
            )
        debug_log('response={}', variable_as_list=[json.dumps(response, default=str),], logger=logger)
        for lt in response['LaunchTemplateVersions']:
            result.append(int(lt['VersionNumber']))
        if 'NextToken' in response:
            result += get_launch_template_versions(
                logger=logger,
                boto3_clazz=boto3_clazz,
                next_token=response['NextToken']
            )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    result.sort()
    debug_log('result={}', variable_as_list=[result,], logger=logger)
    return result


def start_sync_server_instance(
    logger=get_logger(),
    boto3_clazz=boto3
):
    result = list()
    client = get_client(client_name='ec2', boto3_clazz=boto3_clazz)
    try:
        latest_version = get_launch_template_versions(logger=logger, boto3_clazz=boto3_clazz)[-1]
        logger.info('Launch Template Latest Version: {}'.format(latest_version))
        pass
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


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
    
    
    # Get current SQS message count
    sqs_queue_size = get_sqs_queue_size(logger=logger, boto3_clazz=boto3_clazz)

    # If count > 0, get the current running EC2 instances
    if sqs_queue_size > 0:

        # Is sync server running?
        sync_server_running = is_github_sync_server_running(
            ec2_instances=get_running_ec2_instances(logger=logger, boto3_clazz=boto3_clazz)
        )
        logger.info('sync_server_running={}'.format(sync_server_running))

        # If sync server is not running, start a new sync server instance
        if sync_server_running is False:
            logger.info('Attempting to start the Github Sync Server')
            start_sync_server_instance(logger=logger, boto3_clazz=boto3_clazz)
        else:
            logger.info('Github Sync Server appears to be running already')

    else:
        logger.info('No messages')

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



