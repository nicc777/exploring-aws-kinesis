# Random Thoughts and other Scribbles

This is just a file where I keep some notes with the intention to later move it into one of the main README files if that will add value. Over time, some notes here will just be discarded and deleted.

# Todo Items or List

Some next steps I'm thinking about (Lab 3)...

* ~~Create Lambda function `employee-access-card-status` with API end-point~~
* ~~Create S3 Events bucket~~
* ~~Create Lambda function `link-employee-and-card` with API end-point. Persist events in directory `/employee-access-card-link-events`~~
* Create a UI to link an access card to a person busy onboarding.
* Create UI to view (and poll) for card linking status
* Create Lambda function `s3_event_handler` with SNS and SQS integration from the S3 events bucket
* Create SNS Topic and SQS queue to pass on processed event from `s3_event_handler`
* Create Lambda function `link-employee-and-card-persist` to persist the new linked data in the DynamoDB table

I also need to add CognitoID to the DynamoDB table for any employee with a login. This is important to link the person requesting the linking of another employee to an access card for Audit purposes. With the Cognito link and the JWT that was authorized, it will be virtually impossible to dispute the event origin.

Create a new index in DynamoDB with Partition Key `CognitoSubjectId` and sort key `SK`

Add appropriate scope to the employee allowed to link access cards and ensure that is enforced on the API Gateway.

# Design Thoughts...

## Issuing of an Access Card

### UI Elements

Basic flow:

* Enter a person ID
* System retrieves person details and displays the data on screen
* If the person status is `onboarding`, add a link to issue access card. 
* User clicks on link and a text box is made visible to enter an access card ID (the idea here is that the user has the physical access card in their hands, and therefor know they can issue it to the person).
* The form is submitted
* The screen now changes to a waiting state for confirmation (poling `employee-access-card-status` API end point). If no positive response is received after 1 minute, display a warning message to check back again later

API Entry point and validation

* The API Lambda function `link-employee-and-card` accepts the input for Employee ID and Access Card nr
* Retrieve the employee record
* Retrieve the access card record
* Validate the access card can be issued (based on several rules - see below)
* Create a command event and put the object in the S3 event bucket

