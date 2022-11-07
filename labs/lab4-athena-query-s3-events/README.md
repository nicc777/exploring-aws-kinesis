
- [Lab 4 Goals](#lab-4-goals)
- [Initial Scenario Planning](#initial-scenario-planning)
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

# Lab 4 Goals

The aim for this lab is to see if Athena is suitable to query events in S3. From [Lab 3](../lab3-non-kinesis-example/README.md), the events are stored using JSON format, but I am not yet sure if this is a suitable format for Athena. It certainly [appears possible](https://docs.aws.amazon.com/athena/latest/ug/querying-JSON.html), but there is a lot I don't know going into this lab.

The basic scenario walk through:

1. Create events in JSON format, and include perhaps also different types of events (see how much a consistent structure matters).
2. The S3 bucket kicks of a Lambda function (via SNS) and the Lambda function just saves the data in a make-shift table in DynamoDB (I am not worried about technical details of the data - just basic persistence)
3. Take regular snapshots (time-in-point backup) of DynamoDB
4. At some point, restore to a point in time
5. Use Athena to get all events that is required to be replayed
6. Investigate how to best trigger these event objects to be processed again
7. Ensure that post replay the data is what it is supposed to look like (compare with the very last DynamoDB snapshot)

Another question I have would be to see if I can replay data from archives like Glacier. Athena [does not support](https://docs.aws.amazon.com/athena/latest/ug/other-notable-limitations.html) S3 glacier, so I need to consider how a process would look like to get archived objects back into play. Perhaps I need a second bucket that can act as a archive bucket, and then set-up some kind rule to delete objects after x days in the primary event bucket which in turn moves those items to the archive bucket with a life cycle rule to deep archive in the shortest possible time.

Another aspect to keep in mind is that S3 does not provide a list filter. You either list all the objects or you get a specific object. Traditionally it is best to also use a secondary service like DynamoDB to store the meta data around objects, so that you can query objects from DynamoDB and then retrieve the object data as required from S3. This will probably be a key in selecting only objects created after a certain point in time for event replay. Further more, the archive status can be tracked in DynamoDB in order to kick off processes to restore those objects to a normal storage tier for retrieval and replay.

# Initial Scenario Planning

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
| KEY#<<object-key>>      | <<timestamp>>                                          | - TransactionDate (NUMBER, format YYYYMMDD)                                                                 |
|                         |                                                        | - TransactionTime (NUMBER, format HHMMSS)                                                                   |
|                         |                                                        | - InEventBucket  (BOOL)                                                                                     |
|                         |                                                        | - InArchiveBucket  (BOOL)                                                                                   |
|                         |                                                        | - TargetAccountNumber  (STRING)                                                                             |
|                         |                                                        | - Processed  (BOOL, default=false)                                                                          |
|                         |                                                        |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
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
| <<account-number>>      | SAVINGS#BALANCE#ACTUAL<<customer-number>>              | - LastTransactionDate (NUMBER, format YYYYMMDD)                                                             |
|                         |                                                        | - LastTransactionTime (NUMBER, format HHMMSS)                                                               |
|                         |                                                        | - LastEventKey (STRING, links to <<object-key>>)                                                            |
|                         |                                                        | - Balance (Number)                                                                                          |
|                         |                                                        |                                                                                                             |
| <<account-number>>      | SAVINGS#BALANCE#AVAILABLE<<customer-number>>           | - LastTransactionDate (NUMBER, format YYYYMMDD)                                                             |
|                         |                                                        | - LastTransactionTime (NUMBER, format HHMMSS)                                                               |
|                         |                                                        | - LastEventKey (STRING, links to <<object-key>>)                                                            |
|                         |                                                        | - Balance (Number)                                                                                          |
|                         |                                                        |                                                                                                             |
+-------------------------+--------------------------------------------------------+-------------------------------------------------------------------------------------------------------------+
```

Notes:

* The `SAVINGS#BALANCE` balances reflect the balance of all `TRANSACTIONS#VERIFIED` transactions. Unverified transactions does not yet influence the final balance.
* The Available balance is the balance available for transactions. 




