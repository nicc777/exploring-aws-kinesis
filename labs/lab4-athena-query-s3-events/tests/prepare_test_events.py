import csv
import json
import os
import sys


file_name = None
if len(sys.argv) > 1:
    file_name = sys.argv[1]

if file_name is None:
    raise Exception('A filename containing test data must be provided')

print('Parsing test data file: {}'.format(file_name))



