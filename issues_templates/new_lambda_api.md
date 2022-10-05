Input: 

* Employee ID

Output:

If no access card is linked yet:

```json
{
  "AccessCardLinked": false,
  "EmployeeStatus": "...",
  "Name": "...",
  "Surname": "..."
}
```

If a linked access card is found:

```json
{
  "AccessCardLinked": true,
  "EmployeeStatus": "...",
  "Name": "...",
  "Surname": "..."
   "AccessCardData": {
    "CardId": "...",
    "IssuedTimeStamp": 123,
    "IssuedBy": "..."
  }
}
```

API end-point:

* Request Type: `GET`
* `/access-card-app/employee/<<employee-id>>/access-card-status`
* Query string parameters: None
* Requires authentication (JWT): Yes