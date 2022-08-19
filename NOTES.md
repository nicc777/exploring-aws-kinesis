# Field Notes

I use this file to track observations, ideas etc.


# Manually Creating Components

Here is some notes of how I manually created components.

I used the AWS Web Console with the eim to record all the request in order to record the API calls.

I did this by using the developer tools in firefox to record a HAR file. I can't share the HAR file on GitHub since it includes a lot sensitive information, but the API calls I will document as best I can.

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

