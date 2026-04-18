#!/usr/bin/env python3
"""Batch translate English transcripts to target language using thesaurus."""

import os
import json
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Language config
from lang_config import (
    get_target_lang, get_lang_name, get_thesaurus_path,
    get_translation_suffix, get_translation_key
)

TARGET_LANG = get_target_lang()
LANG_NAME = get_lang_name()
THESAURUS_PATH = get_thesaurus_path()
TRANSLATION_SUFFIX = get_translation_suffix()
TRANSLATION_KEY = get_translation_key()

print(f"Target language: {LANG_NAME} ({TARGET_LANG})")

# Load thesaurus (required for translation)
if not THESAURUS_PATH.exists():
    print(f"ERROR: Thesaurus not found at {THESAURUS_PATH}")
    print("Create your domain-specific thesaurus based on thesaurus/example.json")
    sys.exit(1)

with open(THESAURUS_PATH, 'r', encoding='utf-8') as f:
    thesaurus_data = json.load(f)
    # Support both formats: list of {en, TARGET_LANG} or simple {en: TARGET_LANG}
    if isinstance(thesaurus_data, dict) and 'thesaurus' in thesaurus_data:
        THESAURUS = {item['en'].lower(): item.get(TARGET_LANG, item.get('fi', '')) 
                     for item in thesaurus_data['thesaurus']}
    else:
        THESAURUS = {k.lower(): v for k, v in thesaurus_data.items()}

# Bedrock client (check credentials)
if not os.getenv('AWS_ACCESS_KEY') or not os.getenv('AWS_SECRET_ACCESS_KEY'):
    print("ERROR: AWS credentials not set. Add to .env:")
    print("  AWS_ACCESS_KEY=your_key")
    print("  AWS_SECRET_ACCESS_KEY=your_secret")
    sys.exit(1)

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'eu-north-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    config=Config(read_timeout=120)
)

FILLERS = {'uh', 'uh,', 'um', 'um,', 'uh.', 'um.', 's--', 'öh', 'öh,'}

INPUT_DIR = PROJECT_ROOT / 'transcripts_elevenlabs'
OUTPUT_DIR = PROJECT_ROOT / 'translations_final'


def call_claude(prompt: str) -> str:
    response = bedrock.invoke_model(
        modelId='eu.anthropic.claude-sonnet-4-20250514-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    result = json.loads(response['body'].read())
    return result['content'][0]['text']


def extract_segments(words: list) -> list:
    """Group words into speech segments based on sentences and large gaps."""
    if not words:
        return []
    
    # Filter out empty words
    words = [w for w in words if w.get('text', '').strip()]
    if not words:
        return []
    
    segments = []
    current_segment = {
        'start': words[0]['start'],
        'end': words[0]['end'],
        'words': [words[0]]
    }
    
    for i in range(1, len(words)):
        prev_word = words[i-1]
        curr_word = words[i]
        gap = curr_word['start'] - prev_word['end']
        
        is_sentence_end = prev_word['text'].rstrip().endswith('.')
        is_music_gap = gap > 10.0
        
        if is_sentence_end or is_music_gap:
            current_segment['end'] = prev_word['end']
            current_segment['text'] = ' '.join(
                w['text'] for w in current_segment['words'] 
                if w['text'].lower().rstrip(',.') not in FILLERS
            )
            if current_segment['text'].strip():
                segments.append(current_segment)
            
            current_segment = {
                'start': curr_word['start'],
                'end': curr_word['end'],
                'words': [curr_word]
            }
        else:
            current_segment['words'].append(curr_word)
            current_segment['end'] = curr_word['end']
    
    # Last segment
    current_segment['text'] = ' '.join(
        w['text'] for w in current_segment['words']
        if w['text'].lower().rstrip(',.') not in FILLERS
    )
    if current_segment['text'].strip():
        segments.append(current_segment)
    
    return segments


def translate_segment(english_text: str) -> str:
    """Translate using Claude with thesaurus."""
    # Skip if it's just music notation
    if not english_text.strip() or english_text.strip().startswith('('):
        return ''
    
    thesaurus_str = "\n".join([f"- {en} → {target}" for en, target in list(THESAURUS.items())[:100]])
    
    prompt = f"""Translate this English text to natural {LANG_NAME} for voiceover narration.

CRITICAL RULES:
1. Use these EXACT translations for technical terms:
{thesaurus_str}

2. Remove filler words (uh, um, öh)
3. Remove parenthetical notes like "(instrumental music)"
4. Keep brand names (Medikro) as-is
5. Natural spoken {LANG_NAME}, not literal
6. Keep concise - similar length to English

ENGLISH: {english_text}

Return ONLY the {LANG_NAME} translation, nothing else."""

    translated = call_claude(prompt).strip()
    translated = re.sub(r'\([^)]*\)', '', translated)
    translated = re.sub(r'\s+', ' ', translated).strip()
    
    return translated


def translate_file(input_path: Path) -> dict:
    """Translate a single file and return the result."""
    video_name = input_path.stem
    output_path = OUTPUT_DIR / f'{video_name}{TRANSLATION_SUFFIX}.json'
    
    # Skip if already translated
    if output_path.exists():
        print(f"  ⏭️  {video_name} - already done, skipping")
        return None
    
    print(f"  📄 {video_name}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words = data.get('words', [])
    if not words:
        print(f"    ⚠️  No words found, skipping")
        return None
    
    segments = extract_segments(words)
    if not segments:
        print(f"    ⚠️  No segments extracted, skipping")
        return None
    
    print(f"    Found {len(segments)} segments, translating to {LANG_NAME}...")
    
    translated_segments = []
    full_text_parts = []
    
    for i, seg in enumerate(segments):
        translated_text = translate_segment(seg['text'])
        if translated_text:
            translated_segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'english': seg['text'],
                TRANSLATION_KEY: translated_text  # e.g., 'finnish', 'swedish', 'spanish'
            })
            full_text_parts.append(translated_text)
            print(f"    [{i+1}/{len(segments)}] ✓")
    
    if not translated_segments:
        print(f"    ⚠️  No segments translated")
        return None
    
    output = {
        'language_code': TARGET_LANG,
        'language_name': LANG_NAME,
        'text': ' '.join(full_text_parts),
        'segments': translated_segments,
        '_meta': {
            'source': str(input_path),
            'thesaurus': str(THESAURUS_PATH),
            'segment_count': len(translated_segments)
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"    ✅ Saved {len(translated_segments)} segments")
    return output


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Get all English transcripts
    input_files = sorted(INPUT_DIR.glob('*.json'))
    print(f"Found {len(input_files)} English transcripts\n")
    
    success = 0
    skipped = 0
    failed = 0
    
    for input_path in input_files:
        try:
            result = translate_file(input_path)
            if result:
                success += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"    ❌ Error: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Done! ✅ {success} translated, ⏭️ {skipped} skipped, ❌ {failed} failed")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
