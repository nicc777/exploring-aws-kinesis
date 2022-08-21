# Exploring AWS Kinesis

> _**Please Note**_ This is a personal learning experiment and none of the code or examples here are intended for production use. I share my designs, code and other artifacts for the purposes of sharing my experiences and learnings and also to encourage community participation as I believe in the principle of sharing knowledge and experience. 

Please feel free to suggest improvements if you notice I am going down a wrong path

This repository contains experimental artifacts to learn about Event/Message Driven Design using Serverless concepts in AWS.

My personal goal is to explore the serverless options from a business process perspective using a web front-end to capture data that is eventually processed.

I use this repository to explore, learn and test the following AWS Services:

* Kinesis
* Using S3 as a destination
* Using AWS Athena to query S3 data post-ingestion
* React to events in S3 with further SNS and Lambda integration
* SNS and SQS, including the use of dead-letter queues etc.

I also want to explore event-replay to see how such a pattern would work. An example scenario would be a customer support request to re-process data.

Further more I am also interested in the operational aspects and observability options. I want to explore what type of alerts may be required.

# Resources

The following resources serves as sources of knowledge and technical information:

| Title                                                                 | Resource Type | Source                                                                                                                                     | Publish Date      | Description/Notes                                                                       |
|-----------------------------------------------------------------------|:-------------:|--------------------------------------------------------------------------------------------------------------------------------------------|:-----------------:|-----------------------------------------------------------------------------------------|
| Event Sourcing on AWS                                                 | Video (16:19) | [Youtube](https://youtu.be/NvuZoDfuoBc)                                                                                                    | 2021-06-13        | A short and nice introduction to Event Sourcing Patterns using AWS Serverless Resources |
| Scalable serverless event-driven architectures with SNS, SQS & Lambda | Video (32:48) | [Youtube](https://youtu.be/8zysQqxgj0I)                                                                                                    | 2021-02-05        | A more detailed look at SNS and SQS                                                     |
| The Many Meanings of Event-Driven Architecture (Martin Fowler)        | Video (50:05) | [Youtube](https://youtu.be/STKCRSUsyP0)                                                                                                    | 2017-05-11        | A theoretical look from "the man"                                                       |
| Amazon Kinesis Documentation                                          | HTML/PDF      | [AWS Documentation Portal](https://docs.aws.amazon.com/kinesis/?id=docs_gateway)                                                           | Regularly Updated | Kinesis documentation and API reference                                                 |
| AWS Serverless Application Repository                                 | HTML          | [AWS Serverless Application Repository Portal](https://aws.amazon.com/serverless/serverlessrepo/)                                          | Regularly Updated | Examples and blueprints for common applications that can be re-used                     |
| Amazon Kinesis Data Firehose Data Transformation                      | HTML          | [Amazon Kinesis Data Firehose Data Transformation Documentation](https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html) | Regularly Updated | Notes about data transformation requirements for Lambda functions                       |

_**Note**_: More resources will be added as I find them

# Labs

The various practical exercises I did is located in the `labs` directory. All lab notes is in the file [NOTES.md](NOTES.md). Below is a short description of what each lab directory contains:

| Lab Session | Description                                                                                                                            | Status      |
|:-----------:|----------------------------------------------------------------------------------------------------------------------------------------|-------------|
| Lab 1       | Creating resources via the AWS Console to get an initial idea of what is required, how it works and the settings required              | Complete    |
| Lab 2       | Take learnings from Lab 1 and produce a CloudFormation template (or templates) to easily create more streams ingested from API Gateway | In Progress |
| Lab 3       | A lower volume example without Kinesis - ideal for a mixed environment                                                                 | Not Started |
| Lab 4       | Operations: replaying old events                                                                                                       | Not Started |

# Current Status

> Infrastructure as Code Lab Resource Provisioning

This project started on 2022-08-18 and I am still in the early stages of collecting theoretical knowledge.

More information will be provided on an ongoing bases.

I expect this project to have the following stages:

* ~~Early Exploration~~ 
* ~~Lab Design (based on learnings from documentation)~~
* ~~Manual Lab Resource Provisioning (AWS API and AWS Console)~~
* Infrastructure as Code Lab Resource Provisioning (CloudFormation) (`In Progress`)
* Finalize documentation
* Maintenance Phase (long term)
