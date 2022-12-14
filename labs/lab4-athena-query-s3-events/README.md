
- [Lab 4 Goals](#lab-4-goals)
- [Initial Scenario Planning](#initial-scenario-planning)
  - [Security Notes](#security-notes)
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
  - [Restoring / Recovery Planning and Thinking](#restoring--recovery-planning-and-thinking)
    - [Points of Failure/Restore](#points-of-failurerestore)
  - [AWS Infrastructure](#aws-infrastructure)
    - [Triggering Step Functions from SQS FIFO Queue (Design Strategy)](#triggering-step-functions-from-sqs-fifo-queue-design-strategy)
- [Implementation](#implementation)
  - [Deploying the DynamoDB Stack](#deploying-the-dynamodb-stack)
  - [Deploying the New Event S3 Bucket Resources](#deploying-the-new-event-s3-bucket-resources)
  - [Deploying the Transaction Processing Resources](#deploying-the-transaction-processing-resources)
- [Learnings and Discoveries](#learnings-and-discoveries)
  - [S3 SNS Notifications - Data Structures](#s3-sns-notifications---data-structures)
    - [Message of a S3 Create Type Event (PUT)](#message-of-a-s3-create-type-event-put)
    - [Message of a S3 Remove Type Event (DELETE)](#message-of-a-s3-remove-type-event-delete)
  - [DynamoDB](#dynamodb)
  - [Operational Processes involving Restoring Services and Applying Point-In-Time Recovery with Event Replay](#operational-processes-involving-restoring-services-and-applying-point-in-time-recovery-with-event-replay)

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

> _**Update 2022-12-05**_: The goals are not changing, but I am rethinking my whole approach, as I learn more about some of the theory behind events and data processing. This README will probably undergo significant updates in the following days. Some information may not be relevant, and I will update, add and remove as I go - please keep this in mind if you are at all following my progress for some reason.

# Initial Scenario Planning

## Security Notes

The implementation and sample code cannot be considered secure. There are numerous known issues, including:

* A complete lack of authorization (all events are assumed to be properly authorized by the time the event data file is created)
* The event sequence numbers are sequential, instead of being a random number (best practices deviation)
* There are an absolute minimum amount of data validation. The focus is on event recovery and replay and not on code or logic purity and absolute correctness
* The AWS policies to resources will be tighter in production scenarios
* Proper audit trail logs have not been considered (considered out of scope in terms of the experiment goals) 

## S3 Buckets

In this example, I use the S3 buckets as a collector for the event data into data files, where each file represents an event that happened - in this case some financial transaction.

At this stage, the event has not yet been processed. Therefore, the event represents a "request" to perform a transaction without any validation having being done yet. For example, a request to withdraw cash will include all the relevant information to perform the action, but we do not know yet simple things, like does the account even exist and if it does, is there available funds?

My reasoning for using this technique is to have some concrete repository containing all the original events that can be used to replay events in order to recover from some critical error. Once the transaction has been processed, the event data file will be moved to an archive folder, where it will go through the AWS S3 life cycle rules where it will eventually be archived in AWS Glacier. This is a nice solution in my opinion, as it provides a really affordable long term reliable archive of ALL events. Historical data can easily be send to other S3 buckets where additional processing, like data analytics or fraud detection analysis, can be run. Another great use case is when a new analytical system is used, you will have the ability to re-run all old events in order to either gain some new insight or even use the old data as training data for AI/ML.

The following buckets will be created:

| Bucket Name                                     | Glacier | Processing                                                                             | 
|-------------------------------------------------|:-------:|----------------------------------------------------------------------------------------|
| `lab4-new-events-v2`                            | No      | Delete key after 1 day. Delete action triggers Lambda to move data to archive bucket   |
| `lab4-archive-events-v2`                        | Yes     | Move to glacier class after 3 days (if possible)                                       |
| `lab4-archive-events-inventory-v2`              | No      |                                                                                        |
| `lab4-rejected-events-v2`                       | Yes     | Move to glacier class after 3 days (if possible)                                       |
| `lab4-rejected-events-inventory-v2`             | No      |                                                                                        |
| `lab4-transaction-commands-v2`                  | Yes     | Move to glacier class after 3 days (if possible)                                       |
| `lab4-transaction_commands-inventory-v2`        | No      |                                                                                        |


Any transaction that failed, for example due to insufficient funds, goes to the `rejected` bucket. The ide is that events in this bucket should not be re-run in a disaster recovery scenario, as we already know that these events will fail based on business logic error, time sensitive transaction errors etc.

When all transactions are persisted in the accounts table in DynamoDB, the database command(s) are written to another bucket called `lab4-transaction-commands-xxx`. This is the 1st tier "backup" that will be used in order to restore account data. However, if errors (like missing data) is detected, a fallback will be to rerun from the original which by now would be in the `lab4-archive-events-xxx` bucket. The major difference between using these two data restore sources is that the transaction commands archive does not have to deal with any logic or processing - it is simply re-running all DynamoDB commands to restore data. In contrast, processing from the original event data requires some caution, as we do not want to again perform certain operations, for example calling an external party required to complete a transaction (think about third party payments as an example - they have already being paid, so we are only interested in restoring the DynamoDB commands and not do the external payment again, effectively paying them twice!).

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
    "Currency": {
        "100-euro-bills": 1,
        "20-euro-bills": 1,
        "1-euro-bills": 3,
        "20-cents": 2,
        "5-cents": 1
    },
    "CustomerNumber": "<<customer number>>"
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
    "PreviousRequestIdReference": "<<request-id>>",
    "Verified": true,
    "VerifiedCurrency": {
        "100-euro-bills": 1,
        "20-euro-bills": 1,
        "1-euro-bills": 3,
        "20-cents": 2
    },
    "VerifiedByEmployeeId": "1234567890",
    "FinalFinding": "5 cents was from incorrect currency and rejected. The customer was informed that the coins are available for collection at the branch.",
    "CustomerNumber": "<<customer number>>"
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
    "Currency": {
        "50-euro-bills": 4
    },
    "CustomerNumber": "<<customer number>>"
}
```

### Incoming Payment

Key structure: `incoming_payment_<<request-id>>.event`

Effect on Available Balance: Increase Balance by `Amount`

```json
{
    "EventTimeStamp": 1234567890,
    "TargetAccount": "<<account number>>",
    "Amount": "123.45",
    "SourceInstitution": "Source Bank",
    "SourceAccount": "Source Account Number",
    "Reference": "Some Free Form Text",
    "CustomerNumber": "<<customer number>>"
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
    "Reference": "Some Free Form Text",
    "CustomerNumber": "<<customer number>>"
}
```

### Outgoing Payment Accepted by Target Institution

Key structure: `outgoing_payment_verified_<<request-id>>.event`

Effect on Available Balance: None

_**Note**_: The `<<request-id>>` corresponds to the original request ID for the `unverified` event.

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "Reference": "Some Free Form Text",
    "PreviousRequestIdReference": "<<request-id>>",
    "CustomerNumber": "<<customer number>>"
}
```

### Outgoing Payment Rejected by Target Institution

Key structure: `outgoing_payment_rejected_<<request-id>>.event`

_**Note**_: The `<<request-id>>` corresponds to the original request ID for the `unverified` event.

Effect on Available Balance: Increase Balance by `RejectedAmount`

```json
{
    "EventTimeStamp": 1234567890,
    "SourceAccount": "<<account number>>",
    "Reason": "Incorrect account number (account not found)",
    "PreviousRequestIdReference": "<<request-id>>",
    "CustomerNumber": "<<customer number>>"
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
    "Reference": "Some Free Form Text",
    "CustomerNumber": "<<customer number>>"
}
```

## Event Data Objects in DynamoDB

Table Name: `lab4_event_objects_v1`

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
| KEY#<<object-key>>      | EVENT#<<timestamp>>                                    | - EventType (InitialEvent|ArchiveEvent|RejectEvent|...)                                                     |
|                         |                                                        | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |                                                        | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - ErrorState (BOOL)                                                                                         |
|                         |                                                        | - ErrorReason (STRING)                                                                                      |
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

Table Name: `lab4_accounts_v1`

```text
+----------------------------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
| Primary Key                                                                      | Attributes                                                                                                  |
+-------------------------+--------------------------------------------------------+                                                                                                             |
| Partition Key (PK)      | Sort Key (ST) Type: NUMBER                             |                                                                                                             |
| Name: PK                | Name: SK                                               |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
|                         |                                                        |                                                                                                             |
| <<account-number>>      | TRANSACTION#<<type>>#<<event-key>>                     | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |   Types: PENDING, VERIFIED or REVERSAL                 | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - EventKey (STRING, links to <<object-key>>)                                                                |
|                         |                                                        | - EventRawData (String, containing JSON of original transaction)                                            |
|                         |                                                        | - Amount (Number)                                                                                           |
|                         |                                                        | - TransactionType (String)                                                                                  |
|                         |                                                        | - RequestId (String)                                                                                        |
|                         |                                                        | - PreviousRequestIdReference (String, default="n/a")                                                        |
|                         |                                                        | - EffectOnActualBalance (String) (Either "None", "Increase" or "Decrease" with "Amount")                    |
|                         |                                                        | - EffectOnAvailableBalance (String) (Either "None", "Increase" or "Decrease" with "Amount")                 |
|                         |                                                        | - BalanceActual (Number) (value in CENTS)                                                                   |
|                         |                                                        | - BalanceAvailable (Number) (value in CENTS)                                                                |
|                         |                                                        | - StatementIdentifier (String) (Default: date format YYYYMM)                                                |
|                         |                                                        | - CustomerNumber (String)                                                                                   |
|                         |                                                        | - TransactionSequence (Number) (Increments with each new record. Start at "1")                              |
|                         |                                                        |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
```

Global Secondary Indexes:

```text
+-------------------------------------------------------------------------+---------------------------------+
| Primary Key                                                             | Index Name                      |
+---------------------------------+---------------------------------------|                                 |
| Partition Key (PK)              | Sort Key (ST) Attribute               |                                 |
+---------------------------------+---------------------------------------+---------------------------------+
| EventKey                        | SK                                    | EventKeyIdx                     |
| StatementIdentifier             | SK                                    | StatementIdentifierIdx          |
| CustomerNumber                  | SK                                    | CustomerNumberIdx               |
+---------------------------------+---------------------------------------+---------------------------------+
```

> _**Update 2022-12-06**_: The table has been updated to show only a single line entry for each transaction processed, and balances are maintained with each new line entry. I have also added a statement field, which in this case aligns with the year and month, therefore all transaction for a givin month will appear on that months statement. In this example, this saves on batch processing to generate statements, but keep in mind that there are numerous approaches to this feature.

## Restoring / Recovery Planning and Thinking

### Points of Failure/Restore

Failures leading to some kind of restoring/recovering operationally can happen at various points in the key transactional process pipeline.

![Pipeline](../../images/design-Lab_4-Transactional-Pipeline.drawio.png)

From the diagram, the following errors could occur:

| Scenario Number | Infrastructure Affected          | Type / Description of Error                                                                                                                                                                                                                       | Impact                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|:---------------:|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1               | (1) New Events Buckets           | Not all events get created because of an error further upstream, for example a certain channel, like Internet Banking, having an issue.                                                                                                           | Think of a transaction being done on an account on more than one channel, but one channel has an issue and it's events does not get created in S3 immediately. Eventually they may get created, or not at all. However, at a point in time after the failure more transactions processed from other channels may still accumulate affecting balances and various other business rules, and it is therefore important to have some kind of mechanism to disregard events from the broken channel once they are created (but no longer needing to be processed). It can be assumed that all events from the problematic channel can be ignored until service is fully restored. However, some transactions may have been processed in error, which means that the accounts table have to be restored to a point in time as well, and all events except events from the problematic channel must be replayed in order to reflect the true state of each account. |
| 2               | (2 - 4) AWS Service Interruption | Worst case is where only some of the S3 events trigger messages being send via SNS/SQS.                                                                                                                                                           | When such a scenario occurs, the end result may be very similar to scenario 1, even though all channels do actually work and all events are created successfully in S3. In this scenario the recovery is best to first halt all transaction processing and then restore the DynamoDB table to a point in time where it can be confirmed all transactions was still processed successfully. Then, when te AWS services are restored, the processing lambda function needs to be put into some kind of replay mode to only allow replay of S3 events after a point in time (the restore point of the DynamoDB table). Once all transactions have been caught up, the normal operational processes can start again. It is probably a good idea to stop all channels from generating new events at this point.                                                                                                                                                    |
| 3               | (5) Object DB                    | Perhaps a service issue on DynamoDB?                                                                                                                                                                                                              | The effect is that even though all S3 events are created and generate the appropriate downstream events, some transactions can not be committed to the Object DB. The transactional processing also relies on this service in order to validate certain elements and for status updates. Handling of this issue should be handled the same way as scenario 2.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 4               | (6) SQS FIFO Queue               | Depending on upstream issues, some messages older than 5 minutes may not be recognized as duplicates. Also, SQS Service Failure.                                                                                                                  | Downstream, the message processing may fail and since the SQS FIFO queue has no concept for a dead letter queue, the logic has be be maintained downstream. Some form of reconciliation may be required to ensure all events received was processed at some point, with optionally some additional processing to handle old (stale) events.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 5               | (7) Lambda Function              | Exceptions, validation failures, corrupt data etc.                                                                                                                                                                                                | Failures in event processing should spawn some additional queued messages, potentially in an alternative queue. Also, updates in DynamoDB is not always guaranteed, and a reconciliation process may be required (similar to the previous point).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 6               | (8) Account DB                   | Insert/Update fails, especially when multiple calls to the DB is required (event entry and balance adjustment, for example).                                                                                                                      | Some transactions could potentially only be partially completed. Also, since this is an eventual consistent DB, there is no reliable way for the Lambda function to really know the transaction was successfully committed to the DB in full. The DB commit reliability and error detection/correction is a little beyond the scope of this experiment, but for this experiment, we assume we somehow detected the error and now some events need to be replayed in order to correct the errors.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 7               | (9) SQS Cleanup Queue            | SQS Service Failure                                                                                                                                                                                                                               | Any failures from this point further downstream can be fixed independently of transaction fixing, assuming the transactions are properly recorded in the accounts DB. Complication arise when events need to be replayed, while there are also unresolved errors at this point onward.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

From what I can see, it is crucial for the Transaction Processing Lambda functions (7) to know the state of the pipeline and account before proceeding with the transaction.

> _**Important**_: Not all failures will lead to the whole system needed be stopped to resolve an error. Some problems, for example in DynamoDB, will lead to this scenario where everything has to suspend operations until the database is available again. However, sometimes only one particular account has an issue (inconsistency perhaps?), while will require a lock on operations only for that account, while all other transactions are processed as per normal. Therefore, operational processes have to run within a certain context, knowing what the scope of the problem is.

I am going to experiment with [AWS Elastic Cache Global Datastore Service](https://www.amazonaws.cn/en/elasticache/global-datastore/) as a pipeline state cache.

## AWS Infrastructure

![AWS Architecture](../../images/design-Lab4-AWS_Architecture.drawio.png)

Adding elastic cache will require the Lambda functions to also be deployed in a VPC in order for all the Security Groups to be properly set-up to allow access from the Lambda Functions to the Redis Cache.

The Redis Cache will be used as a state repository and will control two types of state:

1. Global state, which will either allow transaction processing or not
2. Account level state, which allows transaction processing on individual account level.

TODO - `I still have to work out a lot of the implementation details`

### Triggering Step Functions from SQS FIFO Queue (Design Strategy)

AWS Step Functions cannot directly subscribe to SQS, and therefore we will need another Lambda function to act as a proxy (`lab4_transaction_init` Lambda function).

Since the SQS queue is a FIFO queue bound to the Account Number (the message group ID), it will guarantee transactions per account are processed one at a time in the correct order. 

However, since the proxy has to wait for the transaction logic to complete before removing the message from the queue, the step function needs to be executed synchronously.

The proxy function is therefore extremely basic: it will get a message from the queue and then call the step function and wait for a result before removing the message from the queue. A timeout should generate an exception so that the transaction can be retried. However, the entire system needs to be aware of the timeout, and I still need to think about how to deal with transactions to third parties that time out, even though those transactions may end being received successfully at the remote service end-point. Perhaps a decoupled queue would work, and we assume the event was submitted successfully to the remote third party until we can verify otherwise.

# Implementation

When running commands, the following environment variables are assumed to be set:

| Environment Variable Example                        | Description                                                                                                          |
|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `export AWS_PROFILE="..."`                          | The AWS Credentials Profile to use                                                                                   |
| `export AWS_REGION="..."`                           | The AWS Region to deploy resources to                                                                                |
| `export ARTIFACT_S3_BUCKET_NAME="..."`              | The S3 Bucket name containing any additional artifacts                                                               |
| `export S3_BUCKET_STACK_NAME="..."`                 | The CloudFormation stack name for deploying New Event Bucket Resources                                               |
| `export DYNAMODB_STACK_NAME="..."`                  | The CloudFormation stack name for deploying DynamoDB Resources                                                       |
| `export TX_PROCESSING_STACK_NAME="..."`             | The CloudFormation stack name for deploying Resources to support Transaction Processing                              |
| `export NEW_EVENT_BUCKET_NAME_PARAM="..."`          | The S3 bucket name for new events                                                                                    |
| `export ARCHIVE_EVENT_BUCKET_NAME_PARAM="..."`      | The S3 bucket name for events archives                                                                               |
| `export ARCHIVE_INVENTORY_BUCKET_NAME_PARAM="..."`  | The S3 bucket name for events archive bucket inventory                                                               |
| `export DYNAMODB_OBJECT_TABLE_NAME_PARAM="..."`     | The DynamoDB Table name for event artifact tracking                                                                  |
| `export DYNAMODB_ACCOUNTS_TABLE_NAME_PARAM="..."`   | The DynamoDB Table name for transactions and accounts                                                                |

## Deploying the DynamoDB Stack

Deploy the stack with the following command:

```shell
aws cloudformation deploy \
    --stack-name $DYNAMODB_STACK_NAME \
    --template-file labs/lab4-athena-query-s3-events/cloudformation/1000-dynamodb.yaml \
    --parameter-overrides ObjectTableNameParam="$DYNAMODB_OBJECT_TABLE_NAME_PARAM" \
        AccountTableNameParam="$DYNAMODB_ACCOUNTS_TABLE_NAME_PARAM"
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
        DynamoDbStackNameParam="$DYNAMODB_STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM
```

## Deploying the Transaction Processing Resources

Run the following commands:

```shell
rm -vf labs/lab4-athena-query-s3-events/lambda_functions/tx_processing_consumer/tx_processing_consumer.zip
cd labs/lab4-athena-query-s3-events/lambda_functions/tx_processing_consumer/ && zip tx_processing_consumer.zip tx_processing_consumer.py && cd $OLDPWD 
aws s3 cp labs/lab4-athena-query-s3-events/lambda_functions/tx_processing_consumer/tx_processing_consumer.zip s3://$ARTIFACT_S3_BUCKET_NAME/tx_processing_consumer.zip

aws cloudformation deploy \
    --stack-name $TX_PROCESSING_STACK_NAME \
    --template-file labs/lab4-athena-query-s3-events/cloudformation/3000-transaction_processing_resources.yaml \
    --parameter-overrides S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
        DynamoDbStackNameParam="$DYNAMODB_STACK_NAME" \
        TransactionProcessingLambdaFunctionSrcZipParam="tx_processing_consumer" \
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

> _**Important**_: I noticed several examples of S3 events not being generated. ~~This seems to be mostly when an existing key is deleted and then `PUT` again. From some reason, the subsequent `PUT` of the same object does not create corresponding events. Further investigation may be required.~~ Further investigation revealed that the S3 events were generated, and the messages was successfully processed and passed on the to SQS FIFO queue, which in turn responded with a `200`. However, the queue counters were never increased and the message was never delivered to the Transaction Processing Lambda function. I suspect the old/original transaction was somehow still visible to the FIFO queue and the subsequent messages was therefore seen as duplicate, which was then rejected my SQS. The [AWS Documentation](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/using-messagededuplicationid-property.html) states that "_Amazon SQS has a deduplication interval of 5 minutes_" and I can see from the timestamps that this may be the reason indeed.

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
                    "name": "lab4-new-events-v2",
                    "ownerIdentity": {
                        "principalId": "..."
                    },
                    "arn": "arn:aws:s3:::lab4-new-events-v2"
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
                    "name": "lab4-new-events-v2",
                    "ownerIdentity": {
                        "principalId": "..."
                    },
                    "arn": "arn:aws:s3:::lab4-new-events-v2"
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

## DynamoDB

~~Only Local Secondary Indexes support consistent reads. In the context of the application, this was important. As a result, I decided not to add local indexes, but to rely on primary key queries with filters, using consistent reads.~~

The DynamoDB COnsistent Read story is still problematic for me. I have abandoned the Local Index idea as it did not serve the intended purpose (had to do with the fact that it must have the same partition key as the table - I wanted a different partition key).

After I concluded basic functional testing, I cleared the bucket and ran all transactions again. However, I noticed the final balance was wrong and upon further investigation I found that the transactions verifying a previous transaction were all failing because the lookup of the previous transaction failed. It would appear that using a consistent read operation does not yield the intended result, as the previous transaction record (unverified transaction) was not yet available at the time of the read request.

After numerous scenarios and testing, I have concluded that some sleep time is required between a unverified event and a verified event referencing the previous event. For small data samples, 5 seconds seems to be perfectly fine. However, this sleep time should be kept in mind when replaying a lot of transactions (1000's?). This makes me start to think of solutions around replaying of events. It really looks like it depends from where you want to replay: either from the source event (S3) or will it be fine to record the DynamoDB events somehow and just replay those? Perhaps I should stream DynamoDB inserts/updates on a queue as well? Assuming these are all VERIFIED updates, the replay should not have to worry about any verification - just push the updates through...

## Operational Processes involving Restoring Services and Applying Point-In-Time Recovery with Event Replay

My initial assessment can be described as the following:

* There is a concept of a transactional pipeline where a transactional message flows through several components before finally and processed and the final transaction state is capture in the accounting table with the balances being updated.
* Infrastructure failures and other service interruptions can happen at any point in the transactional pipeline and may cause various issues requiring more than on approach to service recovery.
* A number of flags and other parameters are required to instruct the Lambda functions in the transactional pipeline what to process and what to ignore. It could be transaction from a specific channel must be ignored, or transaction for a specific account (or accounts) or everything.
* During a DynamoDB table restore a new table is created. Lambda functions therefore has to be instructed of the new tables somehow.
* At this early point already I can recognize that the operational processes also require additional scripts in order to orchestrate the recovery process.
