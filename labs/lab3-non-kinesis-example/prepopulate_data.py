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

TABLE_NAME = 'lab3-access-card-app'


def get_utc_timestamp(with_decimal: bool = False):
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    now = datetime.utcnow()
    timestamp = (now - epoch).total_seconds()
    if with_decimal:
        return timestamp
    return int(timestamp)


# def create_departments():
#     global DEPARTMENTS
#     dept_id = 0
#     while len(DEPARTMENTS) < 100:
#         dept_id += 1
#         DEPARTMENTS[dept_id] = 'Department-{}'.format(dept_id)


# def calc_partition_key_value_from_subject_and_id(subject_type: str, subject_id: int)->str:
#     subject_id_to_str = '{}'.format(subject_id)
#     subject_id_to_str = '1{}{}'.format(subject_id_to_str.zfill(11), subject_type)
#     return '{}{}'.format(
#         hashlib.sha256(subject_id_to_str.encode('utf-8')).hexdigest(),
#         subject_type
#     )


# class SubjectType:
#     EMPLOYEE='-E'
#     ACCESS_CARD='AC'
#     BUILDING='-B'
#     LINKED_CARD='LC'


# class Subject:
#     def __init__(self, subject_type: str, subject_id: int):
#         self.subject_type = subject_type
#         self.subject_id = subject_id
#         self.PARTITION_KEY = calc_partition_key_value_from_subject_and_id(subject_type=subject_type, subject_id=subject_id)


# class LinkedSubjects:
#     def __init__(self, subject1: Subject, subject2: Subject):
#         self.subject1 = subject1
#         self.subject2 = subject2
#         self.PARTITION_KEY = '{}LS'.format(hashlib.sha256('{}|{}'.format(subject1.PARTITION_KEY,subject2.PARTITION_KEY).encode('utf-8')).hexdigest())


# def create_first_100_employees()->dict:
#     global employee_ids
#     employees = dict()
#     client = boto3.client('dynamodb', region_name='eu-central-1')
#     employee_sequence = 0
#     while employee_sequence < 101:
#         employee_sequence += 1
#         subject_id_to_str = '{}'.format(employee_sequence)
#         subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
#         subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.EMPLOYEE, subject_id=employee_sequence)
#         employee_ids.append(subject_id)
#         response = client.put_item(
#             TableName=TABLE_NAME,
#             Item={
#                 'subject-id'        : { 'S': subject_id},
#                 'subject-topic'     : { 'S': 'employee#profile#{}'.format(subject_id_to_str)},
#                 'employee-id'       : { 'S': subject_id_to_str},
#                 'first-name'        : { 'S': 'Firstname-{}'.format(employee_sequence)},
#                 'last-name'         : { 'S': 'Lastname-{}'.format(employee_sequence)},
#                 'department'        : { 'S': DEPARTMENTS[1]},
#                 'employee-status'   : { 'S': 'active'},
#             },
#             ReturnValues='NONE',
#             ReturnConsumedCapacity='TOTAL',
#             ReturnItemCollectionMetrics='SIZE'
#         )
#         employees[subject_id] = dict()
#         employees[subject_id]['subject-topic'] = 'employee#profile#{}'.format(subject_id_to_str)
#         employees[subject_id]['employee-id'] = subject_id_to_str
#         employees[subject_id]['first-name'] = 'Firstname-{}'.format(employee_sequence)
#         employees[subject_id]['last-name'] = 'Lastname-{}'.format(employee_sequence)
#         employees[subject_id]['department'] = DEPARTMENTS[1]
#         employees[subject_id]['employee-status'] = 'active'
#         print('Created employee {}'.format(subject_id_to_str))
#         time.sleep(50/1000) # Sleep 50 milliseconds
#     return employees


# def create_employees_to_be_onboarded(qty: int=1000)->dict:
#     employees = dict()
#     dept_keys = list(DEPARTMENTS.keys())
#     client = boto3.client('dynamodb', region_name='eu-central-1')
#     employee_sequence = 100
#     qty_created = 0
#     while qty_created < qty:
#         qty_created += 1
#         employee_sequence += 1
#         subject_id_to_str = '{}'.format(employee_sequence)
#         subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
#         subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.EMPLOYEE, subject_id=employee_sequence)
#         response = client.put_item(
#             TableName=TABLE_NAME,
#             Item={
#                 'subject-id'        : { 'S': subject_id},
#                 'subject-topic'     : { 'S': 'employee#profile#{}'.format(subject_id_to_str)},
#                 'employee-id'       : { 'S': subject_id_to_str},
#                 'first-name'        : { 'S': 'Firstname-{}'.format(employee_sequence)},
#                 'last-name'         : { 'S': 'Lastname-{}'.format(employee_sequence)},
#                 'department'        : { 'S': DEPARTMENTS[random.choice(dept_keys)]},
#                 'employee-status'   : { 'S': 'onboarding'},
#             },
#             ReturnValues='NONE',
#             ReturnConsumedCapacity='TOTAL',
#             ReturnItemCollectionMetrics='SIZE'
#         )
#         print('Created employee {}'.format(subject_id_to_str))
#         employees[subject_id] = dict()
#         employees[subject_id]['subject-topic'] = 'employee#profile#{}'.format(subject_id_to_str)
#         employees[subject_id]['employee-id'] = subject_id_to_str
#         employees[subject_id]['first-name'] = 'Firstname-{}'.format(employee_sequence)
#         employees[subject_id]['last-name'] = 'Lastname-{}'.format(employee_sequence)
#         employees[subject_id]['department'] = DEPARTMENTS[1]
#         employees[subject_id]['employee-status'] = 'onboarding'
#         time.sleep(150/1000) 


# def create_access_cards(qty: int=1100):
#     global access_cards_ids
#     access_cards = dict()
#     client = boto3.client('dynamodb', region_name='eu-central-1')
#     access_card_sequence = 0
#     while access_card_sequence < qty:
#         access_card_sequence += 1
#         subject_id_to_str = '{}'.format(access_card_sequence)
#         subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
#         subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.ACCESS_CARD, subject_id=access_card_sequence)
#         # access_cards_ids.append(subject_id)
#         access_cards_ids[subject_id] = subject_id_to_str    # access_cards_ids[fgfgf...fsfs00AC] = 100000000001
#         response = client.put_item(
#             TableName=TABLE_NAME,
#             Item={
#                 'subject-id'            : { 'S': subject_id},
#                 'subject-topic'         : { 'S': 'access-card#profile#{}'.format(subject_id_to_str)},
#                 'access-card-id'        : { 'S': subject_id_to_str},
#                 'access-card-issued-to' : { 'S': 'NOT-ISSUED'},
#                 'access-card-status'    : { 'S': 'unissued'}
#             },
#             ReturnValues='NONE',
#             ReturnConsumedCapacity='TOTAL',
#             ReturnItemCollectionMetrics='SIZE'
#         )
#         print('Created access card {}'.format(subject_id_to_str))
#         access_cards[subject_id] = dict()
#         access_cards['subject-topic'] = 'access-card#profile#{}'.format(subject_id_to_str)
#         access_cards['access-card-id'] = subject_id_to_str
#         access_cards['access-card-issued-to'] = 'NOT-ISSUED'
#         access_cards['access-card-status'] = 'unissued'
#         time.sleep(150/1000)


# def select_unique_random_items_from_list(input_list: list, qty_items: int)->list:
#     random.shuffle(input_list)
#     return input_list[0:qty_items-1]


# def randomly_issue_first_100_cards_to_first_100_employees():
#     client = boto3.client('dynamodb', region_name='eu-central-1')
#     now = get_utc_timestamp(with_decimal=False)
#     first_employees_randomized = select_unique_random_items_from_list(input_list=copy.deepcopy(employee_ids), qty_items=len(employee_ids))
#     print('Qty first_employees_randomized = {}'.format(len(first_employees_randomized)))
#     access_cards_to_link = select_unique_random_items_from_list(input_list=copy.deepcopy(list(access_cards_ids.keys())), qty_items=len(employee_ids))
#     linked_access_card_sequence = 0
#     idx = 0
#     while idx < len(first_employees_randomized):
#         employee_id = first_employees_randomized[idx]   # fgfgf...fsfs00-E
#         access_card_id = access_cards_to_link[idx]      # fgfgf...fsfs00AC
#         linked_access_card_sequence += 1
#         subject_id_to_str = '{}'.format(linked_access_card_sequence)
#         subject_id_to_str = '1{}'.format(subject_id_to_str.zfill(11))
#         subject_id = calc_partition_key_value_from_subject_and_id(subject_type=SubjectType.LINKED_CARD, subject_id=linked_access_card_sequence)

#         # Insert NEW linked Card
#         client.put_item(
#             TableName=TABLE_NAME,
#             Item={
#                 'subject-id'                                    : { 'S': subject_id},
#                 'subject-topic'                                 : { 'S': 'linked-access-card#association#{}'.format(subject_id_to_str)},
#                 'linking-timestamp'                             : { 'N': '{}'.format(now)},
#                 'linker-employee-partition-key'                 : { 'S': 'SYSTEM'},
#                 'access-card-building-state'                    : { 'S': 'NULL'},
#                 'access-card-current-building-partition-key'    : { 'S': 'NULL'},
#                 'linked-access-card-employee-partition-key'     : { 'S': employee_id},
#                 'linked-access-card-partition-key'              : { 'S': access_card_id},
#                 'linked-access-card-status'                     : { 'S': 'active'},
#             },
#             ReturnValues='NONE',
#             ReturnConsumedCapacity='TOTAL',
#             ReturnItemCollectionMetrics='SIZE'
#         )

#         # Update Existing Access Card
#         """
#             access_cards_ids[ subject_id       ] = subject_id_to_str    
#             access_cards_ids[ fgfgf...fsfs00AC ] = 100000000001
#         """
#         response2 = client.update_item(
#             TableName=TABLE_NAME,
#             Key={
#                 'subject-id'    : { 'S': access_card_id},
#                 'subject-topic' : { 'S': 'access-card#profile#{}'.format(access_cards_ids[access_card_id])}
#             },
#             UpdateExpression="set #an = :a , #bn = :b",
#             ExpressionAttributeValues={
#                 ':a': { 'S': employee_id},
#                 ':b': { 'S': 'issued'}
#             },
#             ExpressionAttributeNames={
#                 '#an': 'access-card-issued-to',
#                 '#bn': 'access-card-status'
#             },
#             ReturnValues="UPDATED_NEW"
#         )

#         print('Linked employee {} to access card {}'.format(employee_id, access_card_id))
#         if 'Attributes' in response2:
#             data = response2['Attributes']
#             print('\tAttributes: {}'.format(json.dumps(data)))
#         time.sleep(150/1000) 
#         idx += 1


def create_access_cards(qty_cards: int=300)->dict:
    cards = dict()
    idx = 0
    while idx < qty_cards:
        idx += 1
        card_id_to_str = '{}'.format(idx)
        card_id_to_str = '1{}'.format(card_id_to_str.zfill(11))
        cards[card_id_to_str] = dict()
        cards[card_id_to_str]['CardIssuedTimestamp'] = 0
        cards[card_id_to_str]['CardIssuedTo'] = 'not-issued'
        cards[card_id_to_str]['CardIssuedBy'] = 'SYSTEM'
    return cards


def populate_v2(employees: dict, access_cards: dict):
    client = boto3.client('dynamodb', region_name='eu-central-1')
    now = get_utc_timestamp(with_decimal=False)
    for employee_id, employee_data in employees.items():
        PK = 'EMP#{}'.format(employee_id)
        
        # Personal Data
        SK = 'PERSON#PERSONAL_DATA'
        client.put_item(
            TableName=TABLE_NAME,
            Item={
                'PK'                : { 'S': PK},
                'SK'                : { 'S': SK},
                'PersonName'        : { 'S': employee_data['PersonName']},
                'PersonSurname'     : { 'S': employee_data['PersonSurname']},
                'PersonDepartment'  : { 'S': employee_data['PersonDepartment']},
                'PersonStatus'      : { 'S': employee_data['PersonStatus']},
                'CognitoSubjectId'  : { 'S': 'no-login-{}'.format(PK)}
            },
            ReturnValues='NONE',
            ReturnConsumedCapacity='TOTAL',
            ReturnItemCollectionMetrics='SIZE'
        )

        # Issues Access Card
        if employee_data['PersonStatus'] == 'active':
            SK = 'PERSON#PERSONAL_DATA#ACCESS_CARD'
            selected_card_idx = employee_data['CardIdx']
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                    : { 'S': PK},
                    'SK'                    : { 'S': SK},
                    'CardIssuedTimestamp'   : { 'N': '{}'.format(access_cards[selected_card_idx]['CardIssuedTimestamp'])},
                    'CardRevokedTimestamp'  : { 'N': '0'},
                    'CardStatus'            : { 'S': employee_data['CardStatus']},
                    'CardIssuedTo'          : { 'S': access_cards[selected_card_idx]['CardIssuedTo']},
                    'CardIssuedBy'          : { 'S': employee_data['CardIssuedBy']},
                    'CardIdx'               : { 'S': employee_data['CardIdx']},
                    'PersonName'            : { 'S': employee_data['PersonName']},
                    'PersonSurname'         : { 'S': employee_data['PersonSurname']},
                    'PersonDepartment'      : { 'S': employee_data['PersonDepartment']},
                    'PersonStatus'          : { 'S': employee_data['PersonStatus']},
                    'ScannedBuildingIdx'    : { 'S': 'null'},
                    'ScannedStatus'         : { 'S': 'scanned-out'},
                    'CognitoSubjectId'      : { 'S': 'no-login-{}'.format(PK)}
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )

        if 'CardIdx' in employee_data and employee_data['PersonStatus'] == 'active':
            SK = 'PERSON#PERSONAL_DATA#PERMISSIONS#{}'.format(now)
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                    : { 'S': PK},
                    'SK'                    : { 'S': SK},
                    'CardIdx'               : { 'S': employee_data['CardIdx']},
                    'ScannedBuildingIdx'    : { 'S': 'null'},
                    'CognitoSubjectId'      : { 'S': 'no-login-{}'.format(PK)},
                    'SystemPermissions'     : { 'S': 'basic,public'},
                    'StartTimestamp'        : { 'N': '{}'.format(now)},
                    'EndTimestamp'          : { 'N': '-1'}
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )
            

    # Access Cards
    for access_card_id, access_card_data in access_cards.items():
        PK = 'CARD#{}'.format(access_card_id)
        if access_card_data['CardIssuedTo'] == 'not-issued':
            SK = 'CARD#STATUS'
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                    : { 'S': PK             },
                    'SK'                    : { 'S': SK             },
                    'LockIdentifier'        : { 'S': 'null'         },
                    'IsAvailableForIssue'   : { 'BOOL': True        },
                    'CardIssuedTo'          : { 'S': 'no-one'       },
                    'CardIssuedBy'          : { 'S': 'not-issued'   },
                    'CardIssuedTimestamp'   : { 'N': '-1'           }
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )
            SK = 'CARD#EVENT#{}'.format(now)
            lock_id = '{}'.format(hashlib.sha256('{}'.format(access_card_id).encode('utf-8')).hexdigest())
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                                : { 'S': PK                             },
                    'SK'                                : { 'S': SK                             },
                    'CardIdx'                           : { 'S': '{}'.format(access_card_id)    },
                    'EventType'                         : { 'S': 'NewCard'                      },
                    'EventBucketName'                   : { 'S': 'n/a'                          },
                    'EventBucketKey'                    : { 'S': 'n/a'                          },
                    'EventRequestId'                    : { 'S': 'n/a'                          },
                    'EventRequestedByEmployeeId'        : { 'S': 'SYSTEM'                       },
                    'EventTimestamp'                    : { 'N': '{}'.format(now)               },
                    'EventOutcomeDescription'           : { 'S': 'Physical Card Added to Pool'  },
                    'EventErrorMessage'                 : { 'S': 'No Errors'                    },
                    'EventCompletionStatus'             : { 'S': 'Success'                      },
                    'EventProcessorLockId'              : { 'S': '{}'.format(lock_id)           },
                    'EventProcessorStartTimestamp'      : { 'N': '{}'.format(now)               },
                    'EventProcessorExpiresTimestamp'    : { 'N': '{}'.format(now)               },
                    'EventSqsAck'                       : { 'BOOL': False                       },
                    'EventSqsDelete'                    : { 'BOOL': False                       },
                    'EventSqsReject'                    : { 'BOOL': False                       },
                    'EventSqsId'                        : { 'S': 'n/a'                          },
                    'EventSqsOriginalPayloadJson'       : { 'S': '{{}}'                         }
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )
        else:
            SK = 'CARD#STATUS'
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                    : { 'S': PK                                                     },
                    'SK'                    : { 'S': SK                                                     },
                    'CardIssuedTo'          : { 'S': access_card_data['CardIssuedTo']                       },
                    'CardIssuedBy'          : { 'S': 'SYSTEM'                                               },
                    'CardIssuedTimestamp'   : { 'N': '{}'.format(access_card_data['CardIssuedTimestamp'])   },
                    'LockIdentifier'        : { 'S': 'null'                                                 },
                    'IsAvailableForIssue'   : { 'BOOL': False                                               }
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )
            SK = 'CARD#EVENT#{}'.format(now)
            lock_id = '{}'.format(hashlib.sha256('{}'.format(access_card_id).encode('utf-8')).hexdigest())
            description = 'Physical Card Added to Pool and Issued to {}'.format(access_card_data['CardIssuedTo'])
            client.put_item(
                TableName=TABLE_NAME,
                Item={
                    'PK'                                : { 'S': PK                             },
                    'SK'                                : { 'S': SK                             },
                    'CardIdx'                           : { 'S': '{}'.format(access_card_id)    },
                    'EventType'                         : { 'S': 'NewCard+LinkCard'             },
                    'EventBucketName'                   : { 'S': 'n/a'                          },
                    'EventBucketKey'                    : { 'S': 'n/a'                          },
                    'EventRequestId'                    : { 'S': 'n/a'                          },
                    'EventRequestedByEmployeeId'        : { 'S': 'SYSTEM'                       },
                    'EventTimestamp'                    : { 'N': '{}'.format(now)               },
                    'EventOutcomeDescription'           : { 'S': '{}'.format(description)       },
                    'EventErrorMessage'                 : { 'S': 'No Errors'                    },
                    'EventCompletionStatus'             : { 'S': 'Success'                      },
                    'EventProcessorLockId'              : { 'S': '{}'.format(lock_id)           },
                    'EventProcessorStartTimestamp'      : { 'N': '{}'.format(now)               },
                    'EventProcessorExpiresTimestamp'    : { 'N': '{}'.format(now)               },
                    'EventSqsAck'                       : { 'BOOL': False                       },
                    'EventSqsDelete'                    : { 'BOOL': False                       },
                    'EventSqsReject'                    : { 'BOOL': False                       },
                    'EventSqsId'                        : { 'S': 'n/a'                          },
                    'EventSqsOriginalPayloadJson'       : { 'S': '{{}}'                         }
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL',
                ReturnItemCollectionMetrics='SIZE'
            )


def create_employees(total_qty: int=200, active: int=100, access_cards: dict=copy.deepcopy(create_access_cards()))->tuple:
    now = get_utc_timestamp(with_decimal=False)
    card_pool_idx = list(access_cards.keys())
    # print('card_pool_idx={}'.format(card_pool_idx))
    employees = dict()
    idx = 0
    while idx < total_qty:
        idx += 1
        employee_id_to_str = '{}'.format(idx)
        employee_id_to_str = '1{}'.format(employee_id_to_str.zfill(11))
        employees[employee_id_to_str] = dict()
        employees[employee_id_to_str]['PersonName'] = 'Name{}'.format(employee_id_to_str)
        employees[employee_id_to_str]['PersonSurname'] = 'Surname{}'.format(employee_id_to_str)
        employees[employee_id_to_str]['PersonDepartment'] = 'DepartmentA'
        employees[employee_id_to_str]['PersonStatus'] = 'onboarding'
        if len(employees) < active:
            selected_card_idx = random.choice(card_pool_idx)
            card_pool_idx.remove(selected_card_idx)
            access_cards[selected_card_idx]['CardIssuedTimestamp'] = now
            access_cards[selected_card_idx]['CardIssuedTo'] = employee_id_to_str
            employees[employee_id_to_str]['PersonStatus'] = 'active'
            employees[employee_id_to_str]['CardIssuedTimestamp'] = now
            employees[employee_id_to_str]['CardRevokedTimestamp'] = 0
            employees[employee_id_to_str]['CardStatus'] = 'issued'
            employees[employee_id_to_str]['CardIssuedBy'] = 'SYSTEM'
            employees[employee_id_to_str]['CardIdx'] = selected_card_idx
    return (employees, access_cards,)




if __name__ == '__main__':
    access_cards = create_access_cards(qty_cards=200)
    employees, access_cards = create_employees(total_qty=200, active=100, access_cards=copy.deepcopy(access_cards))   
    print('='*80)
    print(json.dumps(access_cards))
    print('-'*80)
    print(json.dumps(employees))

    populate_v2(employees=employees, access_cards=access_cards)
