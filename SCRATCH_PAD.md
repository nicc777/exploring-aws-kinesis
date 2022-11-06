# Random Thoughts and other Scribbles

This is just a file where I keep some notes with the intention to later move it into one of the main README files if that will add value. Over time, some notes here will just be discarded and deleted.

# Todo Items or List

Instead of a page to see the status, I thought I would just create a general search page that could search for the following info:

* Lookup an access card ID and display:
    * Current Status
    * If linked to a person, include a link to the person profile (another "search")
    * The last 10 card events, with a button to retrieve more
* Lookup an Employee and display:
    * Employee Profile
    * Current Building, if known
    * The last 10 card events, with a button to retrieve more
* Lookup a building and display:
    * The current scanned in employees for that building, with a link to the Employee Lookup result for each employee
    * The card used for the scan, linked to the Card Lookup result for each card

This would require Lambda functions for the API Gateway:

| Site Function                 | Lambda Function Name      | Implemented | Notes                                                                                                                                                                     |
|-------------------------------|---------------------------|:-----------:|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Lookup access card            | `api_search_cards.py`     | NO          | Accepts a card ID or Card Issuer or Employee ID as input (a number with the type of number). Criteria can include "EQUAL" (default), "CONTAINS" or "ENDS-WIDTH"           |
| Lookup employee profile       | `api_search_employee.py`  | NO          | Accepts a card ID or Card Issuer or Employee ID as input (a number with the type of number). Criteria can include "EQUAL" (default), "CONTAINS" or "ENDS-WIDTH"           |
| Lookup building occupancy     | `api_search_occupancy.py` | NO          | Accepts campus ID and returns list of employee card profiles (PK = `EMP#<<id>>` and SK = `PERSON#PERSONAL_DATA#ACCESS_CARD`).                                             |

# Design Thoughts...

Nothing new yet...