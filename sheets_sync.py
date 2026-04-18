#!/usr/bin/env python3
"""
Sync translations to/from Google Sheets.

Usage:
  python sheets_sync.py push              # Push all translations to sheet
  python sheets_sync.py push 00_Cource_intro  # Push specific video
  python sheets_sync.py pull              # Pull edits back to JSONs
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import json
import sys
import re
from dotenv import load_dotenv

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Language config
from lang_config import (
    get_target_lang, get_lang_name, get_translation_suffix,
    get_translation_key, get_audio_dir
)

TARGET_LANG = get_target_lang()
LANG_NAME = get_lang_name()
TRANSLATION_SUFFIX = get_translation_suffix()
TRANSLATION_KEY = get_translation_key()
AUDIO_DIR_NAME = get_audio_dir()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT = PROJECT_ROOT / 'service-account.json'
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '')
TRANSLATIONS_DIR = PROJECT_ROOT / 'translations_final'
ENGLISH_DIR = PROJECT_ROOT / 'transcripts_elevenlabs'

# Validate config
if not SPREADSHEET_ID:
    print("ERROR: GOOGLE_SPREADSHEET_ID not set in .env")
    sys.exit(1)
if not SERVICE_ACCOUNT.exists():
    print(f"ERROR: Service account file not found at {SERVICE_ACCOUNT}")
    print("See setup_service_account.md for instructions")
    sys.exit(1)

def get_client():
    """Get authenticated gspread client."""
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT), scopes=SCOPES)
    return gspread.authorize(creds)

def find_translation_file(video_name: str) -> Path:
    """Find the translation file for a video."""
    path = TRANSLATIONS_DIR / f"{video_name}{TRANSLATION_SUFFIX}.json"
    if path.exists():
        return path
    return None

def load_english_transcript(video_name: str) -> dict:
    """Load English transcript to get original text and timing."""
    # Try different naming patterns
    patterns = [
        f"{video_name}.json",
        f"{video_name}_boosted.json",
    ]
    for p in patterns:
        path = ENGLISH_DIR / p
        if path.exists():
            return json.loads(path.read_text())
    return None

def extract_segments_from_words(words: list, gap_threshold: float = 10.0) -> list:
    """Group words into segments based on sentence endings and large gaps."""
    if not words:
        return []
    
    segments = []
    current_words = []
    current_start = None
    
    for i, word in enumerate(words):
        text = word.get('text', '').strip()
        if not text:
            continue
            
        if current_start is None:
            current_start = word.get('start', 0)
        
        current_words.append(text)
        
        # Check if this is end of segment (sentence end or large gap)
        is_sentence_end = text.endswith('.')
        next_gap = 0
        if i + 1 < len(words):
            next_word = words[i + 1]
            next_gap = next_word.get('start', 0) - word.get('end', 0)
        
        if is_sentence_end or next_gap > gap_threshold or i == len(words) - 1:
            if current_words:
                segments.append({
                    'start': current_start,
                    'end': word.get('end', 0),
                    'text': ' '.join(current_words)
                })
                current_words = []
                current_start = None
    
    return segments

def load_translation(filepath: Path, video_name: str) -> tuple:
    """Load translation JSON and return (data, segments with english+translated)."""
    data = json.loads(filepath.read_text())
    segments = data.get('segments', [])
    return data, segments

def push_to_sheet(gc, video_filter: str = None):
    """Push translations to Google Sheet."""
    print(f"Opening spreadsheet (language: {LANG_NAME})...")
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # Get all translation files
    all_files = sorted(TRANSLATIONS_DIR.glob(f'*{TRANSLATION_SUFFIX}.json'))
    
    # Build video list
    videos = {}
    for f in all_files:
        name = f.stem.replace(TRANSLATION_SUFFIX, '')
        videos[name] = f
    
    if video_filter:
        videos = {k: v for k, v in videos.items() if video_filter in k}
    
    print(f"Found {len(videos)} videos to push")
    
    # Clear and add headers
    sheet = spreadsheet.sheet1
    sheet.clear()
    headers = ['Video', 'Segment', 'Start', 'End', 'Slot (sec)', 'Max Chars (~15.5/s)', 'English', LANG_NAME, 'Char Count', 'Status']
    sheet.append_row(headers)
    
    all_rows = []
    for video_name in sorted(videos.keys()):
        filepath = videos[video_name]
        print(f"  Processing {video_name}...")
        
        try:
            data, segments = load_translation(filepath, video_name)
        except Exception as e:
            print(f"    Error loading {filepath}: {e}")
            continue
        
        if not segments:
            print(f"    No segments found, skipping")
            continue
        
        for i, seg in enumerate(segments):
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            slot = round(end - start, 2)
            max_chars = int(slot * 15.5)  # 14 chars/sec adjusted for 0.9x TTS speed
            english = seg.get('english', '')
            translated = seg.get(TRANSLATION_KEY, '')
            char_count = len(translated)
            status = 'OVER' if char_count > max_chars else 'OK'
            
            all_rows.append([
                video_name, i+1, start, end, slot, max_chars,
                english, translated, char_count, status
            ])
    
    if all_rows:
        print(f"Uploading {len(all_rows)} rows...")
        sheet.append_rows(all_rows)
    
    print(f"\nDone! View at: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")

def pull_from_sheet(gc):
    """Pull edits from sheet back to JSON files and delete changed audio."""
    print(f"Opening spreadsheet (language: {LANG_NAME})...")
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.sheet1
    
    print("Fetching data...")
    all_data = sheet.get_all_records()
    
    # Group by video
    videos = {}
    for row in all_data:
        video = row.get('Video', '')
        if not video:
            continue
        if video not in videos:
            videos[video] = []
        videos[video].append(row)
    
    print(f"Found {len(videos)} videos in sheet")
    
    audio_deleted = 0
    segments_updated = 0
    
    for video_name, rows in videos.items():
        filepath = find_translation_file(video_name)
        if not filepath:
            print(f"  WARNING: No JSON found for {video_name}, skipping")
            continue
        
        print(f"  Updating {filepath.name}...")
        
        # Load existing JSON
        data, segments = load_translation(filepath, video_name)
        
        # Update segments with sheet data
        for row in rows:
            seg_num = int(row.get('Segment', 0)) - 1  # Sheet is 1-indexed
            if 0 <= seg_num < len(segments):
                new_text = row.get(LANG_NAME, '')
                old_text = segments[seg_num].get(TRANSLATION_KEY, '')
                
                if new_text and new_text != old_text:
                    print(f"    Segment {seg_num+1}: updated {LANG_NAME} text")
                    segments[seg_num][TRANSLATION_KEY] = new_text
                    segments_updated += 1
                    
                    # Delete stale audio file so it gets regenerated
                    audio_file = PROJECT_ROOT / AUDIO_DIR_NAME / video_name / f'seg_{seg_num:02d}.mp3'
                    if audio_file.exists():
                        audio_file.unlink()
                        print(f"      → Deleted stale audio: {audio_file.name}")
                        audio_deleted += 1
        
        # Update full text
        data['text'] = ' '.join(seg.get(TRANSLATION_KEY, '') for seg in segments)
        data['segments'] = segments
        
        # Save back
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    print(f"\nDone! {segments_updated} segments updated, {audio_deleted} audio files deleted.")
    if audio_deleted > 0:
        print("Run create_video_with_segments.py to regenerate changed audio.")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    gc = get_client()
    
    if command == 'push':
        video_filter = sys.argv[2] if len(sys.argv) > 2 else None
        push_to_sheet(gc, video_filter)
    elif command == 'pull':
        pull_from_sheet(gc)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
