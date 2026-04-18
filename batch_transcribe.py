#!/usr/bin/env python3
"""Batch transcribe audio files using ElevenLabs Speech-to-Text."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Check API key
if not os.getenv('ELEVEN_API_KEY'):
    print("ERROR: ELEVEN_API_KEY not set. Add to .env file.")
    exit(1)

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))

audio_dir = PROJECT_ROOT / 'audio'
output_dir = PROJECT_ROOT / 'transcripts_elevenlabs'
output_dir.mkdir(exist_ok=True)

audio_files = sorted(audio_dir.glob('*.mp3'))
print(f"Found {len(audio_files)} audio files\n")

for i, audio_path in enumerate(audio_files, 1):
    output_path = output_dir / f"{audio_path.stem}.json"
    
    if output_path.exists():
        print(f"[{i}/{len(audio_files)}] {audio_path.stem} - exists, skip")
        continue
    
    if 'boosted' in audio_path.stem:
        print(f"[{i}/{len(audio_files)}] {audio_path.stem} - boosted, skip")
        continue
    
    print(f"[{i}/{len(audio_files)}] {audio_path.stem}...")
    
    try:
        with open(audio_path, 'rb') as f:
            result = client.speech_to_text.convert(
                model_id='scribe_v1',
                file=f,
                language_code='en',
                timestamps_granularity='word'
            )
        
        transcript = {
            'language_code': result.language_code,
            'text': result.text,
            'words': [
                {'text': w.text, 'start': w.start, 'end': w.end, 'type': w.type}
                for w in (result.words or [])
                if w.type == 'word'
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)
        
        print(f"           {len(transcript['words'])} words")
    except Exception as e:
        print(f"           Error: {e}")

print("\nDone!")
