import csv
import json
import os
import sys
import boto3
import copy
from datetime import datetime


STEP = False

file_name = None
if len(sys.argv) > 1:
    file_name = sys.argv[1]

if len(sys.argv) > 2:
    STEP = True

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


def _create_datetime_object_from_test_data(data: dict)->int:
    tx_datetime = datetime(
        int(data['Transaction Date Year']),
        int(data['Transaction Date Month']),
        int(data['Transaction Date Day']),
        int(int(data['Transaction Date 24HR Time'])/100),
        int(data['Transaction Date 24HR Time'][2:4])
    )
    return int(tx_datetime.timestamp())


#######################################################################################################################
###                                                                                                                 ###
###                                              BUILD EVENT FUNCTIONS                                              ###
###                                                                                                                 ###
#######################################################################################################################

def build_cash_deposit_event(data: dict)->dict:
    event_data = dict()
    print('Preparing a cash deposit event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['TargetAccount']                 = data['Reference Account']
    event_data['Amount']                        = data['Amount']
    event_data['LocationType']                  = data['Location']
    event_data['Reference']                     = data['Reference']
    
    event_data['Verified']                      = False
    if data['Instant Verify Flag'].lower() == 'true':
        event_data['Verified']                  = True

    event_data['Currency']                      = dict()
    event_data['Currency']['100-euro-bills']    = data['Notes-100']
    event_data['Currency']['50-euro-bills']     = data['Notes-50']
    event_data['Currency']['20-euro-bills']     = data['Notes-20']
    event_data['Currency']['10-euro-bills']     = data['Notes-10']
    event_data['Currency']['50-cents']          = data['Coins-50']
    event_data['Currency']['20-cents']          = data['Coins-20']
    event_data['Currency']['10-cents']          = data['Coins-10']
    event_data['Currency']['5-cents']           = data['Coins-5']

    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data


def build_verify_cash_deposit_event(data: dict)->dict:
    event_data = dict()
    print('Preparing a cash deposit verification event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['TargetAccount']                 = data['Reference Account']
    event_data['Amount']                        = data['Amount']
    event_data['LocationType']                  = data['Location']
    event_data['Reference']                     = data['Reference']
    event_data['PreviousRequestIdReference']    = data['Linked RequestId']
    
    event_data['Verified']                      = False
    if data['Instant Verify Flag'].lower() == 'true':
        event_data['Verified']                  = True

    event_data['Currency']                      = dict()
    event_data['Currency']['100-euro-bills']    = data['Notes-100']
    event_data['Currency']['50-euro-bills']     = data['Notes-50']
    event_data['Currency']['20-euro-bills']     = data['Notes-20']
    event_data['Currency']['10-euro-bills']     = data['Notes-10']
    event_data['Currency']['50-cents']          = data['Coins-50']
    event_data['Currency']['20-cents']          = data['Coins-20']
    event_data['Currency']['10-cents']          = data['Coins-10']
    event_data['Currency']['5-cents']           = data['Coins-5']

    event_data['VerifiedByEmployeeId']          = data['Verified by Employee ID']
    event_data['FinalFinding']                  = data['Final Finding']

    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data


def build_incoming_payment_event(data: dict)->dict:
    event_data = dict()
    print('Preparing an incoming payment event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['TargetAccount']                 = data['Reference Account']
    event_data['Amount']                        = data['Amount']
    event_data['SourceInstitution']             = data['Source Bank']
    event_data['SourceAccount']                 = data['Source Reference']
    event_data['Reference']                     = data['Reference']
    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data


def build_outgoing_payment_unverified_event(data: dict)->dict:
    event_data = dict()
    print('Preparing an unverified outgoing payment event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['SourceAccount']                 = data['Reference Account']
    event_data['Amount']                        = data['Amount']
    event_data['TargetInstitution']             = data['Destination Bank']
    event_data['TargetAccount']                 = data['Destination Account Reference']
    event_data['Reference']                     = data['Reference']
    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data


def build_outgoing_payment_verified_event(data: dict)->dict:
    event_data = dict()
    print('Preparing an verified on previous outgoing payment event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['SourceAccount']                 = data['Reference Account']
    event_data['Reference']                     = data['Reference']
    event_data['PreviousRequestIdReference']    = data['Linked RequestId']

    return event_data


def build_outgoing_payment_rejected_event(data: dict)->dict:
    event_data = dict()
    print('Preparing a rejected payment event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['SourceAccount']                 = data['Reference Account']
    event_data['Reason']                        = data['Final Finding']
    event_data['PreviousRequestIdReference']    = data['Linked RequestId']

    return event_data


def build_cash_withdrawal_event(data: dict)->dict:
    event_data = dict()
    print('Preparing a cash withdrawal event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['SourceAccount']                 = data['Reference Account']
    event_data['Amount']                        = data['Amount']
    event_data['LocationType']                  = data['Location']
    event_data['Reference']                     = data['Reference']
    
    event_data['Currency']                      = dict()
    event_data['Currency']['100-euro-bills']    = data['Notes-100']
    event_data['Currency']['50-euro-bills']     = data['Notes-50']
    event_data['Currency']['20-euro-bills']     = data['Notes-20']
    event_data['Currency']['10-euro-bills']     = data['Notes-10']
    event_data['Currency']['50-cents']          = data['Coins-50']
    event_data['Currency']['20-cents']          = data['Coins-20']
    event_data['Currency']['10-cents']          = data['Coins-10']
    event_data['Currency']['5-cents']           = data['Coins-5']

    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data


def build_inter_account_transfer_event(data: dict)->dict:
    event_data = dict()
    print('Preparing an inter-account transfer event for source account {}'.format(data['Reference Account']))

    event_data['EventTimeStamp']                = _create_datetime_object_from_test_data(data=data)
    event_data['SourceAccount']                 = data['Reference Account']
    event_data['TargetAccount']                 = data['Destination Account Reference']
    event_data['Amount']                        = data['Amount']
    event_data['Reference']                     = data['Reference']
    event_data['CustomerNumber']                = data['CustomerNumber']

    return event_data

#######################################################################################################################
###                                                                                                                 ###
###                                         TEST DATA PROCESSING AND UPLOAD                                         ###
###                                                                                                                 ###
#######################################################################################################################

def upload_event(event_data: dict, key_name: str)->bool:
    if len(event_data) > 0:
        print('   Uploading data to key: {}'.format(key_name))
        print('      data: {}'.format(json.dumps(event_data)))
        s3_client = boto3.client('s3')
        s3_client.put_object(
            ACL='private',
            Body=json.dumps(event_data).encode('utf-8'),
            Bucket='lab4-new-events-qpwoeiryt',
            Key=key_name
        )

    else:
        print('   Can not upload key "{}" to S3 because there is no event data'.format(key_name))
    return True


EVENT_BUILD_MAPPING = {
    'cash_deposit_': build_cash_deposit_event,
    'incoming_payment_': build_incoming_payment_event,
    'verify_cash_deposit_': build_verify_cash_deposit_event,
    'cash_withdrawal_': build_cash_withdrawal_event,
    'outgoing_payment_unverified_': build_outgoing_payment_unverified_event,
    'outgoing_payment_verified_': build_outgoing_payment_verified_event,
    'outgoing_payment_rejected_': build_outgoing_payment_rejected_event,
    'inter_account_transfer_': build_inter_account_transfer_event,
}


tx_counter = 0
for event_record in test_data:
    tx_counter += 1
    request_id = f'r{tx_counter:07}'
    upload_event(
        event_data=EVENT_BUILD_MAPPING[event_record['Transaction Type']](data=copy.deepcopy(event_record)),
        key_name='{}{}.event'.format(event_record['Transaction Type'], request_id)
    )
    print()
    if STEP is True:
        input('Press ENTER for next transaction')
    print()
