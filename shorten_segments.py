#!/usr/bin/env python3
"""Shorten Finnish segments that are too long for their time slots."""

import os
import json
import csv
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config

load_dotenv()

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='eu-north-1',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    config=Config(read_timeout=60)
)


def parse_ts(ts):
    parts = ts.split(':')
    return int(parts[0]) * 60 + float(parts[1])


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


def shorten_segments(csv_path: Path, output_path: Path):
    with open(csv_path) as f:
        segments = list(csv.DictReader(f))
    
    updated = []
    for seg in segments:
        start = parse_ts(seg['start'])
        end = parse_ts(seg['end'])
        target_duration = end - start
        finnish = seg['finnish']
        estimated_tts = len(finnish) / 15
        
        if estimated_tts > target_duration + 0.5:
            target_chars = int(target_duration * 14)
            print(f"Segment {seg['segment_id']}: {len(finnish)} -> ~{target_chars} chars")
            
            prompt = f"""Shorten this Finnish text to approximately {target_chars} characters while keeping the same meaning.
Keep it natural Finnish, suitable for spoken narration.

Original ({len(finnish)} chars): {finnish}

Return ONLY the shortened Finnish text, nothing else."""
            
            shortened = call_claude(prompt).strip()
            print(f"  Was: {finnish}")
            print(f"  Now ({len(shortened)}): {shortened}\n")
            seg['finnish'] = shortened
        
        updated.append(seg)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['segment_id', 'start', 'end', 'english', 'finnish'])
        writer.writeheader()
        writer.writerows(updated)
    
    print(f"Saved to {output_path}")


if __name__ == '__main__':
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "00_Cource_intro"
    shorten_segments(
        Path(f'translations_new/{name}.csv'),
        Path(f'translations_new/{name}_fixed.csv')
    )
