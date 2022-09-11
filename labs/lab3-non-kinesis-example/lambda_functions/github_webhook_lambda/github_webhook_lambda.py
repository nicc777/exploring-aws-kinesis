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


def validate_valid_github_webhook_request(event, logger=get_logger())->bool:
    
    if 'x-github-delivery' not in event['headers']:
        logger.error('Expected header x-github-delivery')
        return False
    if 'x-github-hook-installation-target-id' not in event['headers']:
        logger.error('Expected header x-github-hook-installation-target-id')
        return False
    if 'x-github-hook-id' not in event['headers']:
        logger.error('Expected header x-github-hook-id')
        return False
    if 'x-github-hook-installation-target-type' not in event['headers']:
        logger.error('Expected header x-github-hook-installation-target-type')
        return False
    
    if event['headers']['x-github-hook-id'] != 'repository':
        logger.error('Expected header x-github-hook-installation-target-type value to be "repository"')
        return False
    
    if event['requestContext']['http']['userAgent'].startswith('GitHub-Hookshot/') is False:
        logger.error('Expected a GitHub user-agent')
        return False
    
    return True


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


def validate_github_data(data: dict, logger=get_logger())->bool:

    if 'action' not in data:
        logger.error('Expected "action" key')
        return False

    if data['action'] not in ("prereleased", "created"):
        logger.error('Only pre-released or created actions are supported at the moment')
        return False

    if data['release']['author']['login'] not in SUPPORTED_SENDER_LOGINS:
        logger.error('Only pre-released or created actions are supported at the moment')
        return False

    if data['repository']['full_name'] not in SUPPORTED_REPOSITORIES:
        logger.error('Repository full name not in SUPPORTED_REPOSITORIES')
        return False

    if data['sender']['login'] not in SUPPORTED_SENDER_LOGINS:
        logger.error('Invalid sender login')
        return False

    return True


###############################################################################
###                                                                         ###
###                 A W S    A P I    I N T E G R A T I O N                 ###
###                                                                         ###
###############################################################################


def post_sqs(
    data: dict,
    logger=get_logger(),
    boto3_clazz=boto3
):
    client = get_client(client_name='sqs', boto3_clazz=boto3_clazz)
    try:    
        response = client.send_message(
            QueueUrl=os.getenv('SQS_URL'),
            MessageBody=json.dumps(data)
        )
        logger.info('response={}'.format(response))
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
    
    if not validate_valid_github_webhook_request(event=event, logger=logger):
        logger.error('Invalid Request')
        debug_log('return_object={}', variable_as_list=[return_object,], logger=logger)
        return return_object

    github_data = decode_data(event=event, body=extract_post_data(event=event))
    if validate_github_data(data=github_data, logger=logger) is False:
        logger.error('Invalid Request Body Data')
        debug_log('return_object={}', variable_as_list=[return_object,], logger=logger)
        return return_object

    sqs_data = dict()
    sqs_data['repository'] = github_data['repository']['full_name']
    sqs_data['tag_name'] = github_data['release']['tag_name']
    sqs_data['tar_file'] = github_data['release']['tarball_url']

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



