import csv
import json
import os
import sys
import boto3
import copy
from datetime import datetime


file_name = None
if len(sys.argv) > 1:
    file_name = sys.argv[1]

if file_name is None:
    raise Exception('A filename containing test data must be provided')

print('Parsing test data file: {}'.format(file_name))

if os.path.exists(file_name) is False:
    raise Exception('ERR: File does not appear to exist')

if os.path.isfile(file_name) is False:
    raise Exception('ERR: Not a file?')

reader = None
test_data = list()
with open(file_name, newline='') as csv_file:
    reader = csv.DictReader(csv_file)
    keys = reader.fieldnames
    for row in reader:
        record = dict()
        for key in keys:
            record[key] = row[key]
        test_data.append(record)

# print('JSON test_data={}'.format(json.dumps(test_data)))
print('Test Data contains {} records/transaction events'.format(len(test_data)-1))





def build_cash_deposit_event(data: dict)->dict:
    event_data = dict()
    print('Preparing a cash deposit event for source account {}'.format(data['Reference Account']))

    return event_data


def build_incoming_payment_event(data: dict)->dict:
    event_data = dict()
    print('Preparing an incoming payment event for source account {}'.format(data['Reference Account']))

    """
        {
            "EventTimeStamp": 1234567890,
            "TargetAccount": "<<account number>>",
            "Amount": "123.45",
            "LocationType": "ATM or Teller",
            "Reference": "Some Free Form Text",
            "Verified": false,
            "Currency": {
                "100-euro-bills": 1,
                "20-euro-bills": 1,
                "1-euro-bills": 3,
                "20-cents": 2,
                "5-cents": 1
            }
        }
    """

    tx_datetime = datetime(
        int(data['Transaction Date Year']),
        int(data['Transaction Date Month']),
        int(data['Transaction Date Day']),
        int(int(data['Transaction Date 24HR Time'])/100),
        int(data['Transaction Date 24HR Time'][2:4])
    )
    event_data['EventTimeStamp'] = int(tx_datetime.timestamp())
    print('   Transaction timestamp: {} -> {}'.format(tx_datetime, event_data['EventTimeStamp']))

    return event_data



def upload_event(event_data: dict)->bool:
    
    return True


EVENT_BUILD_MAPPING = {
    'cash_deposit_': build_cash_deposit_event,
    'incoming_payment_': build_incoming_payment_event,
}


for event_record in test_data:
    EVENT_BUILD_MAPPING[event_record['Transaction Type']](data=copy.deepcopy(event_record))
