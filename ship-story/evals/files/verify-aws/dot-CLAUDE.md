# Contact API

Serverless backend for the marketing site's contact form.

Issue tracker: Jira (project DAVE)

## Checks

- `npm run lint`
- `npm test`

## Deploy

Merging to `main` deploys the `contact-api` CloudFormation stack via GitHub Actions.
The form handler is the Lambda function `contact-form-handler` (logs in
`/aws/lambda/contact-form-handler`); accepted submissions are published to the SQS
queue `contact-intake`.
