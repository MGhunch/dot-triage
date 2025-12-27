# Dot Triage
# New job setup for Hunch agency
# Standalone version - no external dependencies

import os
import json
from datetime import date
from flask import Flask, request, jsonify
from anthropic import Anthropic
import httpx

app = Flask(__name__)

# ===================
# CONFIG
# ===================

AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = 'app8CI7NAZqhQ4G1Y'
AIRTABLE_PROJECTS_TABLE = 'Projects'
AIRTABLE_CLIENTS_TABLE = 'Clients'

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

# Anthropic client
anthropic_client = Anthropic(
    api_key=ANTHROPIC_API_KEY,
    http_client=httpx.Client(timeout=60.0, follow_redirects=True)
)

# Load prompt
PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompt.txt')
with open(PROMPT_PATH, 'r') as f:
    TRIAGE_PROMPT = f.read()


# ===================
# HELPERS
# ===================

def strip_markdown_json(content):
    """Strip markdown code blocks from Claude's JSON response"""
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    return content.strip()


def _get_airtable_headers():
    """Get standard Airtable headers"""
    return {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}',
        'Content-Type': 'application/json'
    }


# ===================
# AIRTABLE FUNCTIONS
# ===================

def get_client_by_code(client_code):
    """Look up client by code.
    
    Returns client details including Teams ID, SharePoint URL, next job number.
    """
    if not AIRTABLE_API_KEY:
        print("No Airtable API key configured")
        return None
    
    try:
        search_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CLIENTS_TABLE}"
        params = {'filterByFormula': f"{{Client code}}='{client_code}'"}
        
        response = httpx.get(search_url, headers=_get_airtable_headers(), params=params, timeout=10.0)
        response.raise_for_status()
        
        records = response.json().get('records', [])
        
        if not records:
            print(f"Client code '{client_code}' not found in Airtable")
            return None
        
        record = records[0]
        fields = record['fields']
        
        return {
            'recordId': record['id'],
            'clientCode': client_code,
            'clientName': fields.get('Client', ''),
            'teamsId': fields.get('Teams ID', None),
            'sharepointUrl': fields.get('Sharepoint ID', None),
            'nextNumber': fields.get('Next #', 1)
        }
        
    except Exception as e:
        print(f"Error looking up client in Airtable: {e}")
        return None


def increment_client_job_number(client_code):
    """Increment and return the next job number for a client.
    
    Returns formatted job number (e.g., 'TOW 023') or 'TBC' on failure.
    Also returns Teams ID, SharePoint URL, and client record ID.
    """
    if not AIRTABLE_API_KEY:
        print("No Airtable API key configured")
        return f"{client_code} TBC", None, None, None
    
    try:
        client = get_client_by_code(client_code)
        
        if not client:
            return f"{client_code} TBC", None, None, None
        
        current_number = client['nextNumber']
        next_number = current_number + 1
        
        # Format job number (e.g., "TOW 023")
        job_number = f"{client_code} {str(current_number).zfill(3)}"
        
        # Update Airtable with incremented number
        update_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CLIENTS_TABLE}/{client['recordId']}"
        update_data = {'fields': {'Next #': next_number}}
        
        httpx.patch(update_url, headers=_get_airtable_headers(), json=update_data, timeout=10.0)
        
        return job_number, client['teamsId'], client['sharepointUrl'], client['recordId']
        
    except Exception as e:
        print(f"Error incrementing job number: {e}")
        return f"{client_code} TBC", None, None, None


# ===================
# TRIAGE ENDPOINT
# ===================

@app.route('/triage', methods=['POST'])
def triage():
    """Process new job triage.
    
    Accepts:
        - emailContent: The brief/request content
    
    Returns:
        - jobNumber: New job number
        - jobName: Extracted project name
        - All triage analysis fields
        - emailBody: Formatted triage summary HTML
    """
    try:
        data = request.get_json()
        email_content = data.get('emailContent', '')
        
        if not email_content:
            return jsonify({'error': 'No email content provided'}), 400
        
        # Call Claude for triage analysis
        response = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.2,
            system=TRIAGE_PROMPT,
            messages=[
                {'role': 'user', 'content': f'Email content:\n\n{email_content}'}
            ]
        )
        
        # Parse response
        content = response.content[0].text
        content = strip_markdown_json(content)
        analysis = json.loads(content)
        
        # Get job number and client info from Airtable
        client_code = analysis.get('clientCode', 'TBC')
        
        if client_code not in ['HUN', 'TBC']:
            job_number, team_id, sharepoint_url, client_record_id = increment_client_job_number(client_code)
        else:
            job_number = f'{client_code} TBC'
            team_id = None
            sharepoint_url = None
            client_record_id = None
        
        # Return complete analysis with job info
        # Power Automate handles Airtable write (needs Teams Channel ID)
        return jsonify({
            'jobNumber': job_number,
            'jobName': analysis.get('jobName', 'Untitled'),
            'clientCode': client_code,
            'clientName': analysis.get('clientName', ''),
            'projectOwner': analysis.get('projectOwner', ''),
            'teamId': team_id,
            'sharepointUrl': sharepoint_url,
            'emailBody': analysis.get('emailBody', ''),
            'fullAnalysis': analysis
        })
        
    except json.JSONDecodeError as e:
        return jsonify({
            'error': 'Claude returned invalid JSON',
            'details': str(e),
            'raw_response': content if 'content' in locals() else 'No response'
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


# ===================
# HEALTH CHECK
# ===================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Dot Triage',
        'version': '2.0'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
