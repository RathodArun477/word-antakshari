"""
Word validation pipeline. Unlike game/state.py and game/rules.py, this file
DOES do I/O (file loading, network calls) — that's intentional and why it's
kept separate from the pure game logic. Order of checks, cheapest first:
  1. length check (instant, no I/O)
  2. profanity check (local, fast)
  3. local wordlist lookup (in-memory set, instant)
  4. WordNet lookup (local corpus, no network)
  5. Gemini fallback (network call — only reached for rare edge cases)
"""
from better_profanity import profanity
import nltk
from nltk.corpus import wordnet
from english_words import get_english_words_set

from config import MIN_WORD_LENGTH

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
_genai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --- One-time setup at module load ---

profanity.load_censor_words()

try:
    wordnet.synsets("test")
except LookupError:
    nltk.download("wordnet")

_LOCAL_WORDLIST: set[str] = set()


def load_wordlist() -> None:
    global _LOCAL_WORDLIST
    _LOCAL_WORDLIST = get_english_words_set(["web2"],lower=True)


def _in_local_wordlist(word: str) -> bool:
    return word in _LOCAL_WORDLIST


def _in_wordnet(word: str) -> bool:
    return len(wordnet.synsets(word)) > 0


def _check_with_gemini(word: str) -> bool:
    prompt = (
        f'Is "{word}" a valid English word (including common slang or '
        f'proper nouns)? Reply with only "yes" or "no".'
    )
    response = _genai_client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )
    answer = response.text.strip().lower()
    return answer.startswith("yes")


def validate_word(word: str) -> tuple[bool, str | None]:
    """
    Returns (True, None) if valid, or (False, reason) matching
    CONTRACT.md's WordResult reason_if_rejected values.
    Word is assumed already lowercased/stripped by the caller (submit_word).
    """
    if len(word) < MIN_WORD_LENGTH:
        return False, "too_short"

    if profanity.contains_profanity(word):
        return False, "profanity"

    if _in_local_wordlist(word):
        return True, None

    if _in_wordnet(word):
        return True, None

    # Only reaches here for words neither list recognized — rare in practice.
    if _check_with_gemini(word):
        return True, None

    return False, "not_a_word"

def get_wordlist() -> set[str]:
    return _LOCAL_WORDLIST

