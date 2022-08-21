"""
    Using example from https://github.com/amazon-archives/serverless-app-examples/blob/master/python/kinesis-analytics-process-record-python/lambda_function.py

    Adapted to add a more AWS and Python logging function for CloudWatch (replacing the print statements)

    This lambda functions receives a Proxy 2 request from API Gateway (expecting JSON POST messages) and converts the incoming JSON data to something we can push to Kinesis.

    User --> API Gateway --> * This Lambda Functions * --> kinesis --> S3
"""

import json
import logging
import boto3
import hashlib
import traceback


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def lambda_handler(event, context):
    logger.debug('event={}'.format(event))
    client = boto3.client('kinesis')
    incoming_data = dict()
    incoming_data['amazonTraceId'] = event['headers']['X-Amzn-Trace-Id']
    incoming_data['numberOfFields'] = 0
    incoming_data['fieldNames'] = ""
    try:
        body_data = json.loads(event['body'])
        keys = list(body_data.keys())
        incoming_data['numberOfFields'] = len(keys)
        incoming_data['fieldNames'] = ",".join(keys)
        response = client.put_record(
            StreamName='data_recorder_01',
            Data='{}'.format(json.dumps(incoming_data)).encode('utf-8'),
            PartitionKey=hashlib.md5('{}'.format(json.dumps(incoming_data)).encode('utf-8')).hexdigest()
        )
        logger.debug('response={}'.format(response))
    except:
        logger.error('EXCEPTION: {}'.format(traceback.format_exc()))
    result = dict()
    return_object = {
        'statusCode': 201,
        'headers': {
            'x-custom-header' : 'my custom header value',
            'content-type': 'application/json',
        },
        'body': result,
        'isBase64Encoded': False,
    }
    
    result['message'] = 'ok'
    return_object['body'] = json.dumps(result)
    return return_object

