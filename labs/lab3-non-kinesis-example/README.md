
- [Lab 3 Goals](#lab-3-goals)
- [CLI Environment](#cli-environment)
- [Application Components](#application-components)
  - [DynamoDB Design](#dynamodb-design)
  - [Pre-populating Data](#pre-populating-data)
  - [Lambda Function for Listing Employee ID's](#lambda-function-for-listing-employee-ids)
  - [Lambda Function For getting the status of a specific employee and their access card](#lambda-function-for-getting-the-status-of-a-specific-employee-and-their-access-card)
  - [Lambda Function(s) for Linking an employee ID, Access Card and Building ID with an initial default building status of `INSIDE`](#lambda-functions-for-linking-an-employee-id-access-card-and-building-id-with-an-initial-default-building-status-of-inside)
  - [Lambda Function Deployment](#lambda-function-deployment)
- [Infrastructure Components](#infrastructure-components)
  - [VPC and Proxy Server](#vpc-and-proxy-server)
  - [Serving of a web site from EC2 (private only), accessed via a proxy server in a Public VPC](#serving-of-a-web-site-from-ec2-private-only-accessed-via-a-proxy-server-in-a-public-vpc)
    - [Capturing Proxy Request Data to the Docker Containers](#capturing-proxy-request-data-to-the-docker-containers)
    - [Testing the API from the command line with the JWT Access Token](#testing-the-api-from-the-command-line-with-the-jwt-access-token)
  - [Handling Updates to Static Web Pages](#handling-updates-to-static-web-pages)
    - [GitHub Web Hooks](#github-web-hooks)
    - [Managing the GitHub Sync Server](#managing-the-github-sync-server)
    - [Handling the SQS Payload](#handling-the-sqs-payload)
  - [Web API Stack (AWS API Gateway)](#web-api-stack-aws-api-gateway)
  - [Event Infrastructure](#event-infrastructure)
    - [S3 Events Bucket Resources](#s3-events-bucket-resources)
- [Random Thoughts](#random-thoughts)

# Lab 3 Goals

The main goal of this lab is to adapt lab 2 to create a hybrid Kinesis and direct S3 put solution (splitting high volume and low volume data ingestion processes).

I also want to start to introduce the example scenario in this lab, just to make it a little more practical. Therefore, a number of resources will be created and as such I need to start to think also about how the business logic is split from the Infrastructure.

I am going to attempt to implement a private API as well in order to cater for scenario 1 where a new access card is issued to a employee.

For this exercise to be practical, I would require a privately hosted web front-end which will be a very basic Docker based we application (written in Python). The web application will be running in a Docker container on an EC2 instance running in a Private VPC. There will be a Elastic Load Balancer on the Public VPC to access the private EC2 instance web service and in turn I will bind the ELB domain to a custom domain name which I have purchased manually through the AWS Route 53 service. No authentication will be done at this point.

The web application is very straight forward. A form will be presented where a building ID, an employee ID and a Access Card ID is entered. When the form is submitted, an event to link the two entities is created and when processed, the linked card will be stored in DynamoDB with an initial state of `INSIDE` and the initial building ID set to the building ID from the form. In other words, we assume the employee to be present when handed the card in the building with the relevant building ID. He is therefore inside the building.

The event will be created by the containerized application by publishing to an SNS topic. The SNS topic will forward the message to an SQS queue from where a Lambda function will generate the final event and persist it to S3. The API gateway will require at least the following API end-points:

> _**Note**_: The API end-points below is out of date and I still need to update it (2022-10-04)

| API Endpoint                                                   | Method | Expected Input Data                                                                                                                          | Processing                                                                                            | Result                                    |
|----------------------------------------------------------------|:------:|----------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|-------------------------------------------|
| `/building-access/link-employee-and-card`                      | POST   | JSON Post with the following data: <br /><ul><li>HR Employee ID</li><li>Building ID</li><li>New Employee ID</li><li>Access Card ID</li></ul> | Basic input validation. Construct SNS message and publish to SNS topic.                               | Return `OK` when SNS Accepted the message |
| `/building-access/employee-access-card-status/<<employee-id>>` | GET    | Path variable `employee-id` with the employee ID for which the card must be retrieved.                                                       | Directly query the DynamoDB to search for the employee ID and retrieve the linking fields and status. | Return JSON object with data              |
| `/hr/employee-ids`                                             | GET    | Query string: `max-items` (max. 100, default=100) and then the `start` index position (optional, default=NULL)                                  | Retrieve employee ID's, limit by `max-items` staring at position `start`                           | Return JSON object employee ID's          |

Each of the API endpoints is services by a Lambda function.

# CLI Environment

When running commands, the following environment variables are assumed to be set:

| Environment Variable Example                | Description                                                                                       |
|---------------------------------------------|---------------------------------------------------------------------------------------------------|
| `export AWS_PROFILE="..."`                  | The AWS Credentials Profile to use                                                                |
| `export AWS_REGION="..."`                   | The AWS Region to deploy resources to                                                             |
| `export PARAMETERS_FILE="..."`              | The file containing the stack parameters                                                          |
| `export DYNAMODB_STACK_NAME="..."`          | The CloudFormation stack name for deploying the DynamoDB Table                                    |
| `export LAMBDA_STACK_NAME="..."`            | The CloudFormation stack name for deploying Lambda Functions                                      |
| `export VPC_STACK_NAME="..."`               | The CloudFormation stack name for deploying the VPC resources                                     |
| `export NFS_STACK_NAME="..."`               | The CloudFormation stack name for deploying a FSX Filesystem                                      |
| `export DNS_STACK_NAME="..."`               | The CloudFormation stack name for deploying DNS and ACM                                           |
| `export PROXY_STACK_NAME="..."`             | The CloudFormation stack name for deploying the Proxy server                                      |
| `export GITHUB_SECRET_STACK_NAME="..."`     | The CloudFormation stack name for deploying the GitHub SSH Key in Secrets Manager                 |
| `export GITHUB_SYNC_STACK_NAME="..."`       | The CloudFormation stack name for deploying the GitHub Sync Resources                             |
| `export SSM_VPC_ENDPOINT_STACK_NAME="..."`  | The CloudFormation stack name for deploying The SSM VPC End Point resource                        |
| `export WEB_SERVER_STACK_NAME="..."`        | The CloudFormation stack name for deploying The Web Server and API Gateway Resources              |
| `export COGNITO_STACK_NAME="..."`           | The CloudFormation stack name for deploying The employee Cognito Pool                             |
| `export WEBAPI_STACK_NAME="..."`            | The CloudFormation stack name for deploying The Website API Resources                             |
| `export WEBAPI_LAMBDA_STACK_NAME="..."`     | The CloudFormation stack name for deploying The Website API Resources - Lambda Functions          |
| `export WEBAPI_ROUTES_1_STACK_NAME="..."`   | The CloudFormation stack name for deploying The Website API Resources - Routes and Integrations   |
| `export WEBAPI_ROUTES_2_STACK_NAME="..."`   | The CloudFormation stack name for deploying The Website API Resources - Routes and Integrations   |
| `export WEBAPI_DEPLOYMENT_STACK_NAME="..."` | The CloudFormation stack name for deploying The Website API Resources - Deployment and DNS        |
| `export S3_EVENTS_STACK_NAME="..."`         | The CloudFormation stack name for deploying The S3 Events Bucket                                  |
| `export ARTIFACT_S3_BUCKET_NAME="..."`      | The S3 Bucket name containing any additional artifacts                                            |
| `export EC2_KEYPAIR_KEY_NAME="..."`         | A pre-existing EC2 Key Pair Key Name                                                              |
| `export SUPPORTED_REPOSITORIES="..."`       | CSV List of supported repositories                                                                |
| `export GITHUB_AUTHORIZED_SENDERS="..."`    | CSV List of supported sender login values                                                         |
| `export ROUTE53_PUBLIC_ZONEID="..."`        | The Route 53 Hosted Zone ID of the Public DNS Domain                                              |
| `export ROUTE53_PUBLIC_DNSNAME="..."`       | The Route 53 Hosted Public DNS Domain Name                                                        |
| `export EMPLOYEE_1_EMAIL="..."`             | A valid email address of a dummy employee (expect actual e-mails to be sent here)                 |

Some of these variables, like 

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

![Core Infrastructure](../../images/scenario_01_core_infrastructure_for_events.png)

I will therefore now see how I split up my infrastructure into more logic parts. For now, I have identified the following:

* Events base Infrastructure (as per the image above)
* The EC2 Internal Web Hosting Infrastructure
* Access card linking Infrastructure - basically just an SNS topic and SQS queue that binds the event in S3 to the final Lambda function that updates the state in DynamoDB.

> _**Observation**_: What I still need to see is how I develop these independently and then link then up somehow... Imaging there was different teams developing the various stacks and pipelines - how do they need to coordinate?

## DynamoDB Design

> _**Note**_: As of 2022-09-28 I started to refactor the DynamoDB design as I realized I was still thinking in terms of RDBMS when I did the initial design. The data itself will obviously not change, but I am going to have to rethink the current implementation in order to facilitate the concept of `joins` ([a RDBMS definition](https://en.wikipedia.org/wiki/Join_(SQL))). I am going to base the new approach on [this article](https://dynobase.dev/dynamodb-joins/), especially in view of the phase where I am now where I need to create a Lambda function for the web site API call to view all access cards issued to employees. The query requires me to retrieve both the access card detail, the employee detail and also the linking details (like the status of the current issued card, who issued it etc.).

For this exercise, all data will be gathered in 1x DynamoDB table. Even though the HR system may have their own application sets and table(s), this particular table is for associating employees with access cards as well as tracking which the access card usage status, relative to a building (when applicable).

As such, I started with a composite key design with the following structure:

```text
+----------------------------------------------------------------------------------+----------------------------------------------------------------+
| Primary Key                                                                      | Attributes                                                     |
+-------------------------+--------------------------------------------------------+                                                                |
| Partition Key (PK)      | Sort Key (ST)                                          |                                                                |
| Name: PK                | Name: SK                                               |                                                                |
+-------------------------+--------------------------------------------------------+----------------------------------------------------------------+
|                         |                                                        |                                                                |
| EMP#<<employee ID>>     | PERSON#PERSONAL_DATA                                   | - PersonName                                                   |
|                         |                                                        | - PersonSurname                                                |
|                         |                                                        | - PersonDepartment                                             |
|                         |                                                        | - PersonStatus (onboarding|active|inactive)                    |
|                         |                                                        | - EmployeeId                                                   |
|                         |                                                        |                                                                |
|                         | PERSON#PERSONAL_DATA#ACCESS_CARD                       | - CardIssuedTimestamp                                          |
|                         |                                                        | - CardRevokedTimestamp                                         |
|                         |                                                        | - CardStatus (issued|lost|stolen|expired|revoked)              |
|                         |                                                        | - CardIssuedTo (<<employee ID>>)                               |
|                         |                                                        | - CardIssuedBy (<<employee ID>>)                               |
|                         |                                                        | - CardIdx (<<access card ID>>#<<timestamp>>)                   |
|                         |                                                        | - ScannedBuildingIdx                                           |
|                         |                                                        | - ScannedStatus (scanned-in|scanned-out)                       |
|                         |                                                        |                                                                |
| CARD#<<Access card ID>> | CARD#STATUS#issued                                     | - CardIssuedTo (<<employee ID>>)                               |
|                         |   NOTE: status in ( 'available', 'issued', 'blocked' ) | - CardIssuedBy (<<employee ID>>)                               |
|                         |                                                        | - CardIssuedTimestamp                                          |
|                         |                                                        |                                                                |
|                         | CARD#EVENT#SCANNED                                     | - ScannedInTimestamp (<<timestamp>>)                           |
|                         |                                                        | - BuildingIdxWhereScanned (<<building ID>>)                    |
|                         |                                                        | - ScannedInEmployeeId (<<employee ID>>)                        |
|                         |                                                        | - ScannedStatus (scanned-in|scanned-out)                       |
|                         |                                                        | - ScannedStatusComment (default="scanned normally")            |
|                         |                                                        | - PersonName                                                   |
|                         |                                                        | - PersonSurname                                                |
|                         |                                                        |                                                                |
+-------------------------+--------------------------------------------------------+----------------------------------------------------------------+
```

Global Secondary Indexes:

```text
+-------------------------------------------------------------------------+------------------+
| Primary Key                                                             | Index Name       |
+---------------------------------+---------------------------------------|                  |
| Partition Key (PK)              | Sort Key (ST) Attribute               |                  |
+---------------------------------+---------------------------------------+------------------+
| CardIdx                         | PK                                    | CardIssuedIdx    |
| ScannedBuildingIdx              | PK                                    | OccupancyIdx     |
+---------------------------------+---------------------------------------+------------------+
```

Deploying the table can be done with the following command:

```shell
aws cloudformation deploy \
    --stack-name $DYNAMODB_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/1000_dynamodb.yaml
```

## Pre-populating Data

A python script is provided to pre-populate the table with some initial data. The script can be located in the file [`prepopulate_data.py`](prepopulate_data.py)

Assuming the environment variables are set (as per the exports table), the supplied credentials must be sufficient to write to DynamoDB.

Each time the script run, it will assume it starts with an empty table.

> _**IMPORTANT**_: Delete the stack, recreate the stack and then run the script

> _**WARNING**_: This may take a while and is an expensive operation!

Typical run:

```shell
aws cloudformation delete-stack --stack-name $DYNAMODB_STACK_NAME

# WAIT UNTIL STACK IS DELETED ....

aws cloudformation deploy \
    --stack-name $DYNAMODB_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/1000_dynamodb.yaml

# WAIT UNTIL STACK IS DONE

python3 labs/lab3-non-kinesis-example/prepopulate_data.py
```

To test, you can run the following command to get the full logging and final output:

```shell
python3 labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/list_employee_ids.py 2>&1 1>/dev/null | less
```

## Lambda Function for Listing Employee ID's

The Lambda function will have the following characteristics:

* Supports only the GET method
* Query string variables: 
    * `max-items` - INTEGER - min. 10 and max. 100, default=25
    * `start` STRING - index key to start again (as returned by a previous query)

The Lambda function is located in the file [`list_employee_ids.py`](lambda_functions/list_employee_ids/list_employee_ids.py)

## Lambda Function For getting the status of a specific employee and their access card

TODO

## Lambda Function(s) for Linking an employee ID, Access Card and Building ID with an initial default building status of `INSIDE`

TODO

## Lambda Function Deployment

Each Lambda function must be zipped and uploaded to S3:

```shell
rm -vf labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/list_employee_ids_lambda_function.zip

cd labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/ && zip list_employee_ids_lambda_function.zip list_employee_ids.py && cd $OLDPWD 

aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/list_employee_ids_lambda_function.zip s3://$ARTIFACT_S3_BUCKET_NAME/list_employee_ids_lambda_function.zip
```

All Lambda functions are defined in a single CloudFormation template that can be deployed with:

Deploying the table can be done with the following command:

```shell
aws cloudformation deploy \
    --stack-name $LAMBDA_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/2000_lambda_functions.yaml \
    --parameter-overrides S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
    --capabilities CAPABILITY_NAMED_IAM
```

# Infrastructure Components 

## VPC and Proxy Server

The lab relies on a private and public VPC and use a Proxy Server for Internet access from the Private VPC. Run the following command to provision the resources:

```shell
aws cloudformation deploy \
    --stack-name $VPC_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/3000_vpc_setup.yaml

aws cloudformation deploy \
    --stack-name $DNS_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/3100_dns.yaml \
    --parameter-overrides VpcStackNameParam="$VPC_STACK_NAME"

aws cloudformation deploy \
    --stack-name $PROXY_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/3300_proxy_server.yaml \
    --parameter-overrides VpcStackNameParam="$VPC_STACK_NAME" DnsStackNameParam="$DNS_STACK_NAME" Ec2KeyPairKeyNameParam="$EC2_KEYPAIR_KEY_NAME" \
    --capabilities CAPABILITY_NAMED_IAM
```

Basic VPC design:

![VPC Design](../../images/vpc_design.png)

> _**Interesting Observation**_: The proxy server responds with a HTTP code 400 during health checks. This is actually OK, and therefore the 400 code is used in the Target Group health checks to assume a healthy state.

## Serving of a web site from EC2 (private only), accessed via a proxy server in a Public VPC

As a demonstration, I wanted to synchronize the web site static files from GitHub to the FSX file system. The static web site artifacts is kept in a separate [GitHub repository](https://github.com/nicc777/exploring-aws-kinesis-static-website) as I needed to create a webhook in that repository that will call a URL from a Lambda Function that will trigger the internal processes to synchronize the static content with the FSX volume. Any commit in that repository should therefore trigger the web hook.

> _**Important Pre-Requisite**_: A SSH key must be available in order to create a copy of that key in Secrets Manager, that can later be accessed to connect to GitHub and synchronize the web site.

To create the OpenZFS NFS Filesystem that will host the website static content, run the following command:

```shell
aws cloudformation deploy \
    --stack-name $NFS_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/4000_fsx_filesystem.yaml \
    --parameter-overrides VpcStackName="$VPC_STACK_NAME"

aws cloudformation deploy \
    --stack-name $GITHUB_SECRET_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/4100_github_secret.yaml

# Assuming your GitHub SSH key is in the file ~/.ssh.github_key.pem, run the following command:
export GITHUB_KEY=`cat ~/.ssh/github_key.pem`

# Get the newly created secret ARN
export GITHUB_SECRET_ID=`aws cloudformation describe-stacks --stack-name $GITHUB_SECRET_STACK_NAME | jq -r ".Stacks[0].Outputs[0].OutputValue"`

# Load the SSH key data into the secret
aws secretsmanager put-secret-value --secret-id $GITHUB_SECRET_ID --secret-string "$GITHUB_KEY"

# SSH key data no longer required - ensure it is removed from our environment data
unset GITHUB_KEY

export PYTHON_REQUIREMENTS_FILE_URL="https://raw.githubusercontent.com/nicc777/exploring-aws-kinesis/main/labs/lab3-non-kinesis-example/scripts/github_sync/github_sync.py"
export PYTHON_SCRIPT_SRC_URL="https://raw.githubusercontent.com/nicc777/exploring-aws-kinesis/main/labs/lab3-non-kinesis-example/scripts/github_sync/github_sync.py"

rm -vf labs/lab3-non-kinesis-example/lambda_functions/github_webhook_lambda/github_webhook_lambda.zip
cd labs/lab3-non-kinesis-example/lambda_functions/github_webhook_lambda/ && zip github_webhook_lambda.zip github_webhook_lambda.py && cd $OLDPWD 
aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/github_webhook_lambda/github_webhook_lambda.zip s3://$ARTIFACT_S3_BUCKET_NAME/github_webhook_lambda.zip

rm -vf labs/lab3-non-kinesis-example/lambda_functions/github_syncserver_starter_lambda/github_syncserver_starter_lambda.zip
cd labs/lab3-non-kinesis-example/lambda_functions/github_syncserver_starter_lambda/ && zip github_syncserver_starter_lambda.zip github_syncserver_starter_lambda.py && cd $OLDPWD 
aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/github_syncserver_starter_lambda/github_syncserver_starter_lambda.zip s3://$ARTIFACT_S3_BUCKET_NAME/github_syncserver_starter_lambda.zip

rm -vf labs/lab3-non-kinesis-example/lambda_functions/access_token_requestor/access_token_requestor.zip
cd labs/lab3-non-kinesis-example/lambda_functions/access_token_requestor/ && zip access_token_requestor.zip access_token_requestor.py && cd $OLDPWD 
aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/access_token_requestor/access_token_requestor.zip s3://$ARTIFACT_S3_BUCKET_NAME/access_token_requestor.zip

aws cloudformation deploy \
    --stack-name $GITHUB_SYNC_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/4200_github_deployment_resources.yaml \
    --parameter-overrides VpcStackNameParam="$VPC_STACK_NAME" \
        GitHubSecretStackNameParam="$GITHUB_SECRET_STACK_NAME" \
        DnsStackNameParam="$DNS_STACK_NAME" \
        ProxyServerStackNameParam="$PROXY_STACK_NAME" \
        FsxStackNameParam="$NFS_STACK_NAME" \
        PythonRequirementsFileParam="$PYTHON_REQUIREMENTS_FILE_URL" \
        PythonScriptFile="$PYTHON_SCRIPT_SRC_URL" \
        S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
        SupportedRepositoriesParam=$SUPPORTED_REPOSITORIES \
        GitHubAuthorizedSendersParam=$GITHUB_AUTHORIZED_SENDERS \
    --capabilities CAPABILITY_NAMED_IAM


aws cloudformation deploy \
    --stack-name $COGNITO_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5000_employee_cognito_pool.yaml \
    --parameter-overrides CallbackUrl="https://internal.${ROUTE53_PUBLIC_DNSNAME}/callback.html" \
        PublicDnsNameParam="$ROUTE53_PUBLIC_DNSNAME" \
        Email="$EMPLOYEE_1_EMAIL"


export COGNITO_USER_POOL_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME | jq -r '.Stacks[].Outputs[] | select(.OutputKey == "CognitoAuthorizerUserPoolId") | {OutputValue}' | jq -r '.OutputValue'`
export COGNITO_ISSUER_URL=`curl https://cognito-idp.${AWS_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}/.well-known/openid-configuration | jq -r ".issuer" -`
export COGNITO_CLIENT_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME | jq -r '.Stacks[].Outputs[] | select(.OutputKey == "CognitoAlbUserPoolClientId") | {OutputValue}' | jq -r '.OutputValue'`

# NOTE: The COGNITO_CLIENT_ID is also the AUDIENCE value fo the API Authorizer

# WEB_SERVER_STACK_NAME
export TRUSTED_IP=$(curl http://checkip.amazonaws.com/)

aws cloudformation deploy \
    --stack-name $WEB_SERVER_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5100_web_server.yaml \
    --parameter-overrides VpcStackNameParam="$VPC_STACK_NAME" \
        DnsStackNameParam="$DNS_STACK_NAME" \
        FirstTrustedInternetCiderParam="$TRUSTED_IP" \
        FsxStackNameParam="$NFS_STACK_NAME" \
        PublicDnsHostedZoneIdParam="$ROUTE53_PUBLIC_ZONEID" \
        PublicDnsNameParam="$ROUTE53_PUBLIC_DNSNAME" \
        CognitoStackNameParam="$COGNITO_STACK_NAME" \
        S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
    --capabilities CAPABILITY_NAMED_IAM
```

> In EC2 instances, the FSX volume can be mounted with the command: `mkdir /data && mount -t nfs fs-aaaaaaaaaaaaaaaaa.fsx.eu-central-1.amazonaws.com:/fsx /data`

### Capturing Proxy Request Data to the Docker Containers

I previously used a hacky way to obtain the Access Token, but now I have decided to deploy a Lambda function as part of the INternal site's ELB target groups that will receive the access token and echo that back.

Assuming the website domain is `example.tld`, then the URL of this Lambda function will be `https://internal.example.tld:8443/access-token-request`

Below is an example payload:

```json
{
    "AccessTokenData": "...",
    "OidcIdentity": "... #Not a JWT - just a unique ID string",
    "OidcData": "..."
}
```

The access token payload section has the following structure:

```json
{
  "sub": "... #same value as the 'OidcIdentity' field",
  "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_aaaaaaaaa",
  "version": 2,
  "client_id": "...",
  "origin_jti": "...",
  "event_id": "...",
  "token_use": "access",
  "scope": "openid",
  "auth_time": 1664248370,
  "exp": 1664251970,
  "iat": 1664248370,
  "jti": "...",
  "username": "email-address@example.tld"
}
```

The `OidcData` JWT token has the following payload structure:

```json
{
  "sub": ".. #same value as the 'OidcIdentity' field",
  "email": "email-address@example.tld",
  "username": "email-address@example.tld",
  "exp": 1664248564,
  "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_aaaaaaaaa"
}
```

### Testing the API from the command line with the JWT Access Token

Assuming you have the value of the access token, run the following:

```shell
# Paste the value of the access token here...
export JWT_TOKEN="..."

# Query the API:
curl -H "Authorization: ${JWT_TOKEN}" https://internal-api.your_domain.tld/access-card-app/employees
```

## Handling Updates to Static Web Pages

I want to try the following design:

![GitHub Sync Server](../../images/github_sync_server_design.png)

The basic idea is that any commits to a certain repository will then call the Lambda function (Exposed by a URL). The information from the call will be parsed (details still unknown) and from that information a message will be placed on SQS.

A second Lambda function will be triggered on a timed event and get the number of SQS messages in the queue. If the qty is more than 0, the Lambda function will check if an instance of the Sync Server is already running. If not, it will create the server instance based on a Launch Template.

The server instance, once started, will have a small script that consumes the SQS messages and clone/pull changes from Git as well as run the relevant deployment scripts. If no more SQS messages are available for more than 5 minutes, the instance self-terminates. EVentually I hope to achieve all of this with Jenkins running a pipeline - all dynamically configured by what I hope could be in the SQS message.

### GitHub Web Hooks

I configured the repository [exploring-aws-kinesis-static-website](https://github.com/nicc777/exploring-aws-kinesis-static-website) to point to the Lambda URL from the stack `GITHUB_SYNC_STACK_NAME`.

To get the Lambda function URL, run the following command:

```shell
aws lambda get-function-url-config --function-name "GitHubWebhookLambdaFunction" --output json | jq ".FunctionUrl" | awk -F\" '{print $2}' 
```

The output will be something like `https://abcdefghijklmnopqrstuvwxyz.lambda-url.eu-central-1.on.aws/`

For this lab/experiment I configured the webhook only for `Release` events. I created a pre-release tagged `r0.0.2-SNAPSHOT` and the Lambda function got the event as [documented here](lambda-event-example-payload-github-release-event.json).

The actual body is what is of interest, and [it contained](lambda-event-example-payload-body-payload-from-github.json) the release data generated by GitHub for the release.

The webhook Lambda function will parse the data and place the relevant information on SQS.

For security reasons, the Lambda function will check via environment variables which changes to accept from GitHub, matching both the author login field (set as a comma separated list of approved logins in the `SUPPORTED_SENDER_LOGINS` environment variable) and the whitelisted of repository (matching the repository `full_name` field with the comma separated list of approved values in the `SUPPORTED_REPOSITORIES` environment variable).

Any non-matching event will be silently ignored. The exact same response is always send back to the caller regardless of the final outcome. The reasoning behind such behavior is to not give potentially helpful clues to bad actors.

### Managing the GitHub Sync Server

An AWS Event Bridge Rule will trigger every 10 minutes to see there are new messages on the SQS queue. If so, it will check if an instance of the Sync Server is already running. If not, it will start a new instance from the latest version of the configured Launch Template.

### Handling the SQS Payload

On the GitHub Sync Server, the SQS message that is consumed has the following structure:

```json
{
    "MessageId": "00000000-0000-0000-0000-000000000000",
    "ReceiptHandle": "...",
    "MD5OfBody": "a3ae2d07c63565639ed3d97840f07675",
    "Body": "{\"repository\": \"nicc777/exploring-aws-kinesis-static-website\", \"tag_name\": \"r0.0.7-TEST\", \"tar_file\": \"https://api.github.com/repos/nicc777/exploring-aws-kinesis-static-website/tarball/r0.0.7-TEST\"}",
    "Attributes": {
        "SenderId": "...:GitHubWebhookLambdaFunction",
        "ApproximateFirstReceiveTimestamp": "1663122760567",
        "ApproximateReceiveCount": "1",
        "SentTimestamp": "1663122317176"
    }
}
```

Also note that the system includes the following in `/etc/environment`:

```text
GITHUB_WORKDIR=/data/github
```

Therefore, the basic steps to deploy the new release is as follows:

* Parse `/etc/environment` - the `GITHUB_WORKDIR` is set to the temporary workspace `/data/github`
* Retrieve the remote `tar_file` (as defined in the SQS message) and save in `GITHUB_WORKDIR`
* Identify every directory that was in the tar file, and then loop through them, changing into each directory and run the file `deploy.sh` if present
* Once done, delete all artifacts (tar file and directories/files created during the archive extraction)

When the process runs, you can expect files to be created as shown in the example below:

```shell
# This is inside GITHUB_WORKDIR
sh-4.2$ ls -lahrt /data/github/
total 30K
drwxrwxrwx 5 root      root         5 Sep 14 04:22 ..
-rw-r--r-- 1 ec2-user  ec2-user  2.0K Sep 14 05:20 download-1663132816-8jdl2tfs.tar.gz
drwxr-xr-x 3 ec2-user  ec2-user     3 Sep 14 05:20 untarred-1663132816-eujrkgh0
drwxrwxrwx 3 nfsnobody nfsnobody    4 Sep 14 05:20 .


# Looking inside the temporary directory for the untarred archive
sh-4.2$ ls -lahrt /data/github/untarred-1663132816-eujrkgh0/
total 34K
drwxrwxr-x 4 ec2-user  ec2-user  7 Sep 10 14:56 nicc777-exploring-aws-kinesis-static-website-6962cbf
drwxrwxrwx 3 nfsnobody nfsnobody 4 Sep 14 05:20 ..
drwxr-xr-x 3 ec2-user  ec2-user  3 Sep 14 05:20 .


# The contents of one of the directories from the untarred archive, which should correspond to the contents of the MAIN branch on GitHub
sh-4.2$ ls -lahrt /data/github/untarred-1663132816-eujrkgh0/nicc777-exploring-aws-kinesis-static-website-6962cbf/
total 48K
drwxrwxr-x 2 ec2-user ec2-user    3 Sep 10 14:56 public-website
drwxrwxr-x 2 ec2-user ec2-user    3 Sep 10 14:56 private-website
-rw-rw-r-- 1 ec2-user ec2-user  182 Sep 10 14:56 README.md
-rw-rw-r-- 1 ec2-user ec2-user 1.1K Sep 10 14:56 LICENSE
-rw-rw-r-- 1 ec2-user ec2-user 1.6K Sep 10 14:56 .gitignore
drwxrwxr-x 4 ec2-user ec2-user    7 Sep 10 14:56 .
drwxr-xr-x 3 ec2-user ec2-user    3 Sep 14 05:20 ..
```

## Web API Stack (AWS API Gateway)

These commands can be used to deploy the stack for creating the AWS API Gateway resources that will handle mostly interaction with the Website:

```shell
rm -vf labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/list_employee_ids.zip
cd labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/ && zip list_employee_ids.zip list_employee_ids.py && cd $OLDPWD 
aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/list_employee_ids/list_employee_ids.zip s3://$ARTIFACT_S3_BUCKET_NAME/list_employee_ids.zip

rm -vf labs/lab3-non-kinesis-example/lambda_functions/employee_access_card_status/employee_access_card_status.zip
cd labs/lab3-non-kinesis-example/lambda_functions/employee_access_card_status/ && zip employee_access_card_status.zip employee_access_card_status.py && cd $OLDPWD 
aws s3 cp labs/lab3-non-kinesis-example/lambda_functions/employee_access_card_status/employee_access_card_status.zip s3://$ARTIFACT_S3_BUCKET_NAME/employee_access_card_status.zip

aws cloudformation deploy \
    --stack-name $WEBAPI_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5200_web_site_api_resources.yaml \
    --parameter-overrides CognitoStackNameParam="$COGNITO_STACK_NAME" \
        CognitoIssuerUrlParam="$COGNITO_ISSUER_URL" 

aws cloudformation deploy \
    --stack-name $WEBAPI_LAMBDA_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5225_web_site_api_lambda_functions.yaml \
    --parameter-overrides S3SourceBucketParam="$ARTIFACT_S3_BUCKET_NAME" \
        DynamoDbStackName="$DYNAMODB_STACK_NAME" \
    --capabilities CAPABILITY_NAMED_IAM


export LAMBDA_1_ARN=`aws cloudformation describe-stacks --stack-name $WEBAPI_LAMBDA_STACK_NAME | jq -r '.Stacks[].Outputs[] | select(.OutputKey == "EmployeeRecordsQueryLambdaFunctionArn") | {OutputValue}' | jq -r '.OutputValue'`
aws cloudformation deploy \
    --stack-name $WEBAPI_ROUTES_1_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5250_web_site_api_routes_and_integrations.yaml \
    --parameter-overrides ApiGatewayStackNameParam="$WEBAPI_STACK_NAME" \
        LambdaFunctionArnParam="$LAMBDA_1_ARN" \
        LambdaSourcePathParam="/access-card-app/employees" \
        RouteKeyParam="/access-card-app/employees" \
        HttpMethodParam="GET" \
    --capabilities CAPABILITY_NAMED_IAM

export LAMBDA_2_ARN=`aws cloudformation describe-stacks --stack-name $WEBAPI_LAMBDA_STACK_NAME | jq -r '.Stacks[].Outputs[] | select(.OutputKey == "ListAccessCardStatusLambdaFunctionArn") | {OutputValue}' | jq -r '.OutputValue'`
aws cloudformation deploy \
    --stack-name $WEBAPI_ROUTES_2_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5250_web_site_api_routes_and_integrations.yaml \
    --parameter-overrides ApiGatewayStackNameParam="$WEBAPI_STACK_NAME" \
        LambdaFunctionArnParam="$LAMBDA_2_ARN" \
        LambdaSourcePathParam="/access-card-app/employee/*/access-card-status" \
        RouteKeyParam="/access-card-app/employee/{employeeId}/access-card-status" \
        HttpMethodParam="GET" \
    --capabilities CAPABILITY_NAMED_IAM

aws cloudformation deploy \
    --stack-name $WEBAPI_DEPLOYMENT_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/5275_web_site_api_deployment.yaml \
    --parameter-overrides WebServerStackName="$WEB_SERVER_STACK_NAME" \
        PublicDnsNameParam="$ROUTE53_PUBLIC_DNSNAME" \
        PublicDnsHostedZoneIdParam="$ROUTE53_PUBLIC_ZONEID" \
        ApiGatewayStackNameParam="$WEBAPI_STACK_NAME"
```

## Event Infrastructure

### S3 Events Bucket Resources

> _**Note**_: The S3 bucket has a retention policy and therefore the creation is more a once-off kind of thing. If you need to delete the bucket, you need to wait until the last object's lock has been removed and then delete all objects, and then delete the stack. Alternatively, you can delete the stack but keep the S3 bucket.

The S3 bucket can be deployed with the following commands:

```shell
export S3_EVENTS_STACK_NAME="..."
export S3_EVENTS_BUCKET_NAME="..."

aws cloudformation deploy \
    --stack-name $S3_EVENTS_STACK_NAME \
    --template-file labs/lab3-non-kinesis-example/cloudformation/6000_s3_events_bucket.yaml \
    --parameter-overrides S3EventBucketParam="$S3_EVENTS_BUCKET_NAME" \
    --capabilities CAPABILITY_NAMED_IAM
```

# Random Thoughts

Something that occurred to me while I was designing this solution was to think about why I would still expose certain applications via EC2 - why not have everything as serverless?

The fact is that sometimes we still have to deal with off-the-shelve products, and I am treating this web app as a typical example. In theory I could also just host it directly from S3, but I would like to use this opportunity to exercise some other concepts as well, even though they may not be too high on the cool-scale.
