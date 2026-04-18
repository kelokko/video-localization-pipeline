"""
Language configuration for the localization pipeline.

Supports ANY language - just set TARGET_LANG in .env and provide
a thesaurus file at thesaurus/en-{lang}.json
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Common language names (for nice display only - pipeline works without these)
LANG_NAMES = {
    'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish',
    'de': 'German', 'fr': 'French', 'it': 'Italian',
    'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish',
    'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese',
    'ru': 'Russian', 'ar': 'Arabic', 'hi': 'Hindi',
}

def get_target_lang() -> str:
    """Get target language code from environment. Works with ANY 2-letter code."""
    return os.getenv('TARGET_LANG', 'fi').lower()

def get_lang_name(lang: str = None) -> str:
    """Get display name for language. Falls back to uppercase code if unknown."""
    lang = lang or get_target_lang()
    return LANG_NAMES.get(lang, lang.upper())

def get_thesaurus_path(lang: str = None) -> Path:
    """Get thesaurus file path: thesaurus/en-{lang}.json"""
    lang = lang or get_target_lang()
    return Path(__file__).parent / 'thesaurus' / f'en-{lang}.json'

def get_translation_suffix(lang: str = None) -> str:
    """Get suffix for translation files: _{lang}"""
    lang = lang or get_target_lang()
    return f'_{lang}'

def get_audio_dir(lang: str = None) -> str:
    """Get audio directory name: audio_{lang}"""
    lang = lang or get_target_lang()
    return f'audio_{lang}'

def get_translation_key(lang: str = None) -> str:
    """Get JSON key for translated text (e.g., 'finnish', 'swedish')."""
    lang = lang or get_target_lang()
    return get_lang_name(lang).lower()
