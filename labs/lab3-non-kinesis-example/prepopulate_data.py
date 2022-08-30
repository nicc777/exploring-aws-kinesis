import boto3
import traceback


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


