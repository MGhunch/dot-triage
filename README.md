# Dot Triage

New job setup for Hunch agency workflow.

## What it does

Processes incoming briefs and creates new jobs:
- Extracts client, project owner, job name
- Generates job number (e.g., TOW 023)
- Creates project record in Airtable
- Returns formatted triage summary

## Endpoint

`POST /triage`

### Input

```json
{
  "emailContent": "Forwarded brief or new job request..."
}
```

### Output

```json
{
  "jobNumber": "TOW 023",
  "jobName": "December Newsletter",
  "clientCode": "TOW",
  "clientName": "Tower Insurance",
  "projectOwner": "Sarah Jones",
  "teamId": "19:abc123...",
  "sharepointUrl": "https://...",
  "jobRecordId": "recXXX",
  "emailBody": "<b>Client:</b> Tower Insurance<br>..."
}
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Claude API key
- `AIRTABLE_API_KEY` - Airtable API key

## Deployment

Deploy to Railway. Add environment variables. Done.
