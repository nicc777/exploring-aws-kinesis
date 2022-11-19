import csv
import json
import os
import sys
import boto3


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

