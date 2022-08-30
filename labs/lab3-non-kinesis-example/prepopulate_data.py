import boto3
import traceback
import hashlib
import time
import random


DEPARTMENTS = dict()


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
    client = boto3.client('dynamodb', region_name='eu-central-1')
    employee_sequence = 0
    while employee_sequence < 101:
        employee_sequence += 1
        subject_id_to_str = '{}'.format(employee_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        response = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'        : { 'S': calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.EMPLOYEE, subject_id=employee_sequence)},
                'subject-topic'     : { 'S': 'employee#profile'},
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
        print(response)
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
                'subject-topic'     : { 'S': 'employee#profile'},
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
        print(response)
        time.sleep(50/1000) # Sleep 50 milliseconds


def create_access_cards(qty: int=1100):
    client = boto3.client('dynamodb', region_name='eu-central-1')
    access_card_sequence = 0
    while access_card_sequence < qty:
        access_card_sequence += 1
        subject_id_to_str = '{}'.format(access_card_sequence)
        subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
        response = client.put_item(
            TableName='access-card-app',
            Item={
                'subject-id'            : { 'S': calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.ACCESS_CARD, subject_id=access_card_sequence)},
                'subject-topic'         : { 'S': 'access-card#profile'},
                'access-card-id'        : { 'S': subject_id_to_str},
                'access-card-issued-to' : { 'S': 'NOT-ISSUED'},
                'access-card-status'    : { 'S': 'unissued'}
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )
        print(response)
        time.sleep(50/1000) # Sleep 50 milliseconds


def randomly_issue_first_100_cards_to_first_100_employees():
    pass



if __name__ == '__main__':
    create_departments()
    create_first_100_employees()
    create_employees_to_be_onboarded(qty=100)
    create_access_cards(qty=200)
    randomly_issue_first_100_cards_to_first_100_employees()
