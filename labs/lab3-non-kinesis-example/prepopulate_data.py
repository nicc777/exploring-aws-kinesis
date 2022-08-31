from datetime import datetime
import boto3
import hashlib
import time
import random
import copy
import json


DEPARTMENTS = dict()

employee_ids = list()
access_cards_ids = dict()


def get_utc_timestamp(with_decimal: bool = False):
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    now = datetime.utcnow()
    timestamp = (now - epoch).total_seconds()
    if with_decimal:
        return timestamp
    return int(timestamp)


def create_departments():
    global DEPARTMENTS
    dept_id = 0
    while len(DEPARTMENTS) < 100:
        dept_id += 1
        DEPARTMENTS[dept_id] = 'Department-{}'.format(dept_id)


def calc_partition_key_value_from_subject_and_id(subject_type: str, subject_id: int)->str:
    subject_id_to_str = '{}'.format(subject_id)
    subject_id_to_str = '1{}{}'.format(subject_id_to_str.zfill(11), subject_type)
    return '{}{}'.format(
        hashlib.sha256(subject_id_to_str.encode('utf-8')).hexdigest(),
        subject_type
    )


class SubjectType:
    EMPLOYEE='-E'
    ACCESS_CARD='AC'
    BUILDING='-B'
    LINKED_CARD='LC'


class Subject:
    def __init__(self, subject_type: str, subject_id: int):
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.PARTITION_KEY = calc_partition_key_value_from_subject_and_id(subject_type=subject_type, subject_id=subject_id)


class LinkedSubjects:
    def __init__(self, subject1: Subject, subject2: Subject):
        self.subject1 = subject1
        self.subject2 = subject2
        self.PARTITION_KEY = '{}LS'.format(hashlib.sha256('{}|{}'.format(subject1.PARTITION_KEY,subject2.PARTITION_KEY).encode('utf-8')).hexdigest())


def create_first_100_employees():
    global employee_ids
    client = boto3.client('dynamodb', region_name='eu-central-1')
    employee_sequence = 0
    while employee_sequence < 101:
        employee_sequence += 1
        subject_id_to_str = '{}'.format(employee_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.EMPLOYEE, subject_id=employee_sequence)
        employee_ids.append(subject_id)
        response = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'        : { 'S': subject_id},
                'subject-topic'     : { 'S': 'employee#profile#{}'.format(subject_id_to_str)},
                'employee-id'       : { 'S': subject_id_to_str},
                'first-name'        : { 'S': 'Firstname-{}'.format(employee_sequence)},
                'last-name'         : { 'S': 'Lastname-{}'.format(employee_sequence)},
                'department'        : { 'S': DEPARTMENTS[1]},
                'employee-status'   : { 'S': 'active'},
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        print('Created employee {}'.format(subject_id_to_str))
        time.sleep(50/1000) # Sleep 50 milliseconds


def create_employees_to_be_onboarded(qty: int=1000):
    dept_keys = list(DEPARTMENTS.keys())
    client = boto3.client('dynamodb', region_name='eu-central-1')
    employee_sequence = 100
    qty_created = 0
    while qty_created < qty:
        qty_created += 1
        employee_sequence += 1
        subject_id_to_str = '{}'.format(employee_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        response = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'        : { 'S': calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.EMPLOYEE, subject_id=employee_sequence)},
                'subject-topic'     : { 'S': 'employee#profile#{}'.format(subject_id_to_str)},
                'employee-id'       : { 'S': subject_id_to_str},
                'first-name'        : { 'S': 'Firstname-{}'.format(employee_sequence)},
                'last-name'         : { 'S': 'Lastname-{}'.format(employee_sequence)},
                'department'        : { 'S': DEPARTMENTS[random.choice(dept_keys)]},
                'employee-status'   : { 'S': 'onboarding'},
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        print('Created employee {}'.format(subject_id_to_str))
        time.sleep(150/1000) 


def create_access_cards(qty: int=1100):
    global access_cards_ids
    client = boto3.client('dynamodb', region_name='eu-central-1')
    access_card_sequence = 0
    while access_card_sequence < qty:
        access_card_sequence += 1
        subject_id_to_str = '{}'.format(access_card_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.ACCESS_CARD, subject_id=access_card_sequence)
        # access_cards_ids.append(subject_id)
        access_cards_ids[subject_id] = subject_id_to_str
        response = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'            : { 'S': subject_id},
                'subject-topic'         : { 'S': 'access-card#profile#{}'.format(subject_id_to_str)},
                'access-card-id'        : { 'S': subject_id_to_str},
                'access-card-issued-to' : { 'S': 'NOT-ISSUED'},
                'access-card-status'    : { 'S': 'unissued'}
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        print('Created access card {}'.format(subject_id_to_str))
        time.sleep(150/1000)


def select_unique_random_items_from_list(input_list: list, qty_items: int)->list:
    random.shuffle(input_list)
    return input_list[0:qty_items-1]


def randomly_issue_first_100_cards_to_first_100_employees():
    client = boto3.client('dynamodb', region_name='eu-central-1')
    now = get_utc_timestamp(with_decimal=False)
    first_employees_randomized = select_unique_random_items_from_list(input_list=copy.deepcopy(employee_ids), qty_items=len(employee_ids))
    print('Qty first_employees_randomized = {}'.format(len(first_employees_randomized)))
    access_cards_to_link = select_unique_random_items_from_list(input_list=copy.deepcopy(list(access_cards_ids.keys())), qty_items=len(employee_ids))
    linked_access_card_sequence = 0
    idx = 0
    while idx < len(first_employees_randomized):
        employee_id = first_employees_randomized[idx]
        access_card_id = access_cards_to_link[idx]
        linked_access_card_sequence += 1
        subject_id_to_str = '{}'.format(linked_access_card_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.LINKED_CARD, subject_id=linked_access_card_sequence)

        # Insert NEW linked Card
        response1 = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'                                    : { 'S': subject_id},
                'subject-topic'                                 : { 'S': 'linked-access-card#association#{}'.format(access_cards_ids[access_card_id])},
                'linking-timestamp'                             : { 'N': '{}'.format(now)},
                'linker-employee-partition-key'                 : { 'S': 'SYSTEM'},
                'access-card-building-state'                    : { 'S': 'NULL'},
                'access-card-current-building-partition-key'    : { 'S': 'NULL'},
                'linked-access-card-employee-partition-key'     : { 'S': employee_id},
                'linked-access-card-partition-key'              : { 'S': access_card_id},
                'linked-access-card-status'                     : { 'S': 'active'},
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )

        # Update Existing Access Card
        response2 = client.update_item(
            TableName='access-card-app',
            Key={
                'subject-id'    : { 'S': access_card_id},
                'subject-topic' : { 'S': 'access-card#profile#{}'.format(XXX)}
            },
            UpdateExpression="set access-card-issued-to = :a , access-card-status = :b",
            ExpressionAttributeValues={
                ':a': employee_id,
                ':b': 'issued'
            },
            ReturnValues="UPDATED_NEW"
        )

        print('Linked employee {} to access card {}'.format(employee_id, access_card_id))
        if 'Attributes' in response2:
            data = response2['Attributes']
            print('\tAttributes: {}'.format(json.dumps(data)))
        time.sleep(150/1000) 
        idx += 1



if __name__ == '__main__':
    qty_employees_to_be_onboarded = 100
    qty_access_cards_to_provision = 100 + qty_employees_to_be_onboarded + 100
    create_departments()
    create_first_100_employees()
    create_employees_to_be_onboarded(qty=qty_employees_to_be_onboarded)
    create_access_cards(qty=qty_access_cards_to_provision)    # Ensure we create a little more than what is required...
    randomly_issue_first_100_cards_to_first_100_employees()
