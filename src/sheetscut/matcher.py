"""
Text matching algorithms for Sheetscut.

Provides exact and fuzzy matching of producer text against transcript word lists.
"""

import re
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """
    Normalize text for matching.

    - Lowercase
    - Remove punctuation except apostrophes (for contractions)
    - Collapse whitespace
    """
    text = re.sub(r'[^\w\s\']', '', text.lower())
    return ' '.join(text.split())


def build_search_corpus(word_list: list) -> list:
    """Build parallel list of normalized words for searching."""
    return [normalize_text(w['text']) for w in word_list]


def find_phrase_exact(phrase: str, word_list: list, corpus: list, start_idx: int = 0) -> tuple:
    """
    Find a phrase in the corpus using exact sliding window search.

    Args:
        phrase: The text to find
        word_list: List of word dicts with timecodes
        corpus: Parallel list of normalized words
        start_idx: Index to start searching from (for finding subsequent matches)

    Returns:
        (start_index, end_index) into word_list, or None if not found
    """
    phrase_normalized = normalize_text(phrase)
    phrase_words = phrase_normalized.split()

    if not phrase_words:
        return None

    # Sliding window search
    for i in range(start_idx, len(corpus) - len(phrase_words) + 1):
        if corpus[i:i + len(phrase_words)] == phrase_words:
            return (i, i + len(phrase_words) - 1)

    return None


def find_phrase_fuzzy(phrase: str, word_list: list, corpus: list,
                      threshold: float = 0.85, start_idx: int = 0) -> tuple:
    """
    Find a phrase using fuzzy matching when exact match fails.

    Uses SequenceMatcher to find the best approximate match above threshold.

    Args:
        phrase: The text to find
        word_list: List of word dicts with timecodes
        corpus: Parallel list of normalized words
        threshold: Minimum similarity ratio (0.0-1.0) to accept a match
        start_idx: Index to start searching from

    Returns:
        (start_index, end_index, similarity_score) or None if no match above threshold
    """
    phrase_normalized = normalize_text(phrase)
    phrase_words = phrase_normalized.split()
    phrase_len = len(phrase_words)

    if not phrase_words:
        return None

    best_match = None
    best_score = threshold  # Only accept matches above threshold

    # Sliding window with some flexibility on window size
    for window_size in range(phrase_len - 2, phrase_len + 3):  # Allow +/- 2 words
        if window_size < 3:
            continue
        if window_size > len(corpus):
            continue

        for i in range(start_idx, len(corpus) - window_size + 1):
            candidate = ' '.join(corpus[i:i + window_size])
            score = SequenceMatcher(None, phrase_normalized, candidate).ratio()

            if score > best_score:
                best_score = score
                best_match = (i, i + window_size - 1, score)

    return best_match


def find_phrase(phrase: str, word_list: list, corpus: list,
                start_idx: int = 0, fuzzy: bool = True, fuzzy_threshold: float = 0.85) -> dict:
    """
    Find a phrase in the corpus, trying exact match first, then fuzzy.

    Args:
        phrase: The text to find
        word_list: List of word dicts with timecodes
        corpus: Parallel list of normalized words
        start_idx: Index to start searching from
        fuzzy: Whether to try fuzzy matching if exact fails
        fuzzy_threshold: Minimum similarity for fuzzy match

    Returns:
        dict with match info:
        {
            'found': True/False,
            'exact': True/False,
            'start_idx': int,
            'end_idx': int,
            'score': float (1.0 for exact, <1.0 for fuzzy),
            'matched_text': str (what was actually matched)
        }
    """
    # Try exact match first
    exact_match = find_phrase_exact(phrase, word_list, corpus, start_idx)

    if exact_match:
        start_idx, end_idx = exact_match
        matched_text = ' '.join(w['text'] for w in word_list[start_idx:end_idx + 1])
        return {
            'found': True,
            'exact': True,
            'start_idx': start_idx,
            'end_idx': end_idx,
            'score': 1.0,
            'matched_text': matched_text
        }

    # Try fuzzy match if enabled
    if fuzzy:
        fuzzy_match = find_phrase_fuzzy(phrase, word_list, corpus, fuzzy_threshold, start_idx)

        if fuzzy_match:
            start_idx, end_idx, score = fuzzy_match
            matched_text = ' '.join(w['text'] for w in word_list[start_idx:end_idx + 1])
            return {
                'found': True,
                'exact': False,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'score': score,
                'matched_text': matched_text
            }

    # No match found
    return {
        'found': False,
        'exact': False,
        'start_idx': None,
        'end_idx': None,
        'score': 0.0,
        'matched_text': None
    }


def strip_speaker_labels(text: str) -> str:
    """
    Strip common speaker label patterns from text.

    Removes patterns like:
    - "STEVE: blah blah" → "blah blah"
    - "[STEVE] blah blah" → "blah blah"
    - "STEVE - blah blah" → "blah blah"
    - "Steve: blah blah" → "blah blah"

    Only strips at the beginning of lines, preserving mid-sentence names.
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Pattern 1: "NAME:" or "NAME :" at start of line (with optional spaces)
        # Matches: "STEVE:", "Steve:", "STEVE :", "Steve Cortes:", etc.
        line = re.sub(r'^[\s]*[A-Za-z]+(?:\s+[A-Za-z]+)?[\s]*:\s*', '', line)

        # Pattern 2: "[NAME]" at start of line
        # Matches: "[STEVE]", "[Steve]", "[STEVE CORTES]", etc.
        line = re.sub(r'^[\s]*\[[A-Za-z]+(?:\s+[A-Za-z]+)?\][\s]*', '', line)

        # Pattern 3: "NAME -" or "NAME –" at start of line (hyphen or en-dash)
        # Matches: "STEVE -", "Steve –", "STEVE CORTES -", etc.
        line = re.sub(r'^[\s]*[A-Za-z]+(?:\s+[A-Za-z]+)?[\s]*[-–]\s*', '', line)

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def split_into_chunks(text: str) -> list:
    """
    Split producer's text into sentence chunks.

    First strips speaker labels, then splits on sentence-ending punctuation.
    """
    # Strip speaker labels before chunking
    text = strip_speaker_labels(text)

    chunks = re.split(r'(?<=[.!?])\s+', text.strip())
    return [c.strip() for c in chunks if c.strip()]


def match_producer_text(producer_text: str, word_list: list,
                        fuzzy: bool = True, fuzzy_threshold: float = 0.85,
                        quiet: bool = False) -> tuple:
    """
    Match producer's text selection against the transcript.

    Uses chronological matching: assumes producer selected text in order,
    so each chunk is searched starting from where the last match ended.
    Falls back to full transcript search only if chronological match fails.

    Args:
        producer_text: The text the producer copied/pasted
        word_list: List of word dicts from build_word_list()
        fuzzy: Whether to enable fuzzy matching
        fuzzy_threshold: Minimum similarity for fuzzy matches
        quiet: Suppress progress output

    Returns:
        Tuple of (matched_clips, failed_clips):

        matched_clips: [
            {
                'chunk_num': 1,
                'text': 'What an electrifying experience.',
                'in_seconds': 12.18,
                'out_seconds': 13.68,
                'duration': 1.50,
                'speaker': 'TALENT',
                'match_type': 'exact' or 'fuzzy',
                'match_score': 1.0,
                'matched_text': 'What an electrifying experience.'
            },
            ...
        ]

        failed_clips: [
            {
                'chunk_num': 2,
                'text': 'This text could not be found...',
                'reason': 'no_match'
            },
            ...
        ]
    """
    corpus = build_search_corpus(word_list)
    chunks = split_into_chunks(producer_text)

    matched_clips = []
    failed_clips = []

    # Track position for chronological matching
    # Producer typically selects text in order, so search forward from last match
    expected_start_idx = 0

    for i, chunk in enumerate(chunks):
        # First: try matching from expected position (chronological order)
        result = find_phrase(chunk, word_list, corpus,
                            start_idx=expected_start_idx,
                            fuzzy=fuzzy, fuzzy_threshold=fuzzy_threshold)

        used_fallback = False

        # If not found at expected position, fall back to searching from beginning
        # This handles rare cases where producer selected out-of-order
        if not result['found'] and expected_start_idx > 0:
            result = find_phrase(chunk, word_list, corpus,
                                start_idx=0,
                                fuzzy=fuzzy, fuzzy_threshold=fuzzy_threshold)
            if result['found']:
                used_fallback = True
                if not quiet:
                    print(f"OUT-OF-ORDER chunk {i+1}: found at earlier position in transcript")

        if result['found']:
            start_word = word_list[result['start_idx']]
            end_word = word_list[result['end_idx']]

            # Only update expected position if match was found chronologically (not via fallback)
            # This prevents one bad/out-of-order match from derailing subsequent searches
            if not used_fallback:
                expected_start_idx = result['end_idx'] + 1

            matched_clips.append({
                'chunk_num': i + 1,
                'text': chunk,
                'in_seconds': start_word['start'],
                'out_seconds': end_word['end'],
                'duration': end_word['end'] - start_word['start'],
                'speaker': start_word['speaker'],
                'match_type': 'exact' if result['exact'] else 'fuzzy',
                'match_score': result['score'],
                'matched_text': result['matched_text'],
                'is_error': False
            })

            # Log fuzzy matches for awareness
            if not quiet and not result['exact']:
                print(f"FUZZY MATCH chunk {i+1} (score: {result['score']:.2f}):")
                print(f"  Requested: \"{chunk[:60]}...\"")
                print(f"  Matched:   \"{result['matched_text'][:60]}...\"")
        else:
            failed_clips.append({
                'chunk_num': i + 1,
                'text': chunk,
                'reason': 'no_match',
                'is_error': True
            })
            if not quiet:
                print(f"NO MATCH chunk {i+1}: \"{chunk[:60]}...\"")

    return matched_clips, failed_clips
