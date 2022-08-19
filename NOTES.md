# Field Notes

I use this file to track observations, ideas etc.


# Manually Creating Components

Here is some notes of how I manually created components.

I used the AWS Web Console with the eim to record all the request in order to record the API calls.

I did this by using the developer tools in firefox to record a HAR file. I can't share the HAR file on GitHub since it includes a lot sensitive information, but the API calls I will document as best I can.

As a side note: I used the [Google HAR Analyzer](https://toolbox.googleapps.com/apps/har_analyzer/) for the actual analysis, and even though it does have a feature to download a redacted version of the HAR file, AWS API calls still contain a lot of sensitive information in the POST data Payload, so it is not safe to share publicly.

## Initial Design Goal

After much reading, I settled on the following initial design:

![design](images/manual_creating_components/design.drawio.png)

I will start with the S3 bucket and work my way first to the left. 

## Resource: S3 Bucket

I Created a bucket with public access disabled and encryption enabled (using AWS keys). These were the API calls made:

| Call Order | URL                                                     | Method | Request Data                                                                                                  | Action Description  |
|:----------:|---------------------------------------------------------|:------:|---------------------------------------------------------------------------------------------------------------|---------------------|
| 001        | https://eu-central-1.console.aws.amazon.com/s3/proxy    | `POST` | [001_s3_create_bucket_call.json](labs/lab1-create-solution-using-aws-console/001_s3_create_bucket_call.json)  | Create Bucket       |
| 002        | https://eu-central-1.console.aws.amazon.com/s3/command  | `POST` | [002_s3_create_bucket_call.json](labs/lab1-create-solution-using-aws-console/002_s3_create_bucket_call.json)  | Block Public Access |
| 003        | https://eu-central-1.console.aws.amazon.com/s3/proxy    | `POST` | [003_s3_create_bucket_call.json](labs/lab1-create-solution-using-aws-console/003_s3_create_bucket_call.json)  | Enable Encryption   |

## Resource: Lambda function for Kinesis Data Transformation

Using the [AWS Serverless Application Repository](https://aws.amazon.com/serverless/serverlessrepo/), I created a [Lambda Function](labs/lab1-create-solution-using-aws-console/lambda_functions/data_recorder_kconvert/data_recorder_kconvert_v1.py) to just log the payload and pass it through to the S3 bucket. I will later modify this function to convert the data to CSV suitable for Athena.

The Lambda function create API calls was not captured, as I already know how to define a Lambda function in CloudFormation very well, and I will just use what I already have. I will however attempt to record permissions change API calls when creating Kinesis resources as these will be important for the final CloudFormation template.

## Resource: Kinesis Data Stream

I created a data stream with all the initial settings left at their defaults. The second call was after initial creation that enabled server side encryption (SSE)

| Call Order | URL                                                     | Method | Request Data                                                                                                                    | Action Description  |
|:----------:|---------------------------------------------------------|:------:|---------------------------------------------------------------------------------------------------------------------------------|---------------------|
| 004        | https://kinesis.eu-central-1.amazonaws.com/             | `POST` | [001_kineses_data_stream_call.json](labs/lab1-create-solution-using-aws-console/001_kineses_data_stream_call.json)              | Create Data Stream  |
| 005        | https://kinesis.eu-central-1.amazonaws.com/             | `POST` | [002_kineses_data_stream_enable_sse.json](labs/lab1-create-solution-using-aws-console/002_kineses_data_stream_enable_sse.json)  | Enable SSE          |

## Resource: Kinesis Firehose Delivery Stream

> _**NOTE**_: I got a warning at this stage to increase the Lambda timeout to 1 minute or more. I did that first and then returned to this process.

| Call Order | URL                                                     | Method | Request Data                                                                                                      | Action Description                                                                                                                                       |
|:----------:|---------------------------------------------------------|:------:|-------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 006        | https://iamadmin.amazonaws.com/                         | `POST` | [006_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/006_kineses_delivery_stream.json)  | IAM Permissions                                                                                                                                          |
| 007        | https://iamadmin.amazonaws.com/                         | `POST` | [007_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/007_kineses_delivery_stream.json)  | IAM Permissions                                                                                                                                          |
| 008        | https://logs.eu-central-1.amazonaws.com/                | `POST` | [008_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/008_kineses_delivery_stream.json)  | Log Group                                                                                                                                                |
| 009        | https://logs.eu-central-1.amazonaws.com/                | `POST` | [009_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/009_kineses_delivery_stream.json)  | Log Group                                                                                                                                                |
| 010        | https://logs.eu-central-1.amazonaws.com/                | `POST` | [010_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/010_kineses_delivery_stream.json)  | Log Group                                                                                                                                                |
| 011        | https://firehose.eu-central-1.amazonaws.com/            | `POST` | [011_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/011_kineses_delivery_stream.json)  | Delivery Stream - generated a 400 response                                                                                                               |
| 012        | https://firehose.eu-central-1.amazonaws.com/            | `POST` | [012_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/012_kineses_delivery_stream.json)  | Repeat of request 011 - repeated several times... Each time a 400 response was created. I assume the process is waiting for the IAM permission to apply. |
| 013        | https://firehose.eu-central-1.amazonaws.com/            | `POST` | [013_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/013_kineses_delivery_stream.json)  | Delivery Stream - Finally succeeded                                                                                                                      |
| 014        | https://firehose.eu-central-1.amazonaws.com/            | `POST` | [014_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/014_kineses_delivery_stream.json)  | Unsure of what this request is for...                                                                                                                    |
| 015        | https://logs.eu-central-1.amazonaws.com/                | `POST` | [015_kineses_delivery_stream.json](labs/lab1-create-solution-using-aws-console/015_kineses_delivery_stream.json)  | Appears to be getting logs - no events were returned                                                                                                     |
