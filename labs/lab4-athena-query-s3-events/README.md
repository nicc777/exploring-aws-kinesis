
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

Another question I have would be to see if I can replay data from archives like Glacier. Athena [does not support](https://docs.aws.amazon.com/athena/latest/ug/other-notable-limitations.html) S3 glacier, so I need to consider how a process would look like to get archived objects back into play. Perhaps I need a second bucket that can act as a archive bucket, and then set-up some kind rule to delete objects after x days in the primary event bucket which in turn moves those items to the archive bucket with a life cycle rule to deep archive in the shortest possible time.

Another aspect to keep in mind is that S3 does not provide a list filter. You either list all the objects or you get a specific object. Traditionally it is best to also use a secondary service like DynamoDB to store the meta data around objects, so that you can query objects from DynamoDB and then retrieve the object data as required from S3. This will probably be a key in selecting only objects created after a certain point in time for event replay. Further more, the archive status can be tracked in DynamoDB in order to kick off processes to restore those objects to a normal storage tier for retrieval and replay.

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


