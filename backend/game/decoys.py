"""
Decoy generation for the guessing phase (rule 14, 23).
Priority: WordNet synonyms within the length range -> any wordlist word
within the length range -> any random wordlist word at all (rule 23's own
stated fallback for when nothing similar can be found).
"""
import random
from nltk.corpus import wordnet

from config import DECOY_LENGTH_OFFSET, GUESS_OPTIONS_COUNT
from game.validation import get_wordlist


def _get_synonyms(word: str) -> set[str]:
    synonyms = set()
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            name = lemma.name().replace("_", " ").lower()
            if name != word and " " not in name:
                synonyms.add(name)
    return synonyms


def generate_decoys(word: str, count: int = GUESS_OPTIONS_COUNT - 1) -> list[str]:
    min_len = max(1, len(word) - DECOY_LENGTH_OFFSET)
    max_len = len(word) + DECOY_LENGTH_OFFSET
    first_letter = word[0]

    decoys: set[str] = set()

    def add_candidates(pool, same_letter_only: bool):
        for candidate in pool:
            if len(decoys) >= count:
                return
            if candidate == word or candidate in decoys:
                continue
            if same_letter_only and not candidate.startswith(first_letter):
                continue
            decoys.add(candidate)

    # Tier 1: synonyms, same starting letter, within length range.
    synonyms = _get_synonyms(word)
    length_matched_synonyms = [s for s in synonyms if min_len <= len(s) <= max_len]
    add_candidates(length_matched_synonyms, same_letter_only=True)

    wordlist = get_wordlist()

    # Tier 2: wordlist words, same starting letter, within length range.
    if len(decoys) < count:
        same_letter_length_matched = [
            w for w in wordlist if min_len <= len(w) <= max_len and w.startswith(first_letter)
        ]
        random.shuffle(same_letter_length_matched)
        add_candidates(same_letter_length_matched, same_letter_only=True)

    # Tier 3: same starting letter, any length at all.
    if len(decoys) < count:
        same_letter_any_length = [w for w in wordlist if w.startswith(first_letter)]
        random.shuffle(same_letter_any_length)
        add_candidates(same_letter_any_length, same_letter_only=True)

    # Tier 4 fallback: synonyms, any starting letter, within length range.
    if len(decoys) < count:
        add_candidates(length_matched_synonyms, same_letter_only=False)

    # Tier 5 fallback: wordlist words, any starting letter, within length range.
    if len(decoys) < count:
        any_letter_length_matched = [
            w for w in wordlist if min_len <= len(w) <= max_len
        ]
        random.shuffle(any_letter_length_matched)
        add_candidates(any_letter_length_matched, same_letter_only=False)

    # Tier 6 fallback: final default — any word at all.
    if len(decoys) < count:
        remaining_pool = list(wordlist)
        random.shuffle(remaining_pool)
        add_candidates(remaining_pool, same_letter_only=False)

    return list(decoys)[:count]

def build_guess_options(real_word: str) -> list[str]:
    """Real word + decoys, shuffled — matches CONTRACT.md's GuessOptions payload."""
    decoys = generate_decoys(real_word, count=GUESS_OPTIONS_COUNT - 1)
    options = decoys + [real_word]
    random.shuffle(options)
    return options