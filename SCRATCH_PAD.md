# Random Thoughts and other Scribbles

This is just a file where I keep some notes with the intention to later move it into one of the main README files if that will add value. Over time, some notes here will just be discarded and deleted.

# Todo Items or List

Some next steps I'm thinking about (Lab 3)...

* ~~Create Lambda function `employee-access-card-status` with API end-point~~
* ~~Create S3 Events bucket~~
* ~~Create Lambda function `link-employee-and-card` with API end-point. Persist events in directory `/employee-access-card-link-events`~~
* ~~Create a UI to link an access card to a person busy onboarding.~~
* ~~Create Lambda function `s3_event_handler` with SNS and SQS integration from the S3 events bucket~~
* ~~Create SQS queue to pass on processed event from `s3_event_handler`~~
* ~~Create Lambda function `link-employee-and-card-persist` to persist the new linked data in the DynamoDB table. Consider using step functions, as the requesting party (linked by employee) first needs to be verified. We also require the original Access Token in the payload for this! For authorization we can add an optional attribute in DynamoDB to indicate which users are authorized to do this action. These permission fields are in themselves complex object as the permission requires a start and end date for which that permission is valid, so that the event can be authorized by ensuring the event timestamp falls within this range.~~
* Create UI to view (and poll) for card linking status 

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

TODO Nothing else yet...