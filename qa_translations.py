#!/usr/bin/env python3
"""QA pass on translations - review and improve awkward Finnish."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Validate config
def check_config():
    errors = []
    if not os.getenv('AWS_ACCESS_KEY') or not os.getenv('AWS_SECRET_ACCESS_KEY'):
        errors.append("AWS credentials not set (AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY)")
    if not os.getenv('GOOGLE_SPREADSHEET_ID'):
        errors.append("GOOGLE_SPREADSHEET_ID not set")
    if not (PROJECT_ROOT / 'service-account.json').exists():
        errors.append("service-account.json not found")
    if errors:
        print("ERROR: Missing configuration:")
        for e in errors:
            print(f"  - {e}")
        print("\nSee .env.example and setup_service_account.md")
        exit(1)

check_config()

# Bedrock client
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'eu-north-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    config=Config(read_timeout=120)
)

# Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT = PROJECT_ROOT / 'service-account.json'
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')


def call_claude(prompt: str) -> str:
    response = bedrock.invoke_model(
        modelId='eu.anthropic.claude-sonnet-4-20250514-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    result = json.loads(response['body'].read())
    return result['content'][0]['text']


def review_translation(english: str, finnish: str, max_chars: int) -> dict:
    """Review a translation and suggest improvements if needed."""
    
    prompt = f"""You are a Finnish language expert reviewing translations for voiceover narration.

ENGLISH: {english}
CURRENT FINNISH: {finnish}
MAX LENGTH: {max_chars} characters

Review the Finnish translation. Check for:
1. Awkward literal translations (e.g., "järjestelmän vuodot" instead of "vuotojen varalta")
2. Unnatural word order
3. Missing articles or particles that Finnish needs
4. Technical terms that sound wrong in context
5. Length - must fit within {max_chars} chars

If the translation is GOOD, respond with just: OK

If it needs improvement, respond with ONLY the improved Finnish text (no explanation).
Keep it natural spoken Finnish, concise, within the character limit."""

    result = call_claude(prompt).strip()
    
    if result.upper() == 'OK' or result == finnish:
        return {'status': 'OK', 'improved': ''}
    else:
        # Verify it's within limit
        if len(result) <= max_chars:
            return {'status': 'IMPROVED', 'improved': result}
        else:
            return {'status': 'TOO_LONG', 'improved': result[:max_chars]}


def main():
    print("Connecting to Google Sheets...")
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT), scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.sheet1
    
    # Get all data
    print("Fetching data...")
    all_data = sheet.get_all_values()
    headers = all_data[0]
    rows = all_data[1:]
    
    # Find column indices
    try:
        eng_col = headers.index('English')
        fin_col = headers.index('Finnish')
        max_col = headers.index('Max Chars (~15.5/s)')
        status_col = headers.index('Status')
    except ValueError as e:
        print(f"Column not found: {e}")
        return
    
    # Add new columns if not present
    if 'QA Status' not in headers:
        headers.append('QA Status')
        headers.append('Improved Finnish')
        sheet.update_cell(1, len(headers)-1, 'QA Status')
        sheet.update_cell(1, len(headers), 'Improved Finnish')
    
    qa_col = len(headers) - 1  # QA Status
    imp_col = len(headers)      # Improved Finnish
    
    print(f"Reviewing {len(rows)} translations...")
    
    updates = []
    for i, row in enumerate(rows):
        if len(row) <= eng_col or not row[eng_col]:
            continue
            
        english = row[eng_col]
        finnish = row[fin_col] if len(row) > fin_col else ''
        max_chars = int(row[max_col]) if len(row) > max_col and row[max_col].isdigit() else 200
        
        if not finnish:
            continue
        
        print(f"  [{i+1}/{len(rows)}] Reviewing: {finnish[:40]}...")
        
        try:
            result = review_translation(english, finnish, max_chars)
            updates.append({
                'row': i + 2,  # +2 for header and 0-index
                'qa_status': result['status'],
                'improved': result['improved']
            })
            
            if result['status'] == 'IMPROVED':
                print(f"    → {result['improved'][:50]}...")
        except Exception as e:
            print(f"    Error: {e}")
            updates.append({
                'row': i + 2,
                'qa_status': 'ERROR',
                'improved': ''
            })
    
    # Batch update the sheet
    print("\nUpdating sheet...")
    for u in updates:
        sheet.update_cell(u['row'], qa_col, u['qa_status'])
        if u['improved']:
            sheet.update_cell(u['row'], imp_col, u['improved'])
    
    improved_count = sum(1 for u in updates if u['qa_status'] == 'IMPROVED')
    print(f"\nDone! {improved_count} translations improved out of {len(updates)}")


if __name__ == '__main__':
    main()
