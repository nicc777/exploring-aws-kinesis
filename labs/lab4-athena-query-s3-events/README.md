
- [Lab 4 Goals](#lab-4-goals)
- [Initial Scenario Planning](#initial-scenario-planning)
  - [Event Data](#event-data)

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

Another question I have would be to see if I can replay data from archives like Glacier. Does Athena even work with Glacier? Something to investigate.

# Initial Scenario Planning

## Event Data

Since I need more than one type of event, and since the actual data does not matter, I am going to use these made-up events.

_**Event 1**_:

```json
{
    "E1F1": "String",
    "E1F2": true,
    "E1F3": 123,
    "E1F4": {
        "SF1": "String",
        "SF2": [
            "a",
            "b",
            "c"
        ]
    }
}
```

_**Event 2**_:

```json
{
    "E2F1": "String",
    "E2F2": "String",
    "E2F3": "String",
    "E2F4": [
        "a",
        "b",
        "c"
    ]
}
```

The actual data could be random, but I will attempt to make it still predictable in order to make testing/verification a little easier.

As per lab 3, the two different events will have slightly different key name structures:

* Event 1: `event_1_<<event-id>>.event`
* Event 2: `another_event_<<event-id>>.event`


