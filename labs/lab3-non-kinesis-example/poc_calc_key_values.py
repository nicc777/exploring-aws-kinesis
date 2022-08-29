import hashlib
import random


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
    def __init__(self, subject_type: str, subject_id):
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.PARTITION_KEY = calc_partition_key_value_from_subject_and_id(subject_type=subject_type, subject_id=subject_id)


class LinkedSubjects:
    def __init__(self, subject1: Subject, subject2: Subject):
        self.subject1 = subject1
        self.subject2 = subject2
        self.PARTITION_KEY = '{}LS'.format(hashlib.sha256('{}|{}'.format(subject1.PARTITION_KEY,subject2.PARTITION_KEY).encode('utf-8')).hexdigest())

source_data = [
    [SubjectType.EMPLOYEE, 0, 'Employee'],
    [SubjectType.EMPLOYEE, 1, 'Employee'],
    [SubjectType.EMPLOYEE, 2, 'Employee'],
    [SubjectType.EMPLOYEE, 1998, 'Employee'],
    [SubjectType.EMPLOYEE, 1999, 'Employee'],
    [SubjectType.EMPLOYEE, 2000, 'Employee'],
    [SubjectType.ACCESS_CARD, 0, 'Access Card'],
    [SubjectType.ACCESS_CARD, 1, 'Access Card'],
    [SubjectType.ACCESS_CARD, 2, 'Access Card'],
    [SubjectType.ACCESS_CARD, 1998, 'Access Card'],
    [SubjectType.ACCESS_CARD, 1999, 'Access Card'],
    [SubjectType.ACCESS_CARD, 2000, 'Access Card'],
    [SubjectType.BUILDING, 0, 'Building'],
    [SubjectType.BUILDING, 1, 'Building'],
    [SubjectType.BUILDING, 98, 'Building'],
    [SubjectType.BUILDING, 99, 'Building'],
]

employees = list()
access_cards = list()

for sd in source_data:
    s = Subject(subject_type=sd[0], subject_id=sd[1])
    if sd[0] == SubjectType.EMPLOYEE:
        employees.append(s)
    if sd[0] == SubjectType.ACCESS_CARD:
        access_cards.append(s)
    t = '{}'.format(sd[1])
    id_number = '1{}'.format(t.zfill(11))
    print('| {} | {} | `{}` |'.format(sd[2], id_number, s.PARTITION_KEY))

random.shuffle(employees)
random.shuffle(access_cards)

id = 0
while id < 6:
    ls = LinkedSubjects(subject1=employees[id], subject2=access_cards[id])
    eid = '{}'.format(employees[id].subject_id)
    eid = '1{}'.format(eid.zfill(11))
    acid = '{}'.format(access_cards[id].subject_id)
    acid = '1{}'.format(acid.zfill(11))
    print(
        '| {} | {} | `{}` |'.format(
            eid,
            acid,
            ls.PARTITION_KEY
        )
    )
    id += 1
