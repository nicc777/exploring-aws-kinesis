import logging
import logging.handlers
import time
from datetime import datetime
import logging.handlers
import boto3
import json
import traceback
import os
import requests
import random
import string
import tarfile
import subprocess
import shlex


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
ch = logging.handlers.TimedRotatingFileHandler('/data/logs/github_sync.log', when='midnight', interval=1, backupCount=0, encoding=None, delay=False, utc=True)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s:%(lineno)d - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.info('Logging Configured')
logger.debug('Debug Enabled')


#######################################################################################################################
###                                                                                                                 ###
###                                        G E N E R A L    F U N C T I O N S                                       ###
###                                                                                                                 ###
#######################################################################################################################


def get_utc_timestamp(with_decimal: bool=False): # pragma: no cover
    epoch = datetime(1970,1,1,0,0,0) 
    now = datetime.utcnow() 
    timestamp = (now - epoch).total_seconds() 
    if with_decimal: 
        return timestamp 
    return int(timestamp) 


def get_client(client_name: str, region: str='eu-central-1', boto3_clazz=boto3):
    return boto3_clazz.client(client_name, region_name=region)


def get_sqs_url()->str:
    url = None
    with open('/tmp/sqs_url', 'r') as f:
        url = f.read()
        url = url.splitlines()[0]
        logger.info('SQS URL: "{}"'.format(url))
    return url


def get_instance_id()->str:
    instance_id = None
    with open('/tmp/instance-id', 'r') as f:
        instance_id = f.read()
        instance_id = instance_id.splitlines()[0]
        logger.info('Instance ID: "{}"'.format(instance_id))
    return instance_id


def get_global_environment()->dict:
    environment = dict()
    environment['GITHUB_WORKDIR'] = '/tmp'
    environment['DEPLOYMENT_TARGET_DIR'] = '/tmp'
    try:
        with open('/etc/environment', 'r') as f:
            for line in f:
                line.splitlines()[0]
                values = line.split('=')
                if len(values) > 1:
                    environment[values[0]] = '='.join(values[1:]).replace('\n', '')
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    logger.debug('environment={}'.format(environment))
    return environment


def get_proxies()->list:
    proxies = list()
    try:
        with open('/etc/profile', 'r') as f:
            for line in f:
                line.splitlines()[0]
                values = line.split('=')
                if len(values) > 1:
                    if 'http_proxy' in values[0] or 'https_proxy' in values[0]:
                        proxy_addr = '='.join(values[1:]).replace('\n', '')
                        proxy_addr = proxy_addr.replace('"', '')
                        proxy_addr = proxy_addr.replace(' ', '')
                        if proxy_addr not in proxies:
                            proxies.append(proxy_addr)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    logger.debug('proxies={}'.format(proxies))
    return proxies


def randStr(chars = string.ascii_lowercase + string.digits, N=10):
    # Used implementation from https://pythonexamples.org/python-generate-random-string-of-specific-length/
	return ''.join(random.choice(chars) for _ in range(N))


def download_file(
    url:str,
    target_dir: str
)->str:
    output_file = '{}/download-{}-{}.tar.gz'.format(
        target_dir,
        get_utc_timestamp(with_decimal=False),
        randStr(N=8)
    )
    try:

        proxies = dict()
        for proxy_server in get_proxies():
            proxies['http'] = proxy_server
            proxies['https'] = proxy_server

        req = None
        if len(proxies) > 0:
            req = requests.get(url, stream=True, proxies=proxies)
        else:
            req = requests.get(url, stream=True)
        with open(output_file,'wb') as f:
            for current_chunk in req.iter_content(chunk_size=1024):
                if current_chunk:
                    f.write(current_chunk)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        output_file = None
    logger.debug('output_file={}'.format(output_file))
    return output_file


def untar_file(file: str, work_dir: str='/tmp')->str:
    # Based on examples from https://www.geeksforgeeks.org/how-to-uncompress-a-tar-gz-file-using-python/
    target_dir = '{}/untarred-{}-{}'.format(
        work_dir,
        get_utc_timestamp(with_decimal=False),
        randStr(N=8)
    )
    try:
        file = tarfile.open(file)
        # print(file.getnames())
        file.extractall(target_dir)
        file.close()
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
        target_dir = None
    logger.debug('target_dir={}'.format(target_dir))
    return target_dir


def rm_file(file: str):
    try:
        os.remove(file) 
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def append_line_to_file(file: str, line: str):
    try:
        with open(file, 'a') as f:
            f.write('{}\n'.format(line))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


#######################################################################################################################
###                                                                                                                 ###
###                                            A W S    F U N C T I O N S                                           ###
###                                                                                                                 ###
#######################################################################################################################


def receive_messages(sqs_url: str)->list:
    messages = list()
    try:
        client = get_client(client_name='sqs')
        response = client.receive_message(
            QueueUrl=sqs_url,
            AttributeNames=[
                'All',
            ],
            MaxNumberOfMessages=10,
            VisibilityTimeout=600,
            WaitTimeSeconds=10
        )
        logger.debug('response={}'.format(json.dumps(response, default=str)))
        for message in response['Messages']:
            logger.debug('message={}'.format(json.dumps(message, default=str)))
            receipt_handle = message['ReceiptHandle']
            messages.append(message)
            logger.info('Deleting message "{}"'.format(receipt_handle))
            client.delete_message(
                QueueUrl=sqs_url,
                ReceiptHandle=receipt_handle
            )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    logger.debug('messages={}'.format(json.dumps(messages, default=str)))
    return messages


def terminate_self():
    try:
        client = get_client(client_name='ec2')
        client.terminate_instances(
            InstanceIds=[
                get_instance_id(),
            ]
        )
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


#######################################################################################################################
###                                                                                                                 ###
###                                            M A I N    F U N C T I O N S                                         ###
###                                                                                                                 ###
#######################################################################################################################


def process_deployment_scripts(root_dir: str):
    try:
        mdep = '/tmp/deployments.sh'
        rm_file(file=mdep)
        append_line_to_file(file=mdep, line='#!/bin/sh')
        append_line_to_file(file=mdep, line='export $(grep -v \'^#\' /etc/environment | xargs -d \'\n\')')
        for dirpath, dirnames, filenames in os.walk(root_dir):
            logger.info('Looking for deployment file in directory "{}"'.format(dirpath))
            for file in filenames:
                logger.debug('      --> eval file "{}"'.format(file))
                if file == 'deploy.sh':
                    full_file = '{}{}{}'.format(dirpath, os.sep, file)
                    logger.info('   Adding deployment from file "{}"'.format(full_file))
                    append_line_to_file(file=mdep, line='cd {}'.format(dirpath))
                    append_line_to_file(file=mdep, line='sh {}'.format(full_file))
        os.system(mdep)
        rm_file(file=mdep)
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))


def process_message(
    message: dict,
    global_env: dict=get_global_environment()
):
    logger.info('/'*80)
    logger.debug('message={}'.format(message))

    local_tar_file = None
    try:
        url = message['tar_file']
        logger.info('Attempting to download {}'.format(url))
        local_tar_file = download_file(url=url, target_dir=global_env['GITHUB_WORKDIR'])
        work_dir =  untar_file(file=local_tar_file, work_dir=global_env['GITHUB_WORKDIR'])
        process_deployment_scripts(root_dir=work_dir)
        
        logger.warning('TODO Change into work_dir and run the deployment file within each sub-directory in the work_dir')

    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))

    logger.info('\\'*80)


def main():
    sqs_url = get_sqs_url()
    consecutive_zero_count = 0
    global_env = get_global_environment()
    while True:
        logger.info('-'*80)
        logger.info('MAIN LOOP')
        messages = receive_messages(sqs_url=sqs_url)
        logger.info('Received {} message(s)'.format(len(messages)))

        try:
            for message in messages:
                process_message(
                    message=json.loads(message['Body']),
                    global_env=global_env
                )
        except:
            logger.error('EXCEPTION: {}'.format(traceback.format_exc()))

        # Should I die?
        if len(messages) == 0:
            consecutive_zero_count += 1
            logger.info('consecutive_zero_count={}'.format(consecutive_zero_count))
        else:
            consecutive_zero_count = 0

        if consecutive_zero_count > 20:
            logger.warning('No new messages in over 10 minutes... Terminating Self')
            terminate_self()

        time.sleep(30)


if __name__ == '__main__':
    logger.info('='*80)
    logger.info('===')
    logger.info('===          SYNC CYCLE MAIN START')
    logger.info('===')
    logger.info('='*80)
    for k, v in os.environ.items():
        logger.debug('ENVIRONMENT:   {}={}'.format(k,v))

    main()

