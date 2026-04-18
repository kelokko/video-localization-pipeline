# AI Video Localization Pipeline

An automated pipeline for localizing video content using AI-powered transcription, translation, and voice synthesis. Built for medical e-learning content where terminology consistency and timing precision are critical.

**Live demo:** [Finnish Course](https://academy.medikro.com/fi/courses/demo-spirometry-fundamentals/) | [Swedish Course](https://academy.medikro.com/sv/courses/demo-spirometry-fundamentals/)

## The Problem

Traditional video dubbing is expensive (€5,000-15,000 for 30 videos) and slow. Off-the-shelf AI dubbing tools produce inconsistent terminology and poor timing sync.

## The Solution

This pipeline orchestrates multiple AI services with custom logic for:
- **Transcription** → ElevenLabs Speech-to-Text (word-level timestamps)
- **Translation** → Amazon Bedrock/Claude (with domain-specific thesaurus)
- **Voice Cloning** → ElevenLabs Instant Voice Clone
- **TTS** → ElevenLabs Multilingual v2
- **Audio Processing** → FFmpeg (tempo adjustment, mixing)
- **QA Workflow** → Google Sheets API (collaborative review)

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  VIDEO   │───▶│  AUDIO   │───▶│TRANSCRIBE│───▶│ SEGMENT  │
│  INPUT   │    │ EXTRACT  │    │ (11Labs) │    │ BY TIMING│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────▼────┐
│  VIDEO   │◀───│  AUDIO   │◀───│  TTS +   │◀───│TRANSLATE │
│  OUTPUT  │    │   MIX    │    │  CLONE   │    │(Bedrock) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
                               ┌─────────────────────┘
                               ▼
                      ┌─────────────────┐
                      │ DOMAIN THESAURUS │
                      │   (374 terms)    │
                      └─────────────────┘
```

## Key Features

### Timing Synchronization
Generated audio is speed-adjusted to fit original segment slots using FFmpeg's `atempo` filter.

### Medical Terminology Consistency
A 374-term thesaurus ensures technical terms translate identically across all segments.

### Natural Speech Flow
ElevenLabs context parameters (`previous_text`, `next_text`) create natural breathing between segments.

### QA Interface
Google Sheets integration lets non-technical reviewers edit translations with real-time character limits.

## Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/yourusername/video-translator.git
   cd video-translator
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Set up Google Sheets (optional):**
   - Create a service account in Google Cloud Console
   - Download credentials as `service-account.json`
   - Share your spreadsheet with the service account email

4. **Create thesaurus:**
   ```bash
   # Copy the example and add your domain-specific terms
   cp thesaurus/example.json thesaurus/en-fi.json
   # Edit thesaurus/en-fi.json with your terminology
   ```
   
   The thesaurus ensures consistent translation of technical terms. See `thesaurus/example.json` for the required format.

## Usage

### Quick Start: Interactive Wizard

The easiest way to run the pipeline:

```bash
python run_pipeline.py
```

The wizard:
- Prompts for target language (fi, sv, es, de, or any language code)
- Validates API keys and configuration
- Checks what's already done (skips completed steps)
- Guides you through transcription → translation → QA → video generation
- Auto-detects changed segments and regenerates only those

### Manual Steps (Advanced)

#### 0. Clone narrator voice (once per voice)
```bash
python clone_voice.py
# Creates ElevenLabs voice clone and saves ID to .voice_id
```

#### 1. Transcribe source audio
```bash
python batch_transcribe.py
# Transcribes all audio/*.mp3 files with word-level timestamps
```

#### 2. Translate with thesaurus
```bash
python batch_translate_all.py
# Translates transcripts using domain thesaurus for terminology consistency
```

#### 3. Shorten long segments (optional)
```bash
python shorten_segments.py
# Finds segments too long for their time slots and asks Claude to shorten them
# Only processes segments that exceed the target duration (~10-20% typically)
```

#### 4. Generate localized video
```bash
python create_video_with_segments.py VIDEO_NAME [speed]
# Example: python create_video_with_segments.py 01_Intro 0.9
# Uses 0.9x speed by default (fills timing gaps from removed filler words)
```

### 5. QA workflow (optional)

**Push translations for human review:**
```bash
python sheets_sync.py push              # Push all translations to Google Sheet
python sheets_sync.py push VIDEO_NAME   # Push specific video only
```

**Reviewer edits in Google Sheets** — character counts and length warnings shown automatically.

**Pull edits and regenerate:**
```bash
python sheets_sync.py pull              # Pull edits back to JSON files
python create_video_with_segments.py VIDEO_NAME  # Regenerate with fixes
```

**AI-assisted QA (optional):**
```bash
python qa_translations.py               # Claude reviews translations for awkward phrasing
python apply_qa_fixes.py                # Apply batch fixes to sheet
```

## Project Structure

```
video-translator/
├── input/                    # Source video files (gitignored)
├── output/                   # Generated videos (gitignored)
├── audio_{lang}/             # Generated audio segments per language
├── transcripts_elevenlabs/   # Transcription JSONs (gitignored)
├── translations_final/       # Translation JSONs (gitignored)
├── thesaurus/                # Domain terminology
│   ├── example.json          # Example structure
│   └── en-{lang}.json        # Your terms (gitignored)
├── samples/                  # Example file structures
│   ├── transcript_example.json
│   └── translation_example.json
├── run_pipeline.py           # Interactive wizard (recommended)
├── lang_config.py            # Language configuration
├── clone_voice.py            # Create ElevenLabs voice clone
├── batch_transcribe.py       # Transcribe audio
├── batch_translate_all.py    # Translate with thesaurus
├── shorten_segments.py       # Fix segments that are too long
├── create_video_with_segments.py  # Generate localized video
├── sheets_sync.py            # Push/pull translations to Google Sheets
├── qa_translations.py        # AI review for awkward phrasing
└── apply_qa_fixes.py         # Apply batch fixes
```

## Supported Languages

The pipeline works with **any language** supported by ElevenLabs Multilingual v2 (29+ languages).

Tested in production:
- **Finnish** — 26 videos localized
- **Swedish** — thesaurus prepared
- **Spanish** — thesaurus prepared

Adding a new language:
1. Set `TARGET_LANG=xx` in `.env` (e.g., `de` for German)
2. Create a thesaurus at `thesaurus/en-xx.json`
3. Clone a voice or use the existing multilingual voice
4. Run `python run_pipeline.py`

The pipeline automatically uses `audio_xx/`, `*_xx.json` naming based on your target language.

## Requirements

- Python 3.10+
- FFmpeg (for audio processing)
- API keys: ElevenLabs, AWS Bedrock
- Optional: Google Cloud service account

## Case Study

See [CASE-STUDY-AI-Video-Localization.md](./CASE-STUDY-AI-Video-Localization.md) for the full technical write-up.

## License

MIT
