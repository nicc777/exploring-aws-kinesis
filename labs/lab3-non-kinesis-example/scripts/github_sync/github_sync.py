import logging
import logging.handlers
import time
from datetime import datetime
import logging.handlers
import boto3
import json
import traceback


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


def main():
    sqs_url = get_sqs_url()
    consecutive_zero_count = 0
    while True:
        logger.info('MAIN LOOP')
        messages = receive_messages(sqs_url=sqs_url)
        logger.info('Received {} message(s)'.format(len(messages)))

        # Should I die?
        if len(messages) == 0:
            consecutive_zero_count += 1
            logger.info('consecutive_zero_count={}'.format(consecutive_zero_count))
        else:
            consecutive_zero_count = 0

        if consecutive_zero_count > 20:
            logger.warning('No new messages in over 10 minutes... Terminating Self')
            time.sleep(30)
            terminate_self()

        time.sleep(30)


if __name__ == '__main__':
    main()

