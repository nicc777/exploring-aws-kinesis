
- [Lab 4 Goals](#lab-4-goals)
- [Initial Scenario Planning](#initial-scenario-planning)
  - [S3 Buckets](#s3-buckets)
  - [Event Data](#event-data)
    - [Cash Deposit Event](#cash-deposit-event)
    - [Verify Cash Deposit Event](#verify-cash-deposit-event)
    - [Cash Withdrawal](#cash-withdrawal)
    - [Incoming Payment](#incoming-payment)
    - [Outgoing Payment Not Accepted by Remote Party Yet](#outgoing-payment-not-accepted-by-remote-party-yet)
    - [Outgoing Payment Accepted by Target Institution](#outgoing-payment-accepted-by-target-institution)
    - [Outgoing Payment Rejected by Target Institution](#outgoing-payment-rejected-by-target-institution)
    - [Transfer from one account to another](#transfer-from-one-account-to-another)
  - [Event Data Objects in DynamoDB](#event-data-objects-in-dynamodb)
  - [Transaction Data in DynamoDB](#transaction-data-in-dynamodb)
- [Implementation](#implementation)
  - [Deploying the DynamoDB Stack](#deploying-the-dynamodb-stack)
  - [Deploying the New Event S3 Bucket Resources](#deploying-the-new-event-s3-bucket-resources)
- [Learnings and Discoveries](#learnings-and-discoveries)
  - [S3 SNS Notifications - Data Structures](#s3-sns-notifications---data-structures)
    - [Message of a S3 Create Type Event (PUT)](#message-of-a-s3-create-type-event-put)
    - [Message of a S3 Remove Type Event (DELETE)](#message-of-a-s3-remove-type-event-delete)

# Lab 4 Goals

The aim for this lab is to see if Athena is suitable to query events in S3. From [Lab 3](../lab3-non-kinesis-example/README.md), the events are stored using JSON format, but I am not yet sure if this is a suitable format for Athena. It certainly [appears possible](https://docs.aws.amazon.com/athena/latest/ug/querying-JSON.html), but there is a lot I don't know going into this lab.

The basic scenario walk through:

1. Create events in JSON format, and include perhaps also different types of events (see how much a consistent structure matters).
2. The S3 bucket kicks of a Lambda function (via SNS) and the Lambda function just saves the data in a make-shift table in DynamoDB (I am not worried about technical details of the data - just basic persistence)
3. Take regular snapshots (time-in-point backup) of DynamoDB
4. At some point, restore to a point in time
5. ~~Use Athena to get all events that is required to be replayed~~ Use Athena with [S3 Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html) to get all events that is required to be replayed
6. Investigate how to best trigger these event objects to be processed again
7. Ensure that post replay the data is what it is supposed to look like (compare with the very last DynamoDB snapshot)

Another question I have would be to see if I can replay data from archives like Glacier. Athena [does not support](https://docs.aws.amazon.com/athena/latest/ug/other-notable-limitations.html) S3 glacier, so I need to consider how a process would look like to get archived objects back into play. Perhaps I need a second bucket that can act as a archive bucket, and then set-up some kind rule to delete objects after x days in the primary event bucket which in turn moves those items to the archive bucket with a life cycle rule to deep archive in the shortest possible time.

Another aspect to keep in mind is that S3 does not provide a list filter. You either list all the objects or you get a specific object. Traditionally it is best to also use a secondary service like DynamoDB to store the meta data around objects, so that you can query objects from DynamoDB and then retrieve the object data as required from S3. This will probably be a key in selecting only objects created after a certain point in time for event replay. Further more, the archive status can be tracked in DynamoDB in order to kick off processes to restore those objects to a normal storage tier for retrieval and replay.

# Initial Scenario Planning

## S3 Buckets

The following buckets will be created:

| Bucket Name                                | Glacier | Processing                                                                             | 
|--------------------------------------------|:-------:|----------------------------------------------------------------------------------------|
| `lab4-new-events-qpwoeiryt`                | No      | Delete key after 1 day. Delete action triggers Lambda to move data to archive bucket   |
| `lab4-new-events-inventory-qpwoeiryt`      | No      |                                                                                        |
| `lab4-archive-events-qpwoeiryt`            | Yes     | Move to glacier class after 3 days (if possible)                                       |
| `lab4-archive-events-inventory-qpwoeiryt`  | No      |                                                                                        |
| `lab4-rejected-events-qpwoeiryt`           | Yes     | Move to glacier class after 3 days (if possible)                                       |
| `lab4-rejected-events-inventory-qpwoeiryt` | No      |                                                                                        |

Any transaction that failed, for example due to insufficient funds, goes to the `rejected` bucket.

The SNS topic from the `lab4-new-events-qpwoeiryt` bucket streams into a FIFO SQS Queue.

## Event Data

Originally I though about just using random data, but perhaps it is better to use something practical that can also much easier assist with determining the test cases. One example is to consider simple bank accounts. Events can be either:

* Cash Deposit (increases balance of account)
* Cash Withdrawal (decrease balance of account)
* Incoming Payment (for example salary) (increases balance of account)
* Transfer from one account to another (balance in first account decreases and in the second account increases)


### Cash Deposit Event

Key structure: `cash_deposit_<<request-id>>.event`

Effect on Available Balance: None

```json
{
    "EventTimeStamp": 1234567890,
    "TargetAccount": "<<account number>>",
    "Amount": "123.45",
    "LocationType": "ATM or Teller",
    "Reference": "Some Free Form Text",
    "Verified": false,
    "Currency": [
        "100-euro-bills": 1,
        "20-euro-bills": 1,
        "1-euro-bills": 3,
        "20-cents": 2,
        "5-cents": 1
    ]
}
```

### Verify Cash Deposit Event

Key structure: `verify_cash_deposit_<<request-id>>.event`

Effect on Available Balance: Increase Balance by `Amount`

```json
{
    "EventTimeStamp": 1234567890,
    "TargetAccount": "<<account number>>",
    "Amount": "123.40",
    "LocationType": "ATM or Teller",
    "Reference": "Some Free Form Text",
    "Verified": true,
    "VerifiedCurrency": [
        "100-euro-bills": 1,
        "20-euro-bills": 1,
        "1-euro-bills": 3,
        "20-cents": 2
    ],
    "VerifiedByEmployeeId": "1234567890",
    "FinalFinding": "5 cents was from incorrect currency and rejected. The coins were returned to the customer."
}
```

### Cash Withdrawal

Key structure: `cash_withdrawal_<<request-id>>.event`

Effect on Available Balance: Decrease Balance by `Amount`

Business Rules:

* Balances cannot go below 0 after withdrawal

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "Amount": "200.00",
    "LocationType": "ATM or Teller",
    "Reference": "Some Free Form Text",
    "Currency": [
        "50-euro-bills": 4
    ]
}
```

### Incoming Payment

Key structure: `incoming_payment_<<request-id>>.event`

Effect on Available Balance: Increase Balance by `Amount`

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "Amount": "123.45",
    "SourceInstitution": "Source Bank",
    "SourceAccount": "Source Account Number",
    "Reference": "Some Free Form Text"
}
```

### Outgoing Payment Not Accepted by Remote Party Yet

Key structure: `outgoing_payment_unverified_<<request-id>>.event`

Effect on Available Balance: Decrease Balance by `Amount`

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "Amount": "123.45",
    "TargetInstitution": "Source Bank",
    "TargetAccount": "Source Account Number",
    "Reference": "Some Free Form Text"
}
```

### Outgoing Payment Accepted by Target Institution

Key structure: `outgoing_payment_verified_<<request-id>>.event`

Effect on Available Balance: None

_**Note**_: The `<<request-id>>` corresponds to the original request ID for the `unverified` event.

```json
{
    "EventTimeStamp": 1234567890
}
```

### Outgoing Payment Rejected by Target Institution

Key structure: `outgoing_payment_rejected_<<request-id>>.event`

_**Note**_: The `<<request-id>>` corresponds to the original request ID for the `unverified` event.

Effect on Available Balance: Increase Balance by `RejectedAmount`

```json
{
    "EventTimeStamp": 1234567890,
    "Reason": "Incorrect account number (account not found)",
    "RejectedAmount": "123.45"
}
```

### Transfer from one account to another

Key structure: `inter_account_transfer_<<request-id>>.event`

Effect on Available Balance: 

* Increase Balance by `Amount` on Target Account
* Decrease Balance by `Amount` on Source Account

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "TargetAccount": "<<account number>>",
    "Amount": "123.45",
    "Reference": "Some Free Form Text"
}
```

## Event Data Objects in DynamoDB

Table Name: `lab4_event_objects_qweriuyt`

```text
+----------------------------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| Primary Key                                                                      | Attributes                                                                                                  |
+-------------------------+--------------------------------------------------------+                                                                                                             |
| Partition Key (PK)      | Sort Key (ST) Type: NUMBER                             |                                                                                                             |
| Name: PK                | Name: SK                                               |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
|                         |                                                        |                                                                                                             |
| KEY#<<object-key>>      | STATE                                                  | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |                                                        | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - InEventBucket  (BOOL)                                                                                     |
|                         |                                                        | - InArchiveBucket  (BOOL)                                                                                   |
|                         |                                                        | - InRejectedBucket  (BOOL - note: rejected events won't be in the archive bucket)                           |
|                         |                                                        | - AccountNumber  (STRING)                                                                                   |
|                         |                                                        | - Processed  (BOOL, default=false)                                                                          |
|                         |                                                        |                                                                                                             |
| KEY#<<object-key>>      | EVENT<<timestamp>>                                     | - EventType (InitialEvent|ArchiveEvent|RejectEvent|...)                                                     |
|                         |                                                        | - ErrorState (BOOL)                                                                                         |
|                         |                                                        | - ErrorReason (STRING)                                                                                      |
|                         |                                                        | - NextAction (STRING)                                                                                       |
|                         |                                                        | - AccountNumber  (STRING)                                                                                   |
|                         |                                                        |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
```

Global Secondary Indexes:

```text
+-------------------------------------------------------------------------+------------------------+
| Primary Key                                                             | Index Name             |
+---------------------------------+---------------------------------------|                        |
| Partition Key (PK)              | Sort Key (ST) Attribute               |                        |
+---------------------------------+---------------------------------------+------------------------+
| AccountNumber                   | SK                                    | AccountNumberIdx       |
+---------------------------------+---------------------------------------+------------------------+
```

## Transaction Data in DynamoDB

Table Name: `lab4_bank_accounts_qweriuyt`

```text
+----------------------------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| Primary Key                                                                      | Attributes                                                                                                  |
+-------------------------+--------------------------------------------------------+                                                                                                             |
| Partition Key (PK)      | Sort Key (ST) Type: NUMBER                             |                                                                                                             |
| Name: PK                | Name: SK                                               |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
|                         |                                                        |                                                                                                             |
| <<account-number>>      | TRANSACTIONS#PENDING#<<event-key>>                     | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |                                                        | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - EventKey (STRING, links to <<object-key>>)                                                                |
|                         |                                                        | - EventRawData (String, containing JSON of original transaction)                                            |
|                         |                                                        | - Amount (Number)                                                                                           |
|                         |                                                        |                                                                                                             |
| <<account-number>>      | TRANSACTIONS#VERIFIED#<<event-key>>                    | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |                                                        | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - EventKey (STRING, links to <<object-key>>)                                                                |
|                         |                                                        | - EventRawData (String, containing JSON of original transaction)                                            |
|                         |                                                        | - Amount (Number)                                                                                           |
|                         |                                                        |                                                                                                             |
| <<account-number>>      | SAVINGS#BALANCE#<type>>#<<customer-number>>            | - LastTransactionDate (NUMBER, format YYYYMMDD)                                                             |
|                         |    Types: ACTUAL or AVAILABLE                          | - LastTransactionTime (NUMBER, format HHMMSS)                                                               |
|                         |                                                        | - LastEventKey (STRING, links to <<object-key>>)                                                            |
|                         |                                                        | - Balance (Number)                                                                                          |
|                         |                                                        |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
```

Global Secondary Indexes:

```text
+-------------------------------------------------------------------------+------------------------+
| Primary Key                                                             | Index Name             |
+---------------------------------+---------------------------------------|                        |
| Partition Key (PK)              | Sort Key (ST) Attribute               |                        |
+---------------------------------+---------------------------------------+------------------------+
| EventKey                        | SK                                    | EventKeyIdx            |
+---------------------------------+---------------------------------------+------------------------+
```

Notes:

* The `SAVINGS#BALANCE` balances reflect the balance of all `TRANSACTIONS#VERIFIED` transactions. Unverified transactions does not yet influence the final balance.
* The Available balance is the balance available for transactions. 
* It should be accepted that any cash will only be released once the transaction is a `TRANSACTIONS#VERIFIED` type transaction.

# Implementation

When running commands, the following environment variables are assumed to be set:

| Environment Variable Example                        | Description                                                                                                          |
|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `export AWS_PROFILE="..."`                          | The AWS Credentials Profile to use                                                                                   |
| `export AWS_REGION="..."`                           | The AWS Region to deploy resources to                                                                                |
| `export ARTIFACT_S3_BUCKET_NAME="..."`              | The S3 Bucket name containing any additional artifacts                                                               |
| `export S3_BUCKET_STACK_NAME="..."`                 | The CloudFormation stack name for deploying New Event Bucket Resources                                               |
| `export NEW_EVENT_BUCKET_NAME_PARAM="..."`          | The S3 bucket name for new events                                                                                    |
| `export ARCHIVE_EVENT_BUCKET_NAME_PARAM="..."`      | The S3 bucket name for events archives                                                                               |
| `export ARCHIVE_INVENTORY_BUCKET_NAME_PARAM="..."`  | The S3 bucket name for events archive bucket inventory                                                               |
| `export DYNAMODB_OBJECT_TABLE_NAME_PARAM="..."`     | The DynamoDB Table name for event artifact tracking                                                                  |
| `export DYNAMODB_ACCOUNTS_TABLE_NAME_PARAM="..."`   | The DynamoDB Table name for transactions and accounts                                                                |

## Deploying the DynamoDB Stack

Deploy the stack with the following command:

```shell
# Deploy
```

## Deploying the New Event S3 Bucket Resources

First, prepare the Lambda function source files and upload to the relevant source code bucket. Then deploy the stack:

```shell
rm -vf labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_create/s3_new_event_bucket_object_create.zip
cd labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_create/ && zip s3_new_event_bucket_object_create.zip s3_new_event_bucket_object_create.py && cd $OLDPWD 
aws s3 cp labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_create/s3_new_event_bucket_object_create.zip s3://$ARTIFACT_S3_BUCKET_NAME/s3_new_event_bucket_object_create.zip

rm -vf labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_delete/s3_new_event_bucket_object_delete.zip
cd labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_delete/ && zip s3_new_event_bucket_object_delete.zip s3_new_event_bucket_object_delete.py && cd $OLDPWD 
aws s3 cp labs/lab4-athena-query-s3-events/lambda_functions/s3_new_event_bucket_object_delete/s3_new_event_bucket_object_delete.zip s3://$ARTIFACT_S3_BUCKET_NAME/s3_new_event_bucket_object_delete.zip

aws cloudformation deploy \
    --stack-name $S3_BUCKET_STACK_NAME \
    --template-file labs/lab4-athena-query-s3-events/cloudformation/2000-s3-buckets.yaml \
    --parameter-overrides S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
        NewEventBucketNameParam="$NEW_EVENT_BUCKET_NAME_PARAM" \
        ArchiveBucketNameParam="$ARCHIVE_EVENT_BUCKET_NAME_PARAM" \
        ArchiveInventoryBucketNameParam="$ARCHIVE_INVENTORY_BUCKET_NAME_PARAM" \
    --capabilities CAPABILITY_NAMED_IAM
```

# Learnings and Discoveries

> _**Note**_: While I'm busy with the Lab, this section will evolve as I learn or discover new things. Some of my notes may include knowledge I already had, but I will not make the distinction and I will still echo those thoughts here for context and to ensure that others using this resource can also benefit from these extra pieces of knowledge.

This lab is about the operational processes required that will allow us to recover a DynamoDB Database to a point in time and then replay events in the event bucket after that recovery time (using some "last event" indicator).

The first thought I had after thinking about the initial design was that there are two distinct approaches in recovery:

1. Recovery of much older events, where these events are in inventory records and archive buckets.
2. Recovery of more recent events, where those events may not necessarily be in an inventory file (inventory bucket), but they should be in the DynamoDB table tracking event/inventory files.

At this point, I should also point out that there should be an operational process to stop new events from being generated until the recovery process is complete. This is not ideal as this will demand downtime. One strategy that I will explore is the introduction of daily (or even hourly) summary processes that generates like a point in time snapshot of the state of an account. When recovery is in progress, two things should be noted, assuming the state snapshot is in-tact and trusted to be correct:

1. New events can still be processed, using the last good snapshot as a starting reference, for example to calculate the latest account balance
2. Old events in the process of being recovered and replayed, must only include events before and up to the last known snapshot.

I assume there may be some process to ensure that the recovered and replayed events end with the same state as the last known good snapshot state (i.e. account starting balance from the last known good snapshot should match with the balance calculate from all older events leading up to that point in time).

## S3 SNS Notifications - Data Structures

When the Lambda function ultimately receives an event, the first level structure is a SQS structure and has the following structure:

```json
{
    "Records": [
        {
            "messageId": "36117b2c-afd6-4d73-98e1-248fbbd41cf5",
            "receiptHandle": "...",
            "body": "...",
            "attributes": {
                "ApproximateReceiveCount": "1",
                "SentTimestamp": "1667973667951",
                "SenderId": "...",
                "ApproximateFirstReceiveTimestamp": "1667973667953"
            },
            "messageAttributes": {},
            "md5OfBody": "2354d8a23817f58fde75c781dc12322b",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:eu-central-1:000000000000:S3NewEventStoreNotificationQueue",
            "awsRegion": "eu-central-1"
        }
    ]
}
```

The `Records[].body` field, contains more detail about the SNS message send to the SQS queue and has the following structure:

```json
{
    "Type": "Notification",
    "MessageId": "...",
    "TopicArn": "arn:aws:sns:eu-central-1:000000000000:S3NewEventStoreNotification",
    "Subject": "Amazon S3 Notification",
    "Message": "...",
    "Timestamp": "2022-11-09T06:01:07.921Z",
    "SignatureVersion": "1",
    "Signature": "...",
    "SigningCertURL": "...",
    "UnsubscribeURL": "..."
}
```

The `Message` field contains the actual S3 event

### Message of a S3 Create Type Event (PUT)

```json
{
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "eu-central-1",
            "eventTime": "2022-11-09T06:01:06.967Z",
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "AWS:..."
            },
            "requestParameters": {
                "sourceIPAddress": "n.n.n.n"
            },
            "responseElements": {
                "x-amz-request-id": "...",
                "x-amz-id-2": "..."
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "...",
                "bucket": {
                    "name": "lab4-new-events-qpwoeiryt",
                    "ownerIdentity": {
                        "principalId": "..."
                    },
                    "arn": "arn:aws:s3:::lab4-new-events-qpwoeiryt"
                },
                "object": {
                    "key": "some_file.txt",
                    "size": 119985,
                    "eTag": "b3a671cd395478ee9c78be33740381c4",
                    "sequencer": "00636B4222CBA01ADB"
                }
            }
        }
    ]
}
```

### Message of a S3 Remove Type Event (DELETE)

```json
{
    "Records": [
        {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "eu-central-1",
            "eventTime": "2022-11-09T06:03:46.412Z",
            "eventName": "ObjectRemoved:Delete",
            "userIdentity": {
                "principalId": "AWS:..."
            },
            "requestParameters": {
                "sourceIPAddress": "n.n.n.n"
            },
            "responseElements": {
                "x-amz-request-id": "...",
                "x-amz-id-2": "..."
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "...",
                "bucket": {
                    "name": "lab4-new-events-qpwoeiryt",
                    "ownerIdentity": {
                        "principalId": "..."
                    },
                    "arn": "arn:aws:s3:::lab4-new-events-qpwoeiryt"
                },
                "object": {
                    "key": "some_file.txt",
                    "sequencer": "00636B42C26391BE2F"
                }
            }
        }
    ]
}
```
