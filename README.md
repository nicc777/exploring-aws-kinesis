- [Exploring AWS Kinesis](#exploring-aws-kinesis)
- [Resources](#resources)
- [Labs](#labs)
- [Current Progress and Critical Updates](#current-progress-and-critical-updates)
  - [Updates](#updates)
- [Example Application](#example-application)
  - [Process: Register a New Employee Access Card](#process-register-a-new-employee-access-card)
  - [Process: Enter building through a turnstile gate](#process-enter-building-through-a-turnstile-gate)
  - [Process: Exit building through a turnstile gate](#process-exit-building-through-a-turnstile-gate)
  - [Process: Authenticated user views access card usage events for an employee](#process-authenticated-user-views-access-card-usage-events-for-an-employee)
  - [Final Notes](#final-notes)

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

| Title                                                                                            | Resource Type | Source                                                                                                                                     | Publish Date      | Description/Notes                                                                       |
|--------------------------------------------------------------------------------------------------|:-------------:|--------------------------------------------------------------------------------------------------------------------------------------------|:-----------------:|-----------------------------------------------------------------------------------------|
| Event Sourcing on AWS                                                                            | Video (16:19) | [Youtube](https://youtu.be/NvuZoDfuoBc)                                                                                                    | 2021-06-13        | A short and nice introduction to Event Sourcing Patterns using AWS Serverless Resources |
| Scalable serverless event-driven architectures with SNS, SQS & Lambda                            | Video (32:48) | [Youtube](https://youtu.be/8zysQqxgj0I)                                                                                                    | 2021-02-05        | A more detailed look at SNS and SQS                                                     |
| The Many Meanings of Event-Driven Architecture (Martin Fowler)                                   | Video (50:05) | [Youtube](https://youtu.be/STKCRSUsyP0)                                                                                                    | 2017-05-11        | A theoretical look from "the man"                                                       |
| Amazon Kinesis Documentation                                                                     | HTML/PDF      | [AWS Documentation Portal](https://docs.aws.amazon.com/kinesis/?id=docs_gateway)                                                           | Regularly Updated | Kinesis documentation and API reference                                                 |
| AWS Serverless Application Repository                                                            | HTML          | [AWS Serverless Application Repository Portal](https://aws.amazon.com/serverless/serverlessrepo/)                                          | Regularly Updated | Examples and blueprints for common applications that can be re-used                     |
| Amazon Kinesis Data Firehose Data Transformation                                                 | HTML          | [Amazon Kinesis Data Firehose Data Transformation Documentation](https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html) | Regularly Updated | Notes about data transformation requirements for Lambda functions                       |
| Cross-Origin Resource Sharing (CORS)                                                             | HTML          | [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)                                                                     | Regularly Updated | CORS configuration is required for the API Gateway and this is a great resource         |
| Configuring CORS for an HTTP API                                                                 | HTML          | [AWS Documentation for API Gateway v2](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-cors.html)                    | Regularly Updated | Examples of some specific settings relevant to AWS API Gateway                          |
| Athena compression support                                                                       | HTML          | [AWS Documentation for Athena](https://docs.aws.amazon.com/athena/latest/ug/compression-formats.html)                                      | Regularly Updated | Need to consider this when deciding on a file format to store Events in S3 in.          |
| Best practices for designing and architecting with DynamoDB                                      | HTML          | [AWS Documentation for DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)                     | Regularly Updated | Required for the real scenario to hold our employee and access card data                |
| Use Elastic Load Balancing to distribute traffic across the instances in your Auto Scaling group | HTML          | [AWS Documentation for DyEC2 Auto Scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/autoscaling-load-balancer.html)           | Regularly Updated | Interested to see how we can still use traditional EC2 services for basic applications  |
| How to create a functional VPC using CloudFormation                                              | HTML          | [Blog of Kevin Sookocheff](https://sookocheff.com/post/aws/how-to-create-a-vpc-using-cloudformation/)                                      | 2017-06-07        | Great starting point for creating a VPC in CloudFormation.                              |

_**Note**_: More resources will be added as I find them

# Labs

The various practical exercises I did is located in the `labs` directory. Click on the link for each lab to view the detailed documentation and findings for that lab. Below is a short description of what each lab directory contains:

| Lab Session                                                                       | Description                                                                                                                            | Status      |
|:---------------------------------------------------------------------------------:|----------------------------------------------------------------------------------------------------------------------------------------|:-----------:|
| [Lab 1](labs/lab1-create-solution-using-aws-console/README.md)                    | Creating resources via the AWS Console to get an initial idea of what is required, how it works and the settings required              | Complete    |
| [Lab 2](labs/lab2-construct-cloudformation-template-from-lab1-findings/README.md) | Take learnings from Lab 1 and produce a CloudFormation template (or templates) to easily create more streams ingested from API Gateway | Complete    |
| [Lab 3](labs/lab3-non-kinesis-example/README.md)                                  | A lower volume example without Kinesis - ideal for a mixed environment                                                                 | In Progress |
| Lab 4                                                                             | Operations: replaying old events                                                                                                       | Not Started |
| Lab 5                                                                             | Project Management and DevOps Topic                                                                                                    | Not Started |
| Lab 6                                                                             | Tightening up security. Encryption of data in flight and at rest everywhere.                                                           | Not Started |
| Lab 7                                                                             | A practical application and Load Test                                                                                                  | Not Started |
| Lab 8                                                                             | Add private (internal) SNS Topics for events only originating from internal systems                                                    | Not Started |
| Lab 9                                                                             | Add a custom domain and protect the API Gateway from being called from the AWS URL                                                     | Not Started |
| Lab 10                                                                            | Add authentication and authorization                                                                                                   | Not Started |
| Lab 11                                                                            | Observability                                                                                                                          | Not Started |

# Current Progress and Critical Updates

This project started on 2022-08-18 ~~and I am still in the early stages of collecting theoretical knowledge~~. I got the Kinesis streams working, but there is still a number of things to explore. For example, I want to learn how to protect my data in flight, end-to-end.

More information will be provided on an ongoing bases.

I expect this project to have the following stages:

* ~~Early Exploration~~ 
* ~~Lab Design (based on learnings from documentation)~~
* ~~Lab 1: Manual Lab Resource Provisioning (AWS API and AWS Console)~~
* ~~Lab 2: Infrastructure as Code Lab Resource Provisioning (CloudFormation)~~
* Lab 3: Adapt lab 2 to create a hybrid Kinesis and direct S3 put solution (splitting high volume and low volume data ingestion processes) (`In Progress`)
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

## Updates

| Entry Date | Update                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|:----------:|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2022-09-09 | Progress this morning was frustratingly slow as I am strugling to get the configuration for the Load Balancer right. Also, the EC2 instances deployed in the private VPC is still not able to work with SSM console connections, so I have to troubleshoot that as well.                                                                                                                                                                                                                                                               |
| 2022-09-08 | Still busy with creating the EC2 instance to manage the GitHib deployments. SSM Connect does not work yet. Also busy fixing the proxy connection (final tests to be done) to ensure the EC2 instance can reach the Internet.                                                                                                                                                                                                                                                                                                           |
| 2022-09-07 | Started working on the stacks that will allow any changes on Static Web Page Artifacts to by synchonized to the FSX volume. Still much work to do on this pattern.                                                                                                                                                                                                                                                                                                                                                                     |
| 2022-09-06 | I eventually realized that the certificate I was trying to create for the Proxy server fails because it is a private hosted zone and I probably need a private ACM, which requires a Private CA - something that costs US$400 a month. So the internal proxy server will run unsecured on port 8080. I have successfully added a Load Balancer and DNS record for the Load Balancer to the Proxy server.                                                                                                                               |
| 2022-09-05 | In [Lab 3](labs/lab3-non-kinesis-example/README.md) I added SSM access to EC2 Instances via the AWS Console. As a result, SSH access was also now removed. The only way to access an instance terminal now is via AWS Console. Started adding ELB to the proxy server setup, but at the moment ACM fails to create - still need to trouble shoot this.                                                                                                                                                                                 |
| 2022-09-04 | Sometimes I don't always know just how much a chew off... Today I realized that the _simple_ example application I created requires a ton of additional resources I did not initially thought about. This is not a bad thing, but the effect is that [Lab 3](labs/lab3-non-kinesis-example/README.md) will take considerably longer to complete than what I initially thought. In any case, it is still a worthwhile exercise and I am learning (or re-learning) a ton of stuff. More update to follow in the coming weeks.            |

# Example Application

Lab 1 and 2 are early exploratory labs and as such, they will not contain any meaningful data or even processing functions - it's basically boilerplate stuff to see if it works.

From Lab 3 I am starting to think about a practical application. I have settled on a _"Employee Access Card Usage Event Capturing System"_.

First of all, there are two types of event sources to consider:

* Events from external sources: these are events from devices that have scanned a RFID badge and now submits that data to a public API and-point. We could argue that the AWS IoT services may be better suited for this, but for now I am going to pretend that those services do not exist. At some point I would also introduce some kind to authorization (API Key) so that we ensure that our data is only collected from trusted devices. We will simulate a number of offices where many thousands of people can access turnstiles, vending machines and many other devices that access cards can be scanned for use. There are scenarios, like a person entering a building via a turnstile gate, where a card swipe needs to be synchronize and these scenarios are not ideal for Kinesis. There are other scenarios that may be high volume and where Kinesis can be used, for example to exit a building (always allow - but delay processing).
* Other events are from trusted sources inside our infrastructure that do not require access via a public API Gateway. An example would be when HR from a secured workstation issue a new access card to an employee.

In this scenario and broad use-cases, I would therefore build up the following applications with their relevant events:

## Process: Register a New Employee Access Card

A new Access Card is Issued.

![Scenario 01](images/scenario_01.png)

| Requires API Gateway | Sync/Async   | High Volume | Authentication | Authorization |
|:--------------------:|:------------:|:-----------:|:--------------:|:-------------:|
|  No                  |  Async (Web) |   No        | AWS Cognito    | JWT Token     |

## Process: Enter building through a turnstile gate

A person enters the building and must scan their access card at the turnstile gate.

![Scenario 01](images/scenario_02.png)

| Requires API Gateway | Sync/Async   | High Volume | Authentication | Authorization |
|:--------------------:|:------------:|:-----------:|:--------------:|:-------------:|
|  Yes                 |  Sync        |   No        | n/a            | API Key       |

## Process: Exit building through a turnstile gate

A person exits the building. In emergencies, this could be a high volume scenario.

![Scenario 01](images/scenario_03.png)

| Requires API Gateway | Sync/Async   | High Volume | Authentication | Authorization |
|:--------------------:|:------------:|:-----------:|:--------------:|:-------------:|
|  Yes                 |  Async       |   Yes       | n/a            | API Key       |


## Process: Authenticated user views access card usage events for an employee

An external auditor review key scan logs of an individual.

![Scenario 01](images/scenario_04.png)

| Requires API Gateway | Sync/Async   | High Volume | Authentication | Authorization |
|:--------------------:|:------------:|:-----------:|:--------------:|:-------------:|
|  Yes                 |  Async (Web) |   No        | AWS Cognito    | JWT Token     |

## Final Notes

_**Note**_: Async events can use Kinesis if it is a potential high volume scenario. Events are buffered and therefore there can be small delays before events are processed.

Another business rule we will introduce is that access cannot be allowed if the current employee is considered to be already in the building. In other words, you must scan out before you can scan back in. This means that sometimes when an employee goes out, and immediately tries to go back in, they may have to wait a little.

The actual card state will be maintained in a DynamoDB table.
