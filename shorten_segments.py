#!/usr/bin/env python3
"""Shorten translated segments that are too long for their time slots."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config

load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.resolve()

# Language config
from lang_config import get_target_lang, get_lang_name, get_translation_suffix, get_translation_key

TARGET_LANG = get_target_lang()
LANG_NAME = get_lang_name()
TRANSLATION_SUFFIX = get_translation_suffix()
TRANSLATION_KEY = get_translation_key()

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'eu-north-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    config=Config(read_timeout=60)
)


def call_claude(prompt):
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


def shorten_segments_in_json(json_path: Path):
    """Shorten segments that are too long in a translation JSON file."""
    with open(json_path) as f:
        data = json.load(f)
    
    segments = data.get('segments', [])
    shortened_count = 0
    
    for i, seg in enumerate(segments):
        start = seg.get('start', 0)
        end = seg.get('end', 0)
        target_duration = end - start
        translated = seg.get(TRANSLATION_KEY, seg.get('finnish', ''))  # Fallback for old files
        estimated_tts = len(translated) / 15  # ~15 chars/sec for TTS
        
        if estimated_tts > target_duration + 0.5:  # More than 0.5s over
            target_chars = int(target_duration * 14)
            print(f"  Segment {i+1}: {len(translated)} -> ~{target_chars} chars")
            
            prompt = f"""Shorten this {LANG_NAME} text to approximately {target_chars} characters while keeping the same meaning.
Keep it natural {LANG_NAME}, suitable for spoken narration.

Original ({len(translated)} chars): {translated}

Return ONLY the shortened {LANG_NAME} text, nothing else."""
            
            shortened = call_claude(prompt).strip()
            print(f"    Was: {translated[:60]}...")
            print(f"    Now ({len(shortened)}): {shortened[:60]}...")
            seg[TRANSLATION_KEY] = shortened
            shortened_count += 1
    
    # Update full text
    data['text'] = ' '.join(seg.get(TRANSLATION_KEY, seg.get('finnish', '')) for seg in segments)
    data['segments'] = segments
    
    # Save back
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return shortened_count


def main():
    """Shorten all translations that are too long."""
    print(f"Shortening {LANG_NAME} segments that exceed time slots...\n")
    
    translations_dir = PROJECT_ROOT / 'translations_final'
    translation_files = sorted(translations_dir.glob(f'*{TRANSLATION_SUFFIX}.json'))
    
    if not translation_files:
        print(f"No translation files found matching *{TRANSLATION_SUFFIX}.json")
        return
    
    total_shortened = 0
    
    for tf in translation_files:
        print(f"Processing {tf.name}...")
        count = shorten_segments_in_json(tf)
        if count:
            print(f"  → Shortened {count} segments\n")
            total_shortened += count
        else:
            print(f"  → All segments OK\n")
    
    print(f"Done! Shortened {total_shortened} segments total.")


if __name__ == '__main__':
    main()
