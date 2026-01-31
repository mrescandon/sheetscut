"""
Transcript parsing for Sheetscut.

Handles loading and processing Adobe JSON transcripts with word-level timecodes.
"""

import json


def load_transcript(json_path: str) -> dict:
    """Load Adobe JSON transcript file."""
    with open(json_path, "r") as f:
        return json.load(f)


def build_word_list(transcript: dict) -> list:
    """
    Flatten transcript segments into a single list of words with timecodes.

    Filters out empty string tokens that Adobe sometimes includes.

    Returns list of dicts:
        {
            'text': 'Hello',
            'start': 1.23,        # seconds
            'end': 1.45,          # seconds
            'duration': 0.22,     # seconds
            'speaker': 'TALENT',
            'confidence': 0.95
        }
    """
    all_words = []

    # Build speaker lookup
    speakers = {s['id']: s['name'] for s in transcript.get('speakers', [])}

    for seg in transcript['segments']:
        speaker_name = speakers.get(seg['speaker'], 'Unknown')

        for word in seg['words']:
            # Skip empty strings (Adobe artifact)
            if not word['text'].strip():
                continue

            all_words.append({
                'text': word['text'],
                'start': word['start'],
                'duration': word['duration'],
                'end': word['start'] + word['duration'],
                'speaker': speaker_name,
                'confidence': word.get('confidence', 1.0)
            })

    return all_words
