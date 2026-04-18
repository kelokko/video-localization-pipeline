#!/usr/bin/env python3
"""Generate localized video using segment-based timing."""

import os
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

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

client = ElevenLabs(api_key=os.getenv('ELEVEN_API_KEY'))

# Voice ID from env or file
VOICE_ID = os.getenv('ELEVEN_VOICE_ID')
if not VOICE_ID:
    voice_file = PROJECT_ROOT / '.voice_id'
    if voice_file.exists():
        VOICE_ID = voice_file.read_text().strip()
    else:
        raise ValueError("Set ELEVEN_VOICE_ID in .env or create .voice_id file")

print(f"Using voice ID: {VOICE_ID}")


def generate_segment_audio(text: str, output_path: str, speed: float = 0.9, 
                          previous_text: str = None, next_text: str = None):
    """Generate TTS for a single segment, with context for natural breathing."""
    temp_path = output_path + '.temp.mp3'
    
    # WINNING FORMULA (v3_ctx): Always use period for clean endings
    # (ellipsis causes gasping - discovered 2026-03-08)
    if text and not text.rstrip().endswith(('.', '!', '?')):
        text = text.rstrip() + '.'
    
    # Generate TTS with context (helps ElevenLabs breathe naturally)
    kwargs = {
        'voice_id': VOICE_ID,
        'text': text,
        'model_id': "eleven_multilingual_v2"
    }
    
    # Add context if available (helps avoid abrupt endings)
    if previous_text:
        kwargs['previous_text'] = previous_text
    if next_text:
        kwargs['next_text'] = next_text
    
    audio = client.text_to_speech.convert(**kwargs)
    
    with open(temp_path, 'wb') as f:
        for chunk in audio:
            f.write(chunk)
    
    # Slow down with FFmpeg (atempo 0.9 = 90% speed, slightly slower)
    subprocess.run([
        'ffmpeg', '-y', '-i', temp_path,
        '-filter:a', f'atempo={speed}',
        output_path
    ], capture_output=True)
    
    # Cleanup temp
    Path(temp_path).unlink(missing_ok=True)


def get_duration(file_path: str) -> float:
    """Get duration of audio/video file."""
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', file_path
    ], capture_output=True, text=True)
    return float(result.stdout.strip())


def create_video_with_segments(input_name: str, translation_name: str, output_suffix: str = None, speed: float = 0.9, save_audio: bool = True):
    """Create localized video with segments placed at correct timestamps."""
    if output_suffix is None:
        output_suffix = f'_{TARGET_LANG.upper()}'
    
    video_path = PROJECT_ROOT / 'input' / f'{input_name}.mp4'
    translation_path = PROJECT_ROOT / 'translations_final' / f'{translation_name}.json'
    output_path = PROJECT_ROOT / 'output' / f'{input_name}{output_suffix}.mp4'
    
    # Save audio to permanent location for remixing without API
    audio_dir = PROJECT_ROOT / AUDIO_DIR_NAME / input_name
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # Load translation with segments
    with open(translation_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get('segments', [])
    if not segments:
        print("No segments found!")
        return
    
    print(f"Processing {len(segments)} segments...")
    
    # Get video duration
    video_duration = get_duration(str(video_path))
    print(f"Video duration: {video_duration:.1f}s")
    
    # Generate audio for each segment (or reuse if exists)
    segment_files = []
    for i, seg in enumerate(segments):
        audio_file = audio_dir / f'seg_{i:02d}.mp3'
        
        # Skip TTS if audio already exists
        if audio_file.exists():
            print(f"  [{i+1}/{len(segments)}] Reusing existing audio: {audio_file.name}")
            audio_duration = get_duration(str(audio_file))
        else:
            print(f"  [{i+1}/{len(segments)}] Generating TTS for segment at {seg['start']:.1f}s...")
            seg_text = seg.get(TRANSLATION_KEY, seg.get('finnish', ''))  # Fallback for old files
            print(f"    Text: {seg_text[:50]}...")
            
            # Get context from adjacent segments (helps natural breathing)
            prev_text = segments[i-1].get(TRANSLATION_KEY, segments[i-1].get('finnish', '')) if i > 0 else None
            next_text = segments[i+1].get(TRANSLATION_KEY, segments[i+1].get('finnish', '')) if i < len(segments)-1 else None
            
            generate_segment_audio(
                seg_text, str(audio_file), speed=speed,
                previous_text=prev_text, next_text=next_text
            )
            audio_duration = get_duration(str(audio_file))
        
        print(f"    Duration: {audio_duration:.1f}s (slot: {seg['end'] - seg['start']:.1f}s)")
        
        segment_files.append({
            'file': str(audio_file),
            'start': seg['start'],
            'end': seg['end'],
            'duration': audio_duration
        })
    
    # Build FFmpeg filter to place segments at correct times
    # Create a silent base audio track, then overlay each segment
    filter_parts = []
    inputs = ['-i', str(video_path)]
    
    for i, seg in enumerate(segment_files):
        inputs.extend(['-i', seg['file']])
    
    # Create silent base audio matching video length
    filter_parts.append(f'anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{video_duration}[silent]')
    
    # Delay each segment audio to its start time (no truncation, no adaptive speed)
    mix_inputs = ['[silent]']
    for i, seg in enumerate(segment_files):
        delay_ms = int(seg['start'] * 1000)
        slot_duration = seg['end'] - seg['start']
        
        if seg['duration'] > slot_duration + 0.3:
            print(f"  ⚠️ Segment {i+1} overflows: {seg['duration']:.1f}s > {slot_duration:.1f}s slot")
        
        filter_parts.append(f'[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}]')
        mix_inputs.append(f'[a{i}]')
    
    # Mix all audio streams
    filter_parts.append(f'{" ".join(mix_inputs)}amix=inputs={len(segment_files) + 1}:normalize=0[aout]')
    
    filter_complex = '; '.join(filter_parts)
    
    # Build FFmpeg command
    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_path)
    ]
    
    print(f"\nCreating video...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        return
    
    # Audio files kept in audio_{lang}/{video_name}/ for remixing
    print(f"\nDone! Output: {output_path}")
    print(f"Audio files saved in: {audio_dir}/")
    print(f"Output size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")


def remix_video(input_name: str, translation_name: str, output_suffix: str = None, timing_overrides: dict = None):
    """Remix existing audio files with different timing - NO API CALLS!
    
    timing_overrides: dict of {segment_index: new_start_time}
    Example: {5: 39.5} to delay segment 6 (index 5) to start at 39.5s
    """
    if output_suffix is None:
        output_suffix = f'_{TARGET_LANG.upper()}_remix'
    
    video_path = PROJECT_ROOT / 'input' / f'{input_name}.mp4'
    translation_path = PROJECT_ROOT / 'translations_final' / f'{translation_name}.json'
    output_path = PROJECT_ROOT / 'output' / f'{input_name}{output_suffix}.mp4'
    audio_dir = PROJECT_ROOT / AUDIO_DIR_NAME / input_name
    
    if not audio_dir.exists():
        print(f"Error: No audio files found in {audio_dir}/")
        print("Run create_video_with_segments first to generate audio.")
        return
    
    # Load translation for timing
    with open(translation_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    segments = data.get('segments', [])
    
    video_duration = get_duration(str(video_path))
    print(f"Remixing {len(segments)} segments (NO API calls)...")
    
    # Build segment list with timing overrides
    segment_files = []
    for i, seg in enumerate(segments):
        audio_file = audio_dir / f'seg_{i:02d}.mp3'
        if not audio_file.exists():
            print(f"  Error: Missing {audio_file}")
            return
        
        start_time = timing_overrides.get(i, seg['start']) if timing_overrides else seg['start']
        audio_duration = get_duration(str(audio_file))
        
        print(f"  Segment {i+1}: {start_time:.1f}s (duration: {audio_duration:.1f}s)")
        
        segment_files.append({
            'file': str(audio_file),
            'start': start_time,
            'duration': audio_duration
        })
    
    # Build FFmpeg filter
    filter_parts = []
    inputs = ['-i', str(video_path)]
    
    for seg in segment_files:
        inputs.extend(['-i', seg['file']])
    
    filter_parts.append(f'anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{video_duration}[silent]')
    
    mix_inputs = ['[silent]']
    for i, seg in enumerate(segment_files):
        delay_ms = int(seg['start'] * 1000)
        filter_parts.append(f'[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}]')
        mix_inputs.append(f'[a{i}]')
    
    filter_parts.append(f'{" ".join(mix_inputs)}amix=inputs={len(segment_files) + 1}:normalize=0[aout]')
    filter_complex = '; '.join(filter_parts)
    
    cmd = [
        'ffmpeg', '-y', *inputs,
        '-filter_complex', filter_complex,
        '-map', '0:v', '-map', '[aout]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        str(output_path)
    ]
    
    print("Creating video...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        return
    
    print(f"Done! Output: {output_path}")


if __name__ == '__main__':
    import sys
    
    # WINNING SETTINGS (v3_ctx formula - 2026-03-08)
    # Speed 0.9x + context + period endings = best quality!
    
    if len(sys.argv) < 2:
        print("Usage: python create_video_with_segments.py <video_name> [speed]")
        print("Example: python create_video_with_segments.py 01_2_Assembling 0.9")
        sys.exit(1)
    
    video_name = sys.argv[1]
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 0.9  # Default: winning 0.9x
    
    translation_name = f'{video_name}{TRANSLATION_SUFFIX}'
    suffix = f'_{TARGET_LANG.upper()}' if speed == 0.9 else f'_{TARGET_LANG.upper()}_{int(speed*100)}'
    
    print(f"Creating {LANG_NAME} video for {video_name}...")
    create_video_with_segments(video_name, translation_name, output_suffix=suffix, speed=speed)
