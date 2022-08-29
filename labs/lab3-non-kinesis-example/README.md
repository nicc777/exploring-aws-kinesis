# Lab 3 Goals

The main goal of this lab is to adapt lab 2 to create a hybrid Kinesis and direct S3 put solution (splitting high volume and low volume data ingestion processes).

I also want to start to introduce the example scenario in this lab, just to make it a little more practical. Therefore, a number of resources will be created and as such I need to start to think also about how the business logic is split from the Infrastructure.

I am going to attempt to implement a private API as well in order to cater for scenario 1 where a new access card is issued to a employee.

For this exercise to be practical, I would require a privately hosted web front-end which will be a very basic Docker based we application (written in Python). The web application will be running in a Docker container on an EC2 instance running in a Private VPC. There will be a Elastic Load Balancer on the Public VPC to access the private EC2 instance web service and in turn I will bind the ELB domain to a custom domain name which I have purchased manually through the AWS Route 53 service. No authentication will be done at this point.

The web application is very straight forward. A form will be presented where a building ID, an employee ID and a Access Card ID is entered. When the form is submitted, an event to link the two entities is created and when processed, the linked card will be stored in DynamoDB with an initial state of `INSIDE` and the initial building ID set to the building ID from the form. In other words, we assume the employee to be present when handed the card in the building with the relevant building ID. He is therefore inside the building.

The event will be created by the containerized application by publishing to an SNS topic. The SNS topic will forward the message to an SQS queue from where a Lambda function will generate the final event and persist it to S3. The API gateway will require at least the following API end-points:

| API Endpoint                                                   | Method | Expected Input Data                                                                                                                          | Processing                                                                                            | Result                                    |
|----------------------------------------------------------------|:------:|----------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|-------------------------------------------|
| `/building-access/link-employee-and-card`                      | POST   | JSON Post with the following data: <br /><ul><li>HR Employee ID</li><li>Building ID</li><li>New Employee ID</li><li>Access Card ID</li></ul> | Basic input validation. Construct SNS message and publish to SNS topic.                               | Return `OK` when SNS Accepted the message |
| `/building-access/employee-access-card-status/<<employee-id>>` | GET    | Path variable `employee-id` with the employee ID for which the card must be retrieved.                                                       | Directly query the DynamoDB to search for the employee ID and retrieve the linking fields and status. | Return JSON object with data              |
| `/hr/employee-ids`                                             | GET    | Query string: `max-items` (max. 100, default=100) and then the `start` index position (optional, default=0)                                  | Retrieve employee ID's, limit by `max-items` staring at position `start`                              | Return JSON object employee ID's          |

Each of the API endpoints is services by a Lambda function.

# Application Components

What is of particular interest for me here is how I can split the business logic (Docker image, Lambda functions etc.) from Infrastructure (the rest).

From a high level process perspective refer to the following diagram:

![scenario 1](../../images/scenario_01.png)

Physical world scenario walk through:

* A new employee does not have an access card. They are physically present in a building where the card will be issued.
* The new employee meets up with an authorized representative that will issue an access card to the employee
* The authorized representative captures the data in the system before handing over the access card to the new employee
* When the authorized representative can confirm that the card has been issued, the physical card is now actually issued to the employee

From an infrastructure and application perspective, we have the following context diagram:

![scenario 1 architecture context diagram](../../images/scenario_01_design.png)

From the design exercise, I now start to understand what Infrastructure is really core to the event store, which is basically the following components from the original template in Lab 2:

![Core Infrastructure](../../images/scenario_01_core_infrastructure_for_evemts.png)

I will therefore now see how I split up my infrastructure into more logic parts. For now, I have identified the following:

* Events base Infrastructure (as per the image above)
* The EC2 Internal Web Hosting Infrastructure
* Access card linking Infrastructure - basically just an SNS topic and SQS queue that binds the event in S3 to the final Lambda function that updates the state in DynamoDB.

> _**Observation**_: What I still need to see is how I develop these independently and then link then up somehow... Imaging there was different teams developing the various stacks and pipelines - how do they need to coordinate?

## DynamoDB Design

For this exercise, all data will be gathered in 1x DynamoDB table. Even though the HR system may have their own application sets and table(s), this particular table is for associating employees with access cards as well as tracking which the access card usage status, relative to a building (when applicable).

As such, I started with a composite key design with the following structure:

### Partition Key

Made up of a subject ID, in two parts: `subject-type` and `subject-id-hash`

Subject types can be:

* `Employee` and the ID is a SHA256 hash of the employee number
* `Access Card` and the ID is a SHA256 hash of the access card number
* `Building` and the ID is a SHA256 hash of the building identifier
* `Employee Access Card Link` and the ID is the SHA256 hash of a concatenated string of the employee ID and the access card id

Employee ID's end with the letter `-E` while access card ID's start with the letters `AC`. Before these letter, and only for the purpose of this exercise, we will use sequential numbers for each new employee number or access card, and in both cases we will start at the number `100000000000` which will more-or-less guarantee a 12 digit number for each employee or access card.

Building identifiers end with the letter `-B` and before this sequence a ID which will also be a sequential number similar to the employee and access cards.

the employee access card links is just a combination (concatenation) of the Employee partition key and the access card partition key.

Examples:

| Subject Type | ID Number    | Partition Key Value                                                  |
|--------------|--------------|----------------------------------------------------------------------|
| Employee     | 100000000000 | `7105a7c94731c3b17021741601573512622e20d6eb5ef8d90bd703d09ea5263f-E` |
| Employee     | 100000000001 | `48af5465f4e26fcd41c9021ea531ba3f62b7e1bb2aca74bbb20aca7cdb0eb6d2-E` |
| Employee     | 100000000002 | `f72b23f5379310fb749a3971af2f7523139108e24a5ccda07bff4d4bff9a2c78-E` |
| Employee     | 100000001998 | `59d05236b40f6db1e6e7e95b2e5729241c442fc4d007cf73bf0ff816a1ecd4fd-E` |
| Employee     | 100000001999 | `3d1d121a7f823e4600dff2b291b476b02fb8f1ea399e48b811709240f8bc2591-E` |
| Employee     | 100000002000 | `807ced1921f9bae1401b80e21fec0cd679ef489a625cfd2e33e61132db2a8296-E` |
| Access Card  | 100000000000 | `cf3121e8d17be03ffcbc620a4e9c80c4b5c46966885357df7baa27bb2655ef4cAC` |
| Access Card  | 100000000001 | `fca8c49d4501aa9fdd5fa1ea8e3e56172ee1e65b2ebfb8a2bca8ce48c3386edbAC` |
| Access Card  | 100000000002 | `0654b48384296e5fdd830847cf4912c821189801667c5a50656185f7759fe087AC` |
| Access Card  | 100000001998 | `f208e56b37248f5c441d996065dbb5de4c8eb64dfaffe617dbd71b0314ef502fAC` |
| Access Card  | 100000001999 | `7bc00ee3e73679a2f73ee654a2e2c3a2537df8ea52578c4cefcb01e2856d1d66AC` |
| Access Card  | 100000002000 | `5fa8c78d95177dca11e68b6001a0d1db5bd0711df2aca6dc0aa39b8c2f9bab71AC` |
| Building     | 100000000000 | `ec7f1f0113ff321c8fa7374c6b1cb55a216ee45ad1a1763bb6ef6b9db1c8d20f-B` |
| Building     | 100000000001 | `7c4b67e9caad0fee493793b9b62474e4854dc2b254b12ee18d483630071939d2-B` |
| Building     | 100000000098 | `0e3b534f6483c9ab9223ea668363834a1b2402fc356a470888dcd1792ca24a9d-B` |
| Building     | 100000000099 | `a2f064a59b5bd27804cab668cb1629b5eb53f3d74f1f0d56cae4a6e6a6c8c450-B` |


Below are python functions to calculate the various partition key values:

```python
import hashlib


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
        self.PARTITION_KEY = hashlib.sha256('{}|{}'.format(subject1.PARTITION_KEY,subject2.PARTITION_KEY).encode('utf-8')).hexdigest()

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


for sd in source_data:
    s = Subject(subject_type=sd[0], subject_id=sd[1])
    t = '{}'.format(sd[1])
    id_number = '1{}'.format(t.zfill(11))
    print('| {} | {} | `{}` |'.format(sd[2], id_number, s.PARTITION_KEY))
```



## Lambda Function for Listing Employee ID's

TODO

## Lambda Function For getting the status of a specific employee and their access card

TODO

## Lambda Function(s) for Linking an employee ID, Access Card and Building ID with an initial default building status of `INSIDE`

TODO

# Infrastructure Components 

## Serving of a web site from EC2 (private only), accessed via a proxy server in a Public VPC

TODO

## Event Infrastructure

TODO

## Private API Gateway to access the Lambda API's.

TODO

# Random Thoughts

Something that occurred to me while I was designing this solution was to think about why I would still expose certain applications via EC2 - why not have everything as serverless?

The fact is that sometimes we still have to deal with off-the-shelve products, and I am treating this web app as a typical example. In theory I could also just host it directly from S3, but I would like to use this opportunity to exercise some other concepts as well, even though they may not be too high on the cool-scale.
