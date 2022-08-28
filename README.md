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
| Cross-Origin Resource Sharing (CORS)                                  | HTML          | [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)                                                                     | Regularly Updated | CORS configuration is required for the API Gateway and this is a great resource         |
| Configuring CORS for an HTTP API                                      | HTML          | [AWS Documentation for API Gateway v2](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-cors.html)                    | Regularly Updated | Examples of some specific settings relevant to AWS API Gateway                          |
| Athena compression support                                            | HTML          | [AWS Documentation for Athena](https://docs.aws.amazon.com/athena/latest/ug/compression-formats.html)                                      | Regularly Updated | Need to consider this when deciding on a file format to store Events in S3 in.          |

_**Note**_: More resources will be added as I find them

# Labs

The various practical exercises I did is located in the `labs` directory. All lab notes is in the file [NOTES.md](NOTES.md). Below is a short description of what each lab directory contains:

| Lab Session | Description                                                                                                                            | Status      |
|:-----------:|----------------------------------------------------------------------------------------------------------------------------------------|:-----------:|
| Lab 1       | Creating resources via the AWS Console to get an initial idea of what is required, how it works and the settings required              | Complete    |
| Lab 2       | Take learnings from Lab 1 and produce a CloudFormation template (or templates) to easily create more streams ingested from API Gateway | Complete    |
| Lab 3       | A lower volume example without Kinesis - ideal for a mixed environment                                                                 | In Progress |
| Lab 4       | Operations: replaying old events                                                                                                       | Not Started |
| Lab 5       | Project Management and DevOps Topic                                                                                                    | Not Started |
| Lab 6       | Tightening up security. Encryption of data in flight and at rest everywhere.                                                           | Not Started |
| Lab 7       | A practical application and Load Test                                                                                                  | Not Started |
| Lab 8       | Add private (internal) SNS Topics for events only originating from internal systems                                                    | Not Started |
| Lab 9       | Add a custom domain and protect the API Gateway from being called from the AWS URL                                                     | Not Started |
| Lab 10      | Add authentication and authorization                                                                                                   | Not Started |
| Lab 11      | Observability                                                                                                                          | Not Started |

# Current Status

> Infrastructure as Code Lab Resource Provisioning

This project started on 2022-08-18 and I am still in the early stages of collecting theoretical knowledge.

More information will be provided on an ongoing bases.

I expect this project to have the following stages:

* ~~Early Exploration~~ 
* ~~Lab Design (based on learnings from documentation)~~
* ~~Lab 1: Manual Lab Resource Provisioning (AWS API and AWS Console)~~
* ~~Lab 2: Infrastructure as Code Lab Resource Provisioning (CloudFormation)~~
* Lab 3: Adapt lab 2 to create a hybrid Kinesis and direct S3 put solution (splitting high volume and low volume data ingestion processes).
* Lab 4: Evaluate Athena as a tool to query and replay old captured events
* Lab 5: Reorganize the CloudFormation stacks to a manageable set of files. Invest some time to figure out [AWS::CloudFormation::Stack](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-stack.html). The aim of this is to see how we can add more events in future in a structured way, with some inheritance and resource project organization.
* Lab 6: Use private KMS in all areas to encrypt data. Introduce data models to enforce input and output validation.
* Lab 7: A practical example with some real logic and a CloudFormation template to setup and run load tests via something like [Locust](https://locust.io/)
* Lab 8: Look at adding SNS Topics or other ingress services for events generated internally (not publicly exposed). Adapt examples - see if some of the external event processing can generate an internal only event. Explore how failures are handled.
* Lab 9: Add a custom domain and look at ways to protect the AWS URL for API Gateway. Also consider ACM and digital certificates.
* Lab 10: Adapt end-points and processing to expose public endpoints (not authorization), and protected end-points (requires API key or authorization token). 
* Lab 11: Play with X-Ray to trace events. Look at how to build dashboards and alerts to monitor when things go wrong. Create specific artificial errors in test for: a) Incorrect input models; b) Valid input model with invalid data (processing failure); c) Authentication/Authorization failures; d) Artificial processing slow down
* Finalize documentation, findings, conclusions and refactor final designs and artifacts
* Maintenance Phase (long term)
