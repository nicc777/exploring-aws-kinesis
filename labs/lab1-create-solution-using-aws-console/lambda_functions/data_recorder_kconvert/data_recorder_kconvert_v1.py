"""
    Using example from https://github.com/amazon-archives/serverless-app-examples/blob/master/python/kinesis-analytics-process-record-python/lambda_function.py

    Adapted to add a more AWS and Python logging function for CloudWatch (replacing the print statements)
"""

import base64
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info('Loading function')


def lambda_handler(event, context):
    logger.info('event={}'.format(event))
    output = []

    for record in event['records']:
        payload = base64.b64decode(record['data'])

        # Do custom processing on the record payload here
        output_record = {
            'recordId': record['recordId'],
            'result': 'Ok',
            'data': base64.b64encode(payload)
        }
        output.append(output_record)

    logger.info('Successfully processed {} records.'.format(len(event['records'])))

    return {'records': output}
