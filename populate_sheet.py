#!/usr/bin/env python3
"""Populate Google Sheet with translation timing data."""

import os
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CLIENT_SECRETS = PROJECT_ROOT / 'gcp-oauth.keys.json'
TOKEN_PATH = PROJECT_ROOT / '.google_token.json'
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '')

def get_credentials():
    """Get or refresh Google credentials."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    
    return creds

def load_translation(filepath: Path) -> list:
    """Load translation JSON and extract segments."""
    data = json.loads(filepath.read_text())
    segments = data.get('segments', [])
    return segments

def main():
    print("Authenticating with Google...")
    creds = get_credentials()
    gc = gspread.authorize(creds)
    
    print(f"Opening spreadsheet...")
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    
    # Clear existing data
    sheet.clear()
    
    # Add headers
    headers = ['Video', 'Segment', 'Slot (sec)', 'Max Chars (~14/sec)', 'English Text', 'Finnish Text', 'Char Count', 'Status']
    sheet.append_row(headers)
    
    # Load translation files
    translations_dir = PROJECT_ROOT / 'transcript_elevenlabs_fi_perplexity'
    
    videos = [
        ('00_Cource_intro', '00_Cource_intro_fin_v3_short.json'),
        ('01_2_Assembling', '01_2_Assembling_fin.json'),
    ]
    
    rows = []
    for video_name, filename in videos:
        filepath = translations_dir / filename
        if not filepath.exists():
            print(f"  Skipping {filename} - not found")
            continue
            
        print(f"  Processing {video_name}...")
        segments = load_translation(filepath)
        
        for i, seg in enumerate(segments):
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            slot = round(end - start, 1)
            max_chars = int(slot * 14)
            english = seg.get('english', '')
            finnish = seg.get('finnish', '')
            char_count = len(finnish)
            status = 'OVER' if char_count > max_chars else 'OK'
            
            rows.append([video_name, i+1, slot, max_chars, english, finnish, char_count, status])
        
        # Add empty row between videos
        rows.append(['', '', '', '', '', '', '', ''])
    
    # Batch update for speed
    if rows:
        sheet.append_rows(rows)
    
    print(f"\nDone! Added {len(rows)} rows")
    print(f"View at: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")

if __name__ == '__main__':
    main()
