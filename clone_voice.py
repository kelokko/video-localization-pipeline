#!/usr/bin/env python3
"""Create a voice clone using ElevenLabs Instant Voice Clone."""

import os
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))

voice_sample = Path('voice_sample.mp3')

print("Creating voice clone...")
voice = client.voices.ivc.create(
    name="Medikro Narrator",
    description="English narrator voice from Medikro spirometry training videos",
    files=[open(voice_sample, 'rb')]
)

print(f"Voice clone created!")
print(f"Voice ID: {voice.voice_id}")
print(f"Name: {voice.name}")

with open('.voice_id', 'w') as f:
    f.write(voice.voice_id)

print(f"\nVoice ID saved to .voice_id")
