#!/usr/bin/env python3
"""
Video Localization Pipeline - Interactive Wizard

Guides you through the full localization process:
1. Setup & validation (API keys, folders, glossary)
2. Transcription (ElevenLabs Speech-to-Text)
3. Translation (Bedrock Claude + glossary)
4. Length optimization (shorten long segments)
5. QA workflow (Google Sheets for human review)
6. Voice generation (ElevenLabs TTS with cloning)
7. Video assembly (FFmpeg)

Run: python run_pipeline.py
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).parent.resolve()
ENV_FILE = PROJECT_ROOT / '.env'

# Will be loaded after .env is set up
TARGET_LANG = None
LANG_NAME = None

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(msg):
    print(f"\n{Colors.BLUE}{Colors.BOLD}▶ {msg}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def prompt(msg, default=None):
    if default:
        result = input(f"{msg} [{default}]: ").strip()
        return result if result else default
    return input(f"{msg}: ").strip()

def prompt_yes_no(msg, default=True):
    default_str = "Y/n" if default else "y/N"
    result = input(f"{msg} [{default_str}]: ").strip().lower()
    if not result:
        return default
    return result in ('y', 'yes')


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def check_input_folder():
    """Check input folder for videos."""
    print_step("Checking input folder...")
    
    input_dir = PROJECT_ROOT / 'input'
    if not input_dir.exists():
        input_dir.mkdir(parents=True)
        print_warning(f"Created input folder: {input_dir}")
    
    all_files = list(input_dir.glob('*'))
    video_files = list(input_dir.glob('*.mp4'))
    other_files = [f for f in all_files if f.suffix.lower() != '.mp4' and f.is_file()]
    
    if not all_files:
        print_error("Input folder is empty!")
        print(f"  Put your source videos (MP4 format) into: {input_dir}")
        return None
    
    if not video_files:
        print_error("No MP4 files found in input folder!")
        print(f"  Found these files which will be ignored:")
        for f in other_files[:10]:
            print(f"    - {f.name}")
        if len(other_files) > 10:
            print(f"    ... and {len(other_files) - 10} more")
        return None
    
    if other_files:
        print_warning(f"Found {len(other_files)} non-MP4 files (will be ignored):")
        for f in other_files[:5]:
            print(f"    - {f.name}")
        if len(other_files) > 5:
            print(f"    ... and {len(other_files) - 5} more")
    
    print_success(f"Found {len(video_files)} MP4 videos to process")
    return video_files


def check_target_language():
    """Check/prompt for target language."""
    print_step("Checking target language...")
    
    lang = os.getenv('TARGET_LANG')
    
    if not lang:
        print_warning("TARGET_LANG not set")
        lang = prompt("Enter target language code (e.g., fi, sv, es, de)", "fi")
        set_key(str(ENV_FILE), 'TARGET_LANG', lang.lower())
        load_dotenv(override=True)
    
    from lang_config import get_target_lang, get_lang_name, get_translation_suffix, get_audio_dir, get_thesaurus_path
    
    target_lang = get_target_lang()
    lang_name = get_lang_name()
    
    print_success(f"Target language: {lang_name} ({target_lang})")
    
    return {
        'code': target_lang,
        'name': lang_name,
        'suffix': get_translation_suffix(),
        'audio_dir': get_audio_dir(),
        'thesaurus': get_thesaurus_path()
    }


def check_glossary(thesaurus_path):
    """Check glossary file exists and is valid JSON."""
    print_step("Checking glossary...")
    
    if not thesaurus_path.exists():
        print_error(f"Glossary not found: {thesaurus_path}")
        print("  Create a JSON file with term mappings, e.g.:")
        print('  {"flow transducer": "virtausanturi", "calibration": "kalibrointi"}')
        print(f"  See thesaurus/example.json for reference")
        return False
    
    try:
        with open(thesaurus_path) as f:
            glossary = json.load(f)
        
        # Count terms (support both formats)
        if isinstance(glossary, dict) and 'thesaurus' in glossary:
            term_count = len(glossary['thesaurus'])
        elif isinstance(glossary, dict):
            term_count = len(glossary)
        else:
            print_error("Glossary must be a JSON object")
            return False
        
        if term_count == 0:
            print_warning("Glossary is empty - translations won't use custom terminology")
        else:
            print_success(f"Glossary loaded: {term_count} term pairs")
        
        return True
        
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in glossary: {e}")
        print("  Check for missing commas, quotes, or brackets")
        return False


def check_elevenlabs_key():
    """Check ElevenLabs API key."""
    print_step("Checking ElevenLabs API key...")
    
    api_key = os.getenv('ELEVEN_API_KEY')
    
    if not api_key:
        print_warning("ELEVEN_API_KEY not set")
        api_key = prompt("Enter your ElevenLabs API key")
        if not api_key:
            print_error("API key required")
            return False
        set_key(str(ENV_FILE), 'ELEVEN_API_KEY', api_key)
        load_dotenv(override=True)
    
    # Test the key
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        # Try to list voices as a simple API test
        voices = client.voices.get_all()
        print_success(f"ElevenLabs connected ({len(voices.voices)} voices available)")
        return True
    except Exception as e:
        print_error(f"ElevenLabs API error: {e}")
        print("  Check your API key at https://elevenlabs.io/")
        return False


def check_voice_id():
    """Check voice ID for TTS."""
    print_step("Checking voice ID...")
    
    voice_id = os.getenv('ELEVEN_VOICE_ID')
    voice_file = PROJECT_ROOT / '.voice_id'
    
    if not voice_id and voice_file.exists():
        voice_id = voice_file.read_text().strip()
    
    if not voice_id:
        print_warning("No voice ID configured")
        print("  You need to clone a voice first. Options:")
        print("  1. Run: python clone_voice.py <path-to-sample-audio>")
        print("  2. Use ElevenLabs web UI and paste the voice ID")
        voice_id = prompt("Enter voice ID (or press Enter to clone later)")
        
        if voice_id:
            set_key(str(ENV_FILE), 'ELEVEN_VOICE_ID', voice_id)
            load_dotenv(override=True)
            print_success(f"Voice ID saved: {voice_id}")
        else:
            print_warning("Voice cloning required before TTS generation")
            return False
    else:
        print_success(f"Voice ID configured: {voice_id[:20]}...")
    
    return True


def check_aws_credentials():
    """Check AWS credentials for Bedrock."""
    print_step("Checking AWS credentials...")
    
    access_key = os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not access_key or not secret_key:
        print_warning("AWS credentials not set")
        access_key = prompt("Enter AWS Access Key ID")
        secret_key = prompt("Enter AWS Secret Access Key")
        region = prompt("Enter AWS Region", "us-east-1")
        
        if not access_key or not secret_key:
            print_error("AWS credentials required for translation")
            return False
        
        set_key(str(ENV_FILE), 'AWS_ACCESS_KEY_ID', access_key)
        set_key(str(ENV_FILE), 'AWS_SECRET_ACCESS_KEY', secret_key)
        set_key(str(ENV_FILE), 'AWS_REGION', region)
        load_dotenv(override=True)
    
    # Test the credentials
    try:
        import boto3
        client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        # Just creating the client is enough to validate credentials format
        print_success(f"AWS credentials configured (region: {region})")
        return True
    except Exception as e:
        print_error(f"AWS error: {e}")
        return False


def check_google_sheets():
    """Check Google Sheets configuration."""
    print_step("Checking Google Sheets setup...")
    
    service_account = PROJECT_ROOT / 'service-account.json'
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    
    if not service_account.exists():
        print_warning("Google Sheets service account not found")
        print(f"  Create a service account and save credentials to:")
        print(f"  {service_account}")
        print("  See: https://docs.gspread.org/en/latest/oauth2.html")
        return False
    
    if not spreadsheet_id:
        print_warning("GOOGLE_SPREADSHEET_ID not set")
        spreadsheet_id = prompt("Enter Google Spreadsheet ID (from URL)")
        if spreadsheet_id:
            set_key(str(ENV_FILE), 'GOOGLE_SPREADSHEET_ID', spreadsheet_id)
            load_dotenv(override=True)
    
    # Test the connection
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(str(service_account), scopes=scopes)
        gc = gspread.authorize(creds)
        
        sheet = gc.open_by_key(spreadsheet_id)
        print_success(f"Google Sheets connected: {sheet.title}")
        return True
    except Exception as e:
        print_error(f"Google Sheets error: {e}")
        print("  Make sure the service account has access to the spreadsheet")
        return False


# =============================================================================
# STATUS CHECKING
# =============================================================================

def get_video_names():
    """Get list of video names from input folder."""
    input_dir = PROJECT_ROOT / 'input'
    return [f.stem for f in input_dir.glob('*.mp4')]


def check_transcripts_status():
    """Check which videos have transcripts."""
    transcripts_dir = PROJECT_ROOT / 'transcripts_elevenlabs'
    video_names = get_video_names()
    
    existing = []
    missing = []
    
    for name in video_names:
        transcript_file = transcripts_dir / f"{name}.json"
        boosted_file = transcripts_dir / f"{name}_boosted.json"
        if transcript_file.exists() or boosted_file.exists():
            existing.append(name)
        else:
            missing.append(name)
    
    return existing, missing


def check_translations_status(translation_suffix):
    """Check which videos have translations."""
    translations_dir = PROJECT_ROOT / 'translations_final'
    video_names = get_video_names()
    
    existing = []
    missing = []
    
    for name in video_names:
        translation_file = translations_dir / f"{name}{translation_suffix}.json"
        if translation_file.exists():
            existing.append(name)
        else:
            missing.append(name)
    
    return existing, missing


def check_audio_status(audio_dir_name):
    """Check which videos have generated audio."""
    audio_dir = PROJECT_ROOT / audio_dir_name
    video_names = get_video_names()
    
    complete = []
    missing = []
    
    for name in video_names:
        video_audio_dir = audio_dir / name
        if not video_audio_dir.exists():
            missing.append(name)
        else:
            audio_files = list(video_audio_dir.glob('seg_*.mp3'))
            if audio_files:
                complete.append(name)
            else:
                missing.append(name)
    
    return complete, missing


# =============================================================================
# PIPELINE STEPS
# =============================================================================

def run_transcription():
    """Run batch transcription."""
    print_step("Running transcription...")
    import subprocess
    result = subprocess.run([sys.executable, 'batch_transcribe.py'], cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_translation():
    """Run batch translation."""
    print_step("Running translation...")
    import subprocess
    result = subprocess.run([sys.executable, 'batch_translate_all.py'], cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_shortening():
    """Run segment shortening."""
    print_step("Shortening long segments...")
    import subprocess
    result = subprocess.run([sys.executable, 'shorten_segments.py'], cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_sheets_push():
    """Push translations to Google Sheets."""
    print_step("Pushing to Google Sheets...")
    import subprocess
    result = subprocess.run([sys.executable, 'sheets_sync.py', 'push'], cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_sheets_pull():
    """Pull edits from Google Sheets."""
    print_step("Pulling edits from Google Sheets...")
    import subprocess
    result = subprocess.run([sys.executable, 'sheets_sync.py', 'pull'], cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_video_generation(translation_suffix):
    """Generate videos with TTS."""
    print_step("Generating videos...")
    import subprocess
    
    translations_dir = PROJECT_ROOT / 'translations_final'
    translation_files = list(translations_dir.glob(f'*{translation_suffix}.json'))
    
    for i, tf in enumerate(translation_files):
        video_name = tf.stem.replace(translation_suffix, '')
        print(f"\n  [{i+1}/{len(translation_files)}] Processing {video_name}...")
        result = subprocess.run(
            [sys.executable, 'create_video_with_segments.py', video_name],
            cwd=PROJECT_ROOT
        )
        if result.returncode != 0:
            print_warning(f"Failed to process {video_name}")
    
    return True


# =============================================================================
# MAIN WIZARD
# =============================================================================

def main():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}   Video Localization Pipeline - Interactive Wizard{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    # Load existing .env
    if ENV_FILE.exists():
        load_dotenv()
    else:
        ENV_FILE.touch()
    
    # Phase 1: Validation
    print(f"\n{Colors.BOLD}Phase 1: Setup & Validation{Colors.END}")
    print("-" * 40)
    
    # First, get target language (needed for other checks)
    lang_config = check_target_language()
    
    videos = check_input_folder()
    if not videos:
        print_error("\nFix input folder issues and run again.")
        return 1
    
    if not check_glossary(lang_config['thesaurus']):
        if not prompt_yes_no("Continue without glossary?", default=False):
            return 1
    
    if not check_elevenlabs_key():
        print_error("\nElevenLabs API key required. Get one at https://elevenlabs.io/")
        return 1
    
    if not check_aws_credentials():
        print_error("\nAWS credentials required for translation.")
        return 1
    
    voice_ready = check_voice_id()
    sheets_ready = check_google_sheets()
    
    # Phase 2: Transcription
    print(f"\n{Colors.BOLD}Phase 2: Transcription{Colors.END}")
    print("-" * 40)
    
    existing_transcripts, missing_transcripts = check_transcripts_status()
    
    if not missing_transcripts:
        print_success(f"All {len(existing_transcripts)} videos already transcribed — skipping")
    elif existing_transcripts:
        print_success(f"{len(existing_transcripts)} videos already transcribed")
        print_warning(f"{len(missing_transcripts)} videos need transcription")
        if prompt_yes_no(f"Transcribe {len(missing_transcripts)} remaining videos?"):
            if not run_transcription():
                print_error("Transcription failed")
                return 1
            print_success("Transcription complete!")
    else:
        print(f"  {len(missing_transcripts)} videos to transcribe")
        if prompt_yes_no("Run transcription?"):
            if not run_transcription():
                print_error("Transcription failed")
                return 1
            print_success("Transcription complete!")
    
    # Phase 3: Translation
    print(f"\n{Colors.BOLD}Phase 3: Translation to {lang_config['name']}{Colors.END}")
    print("-" * 40)
    
    existing_translations, missing_translations = check_translations_status(lang_config['suffix'])
    
    if not missing_translations:
        print_success(f"All {len(existing_translations)} videos already translated — skipping")
    elif existing_translations:
        print_success(f"{len(existing_translations)} videos already translated")
        print_warning(f"{len(missing_translations)} videos need translation")
        if prompt_yes_no(f"Translate {len(missing_translations)} remaining videos?"):
            if not run_translation():
                print_error("Translation failed")
                return 1
            print_success("Translation complete!")
            
            if prompt_yes_no("Run length optimization (shorten long segments)?"):
                run_shortening()
    else:
        print(f"  {len(missing_translations)} videos to translate")
        if prompt_yes_no("Run translation?"):
            if not run_translation():
                print_error("Translation failed")
                return 1
            print_success("Translation complete!")
            
            if prompt_yes_no("Run length optimization (shorten long segments)?"):
                run_shortening()
    
    # Phase 4: QA
    print(f"\n{Colors.BOLD}Phase 4: Human Review (QA){Colors.END}")
    print("-" * 40)
    
    if sheets_ready and prompt_yes_no("Push translations to Google Sheets for review?"):
        if run_sheets_push():
            spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
            print_success(f"\nTranslations ready for review!")
            print(f"  Open: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
            print(f"\n  {Colors.YELLOW}Review and edit translations in the sheet.{Colors.END}")
            print(f"  {Colors.YELLOW}Red cells = translations too long for timing.{Colors.END}")
            
            input(f"\n  Press Enter when review is complete...")
            
            if prompt_yes_no("Pull edits back from sheet?"):
                run_sheets_pull()
                print_success("Edits synced! Changed audio will be regenerated.")
    
    # Phase 5: Video Generation
    print(f"\n{Colors.BOLD}Phase 5: {lang_config['name']} Video Generation{Colors.END}")
    print("-" * 40)
    
    if not voice_ready:
        print_warning("Voice ID not configured. Clone a voice first:")
        print("  python clone_voice.py <path-to-sample-audio>")
        return 1
    
    complete_audio, missing_audio = check_audio_status(lang_config['audio_dir'])
    
    if complete_audio:
        print_success(f"{len(complete_audio)} videos have audio generated")
        print("  (Only missing/changed segments will be regenerated)")
    if missing_audio:
        print_warning(f"{len(missing_audio)} videos need audio generation")
    
    if prompt_yes_no(f"Generate {lang_config['name']} videos?"):
        run_video_generation(lang_config['suffix'])
        print_success("\nPipeline complete!")
        print(f"  Output videos: {PROJECT_ROOT / 'output'}")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}Done!{Colors.END}\n")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
