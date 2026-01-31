"""
Core workflow orchestration for Sheetscut.

Main entry point for processing producer paper edits into Premiere sequences.
"""

from .transcript import load_transcript, build_word_list
from .matcher import match_producer_text
from .xml_generator import generate_premiere_xml


def merge_continuous_clips(clips: list, framerate: float = 29.97, merge_threshold: float = 0.5, crosstalk_threshold: float = 1.5) -> tuple:
    """
    Merge consecutive clips that are continuous in source timecode.

    In professional documentary editing, we don't want jump cuts within
    a soundbite. This function merges clips that are close together (within
    merge_threshold) into single clips, and identifies where actual
    jump cuts occur (larger gaps between separate interview sections).

    A "jump cut" is specifically defined as a time shift when the SAME
    speaker is talking that exceeds the merge threshold - this creates a
    visible discontinuity that needs B-roll or a camera cut to cover.

    Speaker changes are tracked separately - they're natural edit points,
    not problems to fix.

    Crosstalk (short "yeah", "exactly", etc.) from one speaker during
    another speaker's continuous speech is absorbed - it doesn't create
    speaker change markers.

    Args:
        clips: List of matched clip dicts, sorted by timeline order
        framerate: Video framerate for frame-accurate gap detection
        merge_threshold: Maximum gap in seconds to merge (default 0.5s)
            - Small gaps (< merge_threshold) within same speaker are merged
            - Larger gaps become jump cut markers
        crosstalk_threshold: Maximum duration in seconds for crosstalk detection (default 1.5s)
            - Short clips under this threshold containing only acknowledgment words
            - That are surrounded by the same other speaker on both sides
            - Will be absorbed rather than creating speaker change markers

    Returns:
        tuple: (merged_clips, edit_points)
        - merged_clips: List of clips with continuous sections merged
        - edit_points: List of dicts describing edit transitions
          Each dict includes:
            - 'type': 'jump_cut' (same speaker, time gap) or 'speaker_change'
            - 'gap_seconds': time gap in source
            - 'from_speaker', 'to_speaker': speaker names
            - etc.
    """
    if not clips:
        return [], []

    # Sort clips by their original chunk_num to maintain selection order
    sorted_clips = sorted(clips, key=lambda x: x['chunk_num'])

    # Pre-process: identify and mark crosstalk to absorb
    # Crosstalk is a short clip surrounded by the SAME other speaker
    sorted_clips = _mark_crosstalk(sorted_clips, crosstalk_threshold)

    merged_clips = []
    edit_points = []

    current_merged = None

    for clip in sorted_clips:
        # Check if this clip is marked as an absorbable affirmation
        absorb_into = clip.get('absorb_into_speaker')

        if current_merged is None:
            # Start a new merged clip (skip affirmations at the very start)
            if absorb_into:
                # Can't absorb if there's nothing to absorb into yet - just skip
                continue

            current_merged = {
                'chunk_num': clip['chunk_num'],
                'text': clip['text'],
                'in_seconds': clip['in_seconds'],
                'out_seconds': clip['out_seconds'],
                'duration': clip['duration'],
                'match_type': clip.get('match_type', 'exact'),
                'match_score': clip.get('match_score', 1.0),
                'matched_text': clip.get('matched_text', clip['text']),
                'speaker': clip.get('speaker', 'UNKNOWN'),
                'merged_chunks': [clip['chunk_num']]
            }
        else:
            # Check if this clip should be absorbed into surrounding speech
            if absorb_into and _speakers_match(absorb_into, current_merged.get('speaker', 'UNKNOWN')):
                # This is an affirmation that should be absorbed - extend the current clip
                # to include this timecode range but keep the original speaker
                current_merged['out_seconds'] = clip['out_seconds']
                current_merged['duration'] = current_merged['out_seconds'] - current_merged['in_seconds']
                # Optionally include the affirmation text in brackets
                current_merged['text'] += f" [{clip['text']}]"
                current_merged['matched_text'] += f" [{clip.get('matched_text', clip['text'])}]"
                current_merged['merged_chunks'].append(clip['chunk_num'])
                continue

            # Check if this clip is continuous with the current merged clip
            gap = clip['in_seconds'] - current_merged['out_seconds']
            from_speaker = current_merged.get('speaker', 'UNKNOWN')
            to_speaker = clip.get('speaker', 'UNKNOWN')
            same_speaker = _speakers_match(from_speaker, to_speaker)

            if abs(gap) <= merge_threshold and same_speaker:
                # Close enough and same speaker! Merge into current clip
                current_merged['out_seconds'] = clip['out_seconds']
                current_merged['duration'] = current_merged['out_seconds'] - current_merged['in_seconds']
                current_merged['text'] += ' ' + clip['text']
                current_merged['matched_text'] += ' ' + clip.get('matched_text', clip['text'])
                current_merged['merged_chunks'].append(clip['chunk_num'])

                # If any merged clip was fuzzy, mark the whole thing as fuzzy
                if clip.get('match_type') == 'fuzzy':
                    current_merged['match_type'] = 'fuzzy'
                    # Keep the lower match score
                    if clip.get('match_score', 1.0) < current_merged.get('match_score', 1.0):
                        current_merged['match_score'] = clip['match_score']
            else:
                # Discontinuity detected - save the current merged clip
                merged_clips.append(current_merged)

                # Determine edit point type
                if same_speaker and abs(gap) > merge_threshold:
                    # Same speaker but time gap exceeds threshold = JUMP CUT (needs B-roll)
                    edit_type = 'jump_cut'
                elif not same_speaker:
                    # Different speaker = natural transition
                    edit_type = 'speaker_change'
                else:
                    # Fallback (shouldn't happen)
                    edit_type = 'transition'

                # Record the edit point
                edit_points.append({
                    'type': edit_type,
                    'timeline_position': sum(c['duration'] for c in merged_clips),
                    'gap_seconds': gap,
                    'from_chunk': current_merged['merged_chunks'][-1],
                    'to_chunk': clip['chunk_num'],
                    'from_timecode': current_merged['out_seconds'],
                    'to_timecode': clip['in_seconds'],
                    'from_speaker': from_speaker,
                    'to_speaker': to_speaker
                })

                # Start a new merged clip
                current_merged = {
                    'chunk_num': clip['chunk_num'],
                    'text': clip['text'],
                    'in_seconds': clip['in_seconds'],
                    'out_seconds': clip['out_seconds'],
                    'duration': clip['duration'],
                    'match_type': clip.get('match_type', 'exact'),
                    'match_score': clip.get('match_score', 1.0),
                    'matched_text': clip.get('matched_text', clip['text']),
                    'speaker': clip.get('speaker', 'UNKNOWN'),
                    'merged_chunks': [clip['chunk_num']]
                }

    # Don't forget the last merged clip
    if current_merged is not None:
        merged_clips.append(current_merged)

    return merged_clips, edit_points


def _speakers_match(speaker1: str, speaker2: str) -> bool:
    """
    Check if two speaker names refer to the same person.

    Handles case-insensitive comparison and common variations.
    """
    if not speaker1 or not speaker2:
        return False

    s1 = speaker1.strip().upper()
    s2 = speaker2.strip().upper()

    return s1 == s2


# Common crosstalk words - short acknowledgments one speaker says during another's speech
CROSSTALK_WORDS = {
    'yeah', 'yes', 'yep', 'yup', 'uh-huh', 'uhuh', 'mhm', 'mmhmm', 'mm-hmm',
    'right', 'exactly', 'correct', 'okay', 'ok', 'sure', 'absolutely',
    'definitely', 'indeed', 'true', 'agreed', 'totally'
}


def _is_crosstalk_phrase(text: str, max_words: int = 4) -> bool:
    """
    Check if text consists only of crosstalk/acknowledgment words.

    Args:
        text: The text to check
        max_words: Maximum number of words to consider as crosstalk (default 4)

    Returns:
        True if text is purely crosstalk (e.g., "Yeah", "Exactly", "Yeah exactly")
    """
    if not text:
        return False

    # Normalize and split into words
    words = text.strip().lower().replace('.', '').replace(',', '').replace('!', '').split()

    # Too many words to be simple crosstalk
    if len(words) > max_words:
        return False

    # All words must be crosstalk words
    return all(word in CROSSTALK_WORDS for word in words)


def _mark_crosstalk(clips: list, crosstalk_threshold: float = 1.5) -> list:
    """
    Mark short crosstalk clips that should be absorbed into surrounding speech.

    Crosstalk is when one speaker briefly acknowledges ("Yeah", "Exactly", etc.)
    while the other speaker is still talking. We don't want these brief
    interjections to create speaker change markers.

    A clip is marked as crosstalk when:
    1. Short duration (< crosstalk_threshold seconds)
    2. Contains only crosstalk words (yeah, exactly, right, okay, etc.)
    3. Surrounded by the SAME OTHER speaker on BOTH sides

    Args:
        clips: List of clips sorted by chunk_num
        crosstalk_threshold: Maximum duration in seconds to consider as crosstalk (default 1.5s)

    Returns:
        List of clips with 'absorb_into_speaker' field added to crosstalk clips
    """
    if len(clips) < 3:
        # Need at least 3 clips to have a middle one surrounded by others
        return clips

    result = []
    for i, clip in enumerate(clips):
        clip_copy = clip.copy()

        # Check if this could be crosstalk
        if (clip.get('duration', 999) <= crosstalk_threshold and
            _is_crosstalk_phrase(clip.get('text', ''))):

            # Look for surrounding clips from the same OTHER speaker
            prev_speaker = None
            next_speaker = None

            # Find previous non-crosstalk clip
            for j in range(i - 1, -1, -1):
                if not _is_crosstalk_phrase(clips[j].get('text', '')):
                    prev_speaker = clips[j].get('speaker', 'UNKNOWN')
                    break

            # Find next non-crosstalk clip
            for j in range(i + 1, len(clips)):
                if not _is_crosstalk_phrase(clips[j].get('text', '')):
                    next_speaker = clips[j].get('speaker', 'UNKNOWN')
                    break

            current_speaker = clip.get('speaker', 'UNKNOWN')

            # Crosstalk if: different speaker AND surrounded by SAME other speaker
            if (prev_speaker and next_speaker and
                not _speakers_match(current_speaker, prev_speaker) and
                _speakers_match(prev_speaker, next_speaker)):

                clip_copy['absorb_into_speaker'] = prev_speaker

        result.append(clip_copy)

    return result


def process_paper_edit(
    transcript_json: str,
    producer_text: str,
    source_media: str,
    output_xml: str,
    fuzzy_matching: bool = True,
    fuzzy_threshold: float = 0.85,
    error_slug_duration: float = 3.0,
    include_markers: bool = True,
    continuous_mode: bool = False,
    crosstalk_threshold: float = 1.5,
    quiet: bool = False,
    **kwargs
) -> dict:
    """
    Main entry point: process a producer's paper edit into a Premiere sequence.

    Args:
        transcript_json: Path to Adobe JSON transcript with word-level timecodes
        producer_text: The text the producer selected/arranged
        source_media: Path to the source video file
        output_xml: Where to save the generated XML
        fuzzy_matching: Enable fuzzy matching for imperfect text
        fuzzy_threshold: Minimum similarity (0.0-1.0) for fuzzy matches
        error_slug_duration: Duration of error placeholder slugs in seconds
        include_markers: Add markers for errors and fuzzy matches
        continuous_mode: Merge continuous clips to avoid internal jump cuts (pro mode)
        crosstalk_threshold: Max duration (seconds) for crosstalk detection (default 1.5s)
            When enabled, short acknowledgments ("yeah", "exactly") from one speaker
            during another's continuous speech are absorbed, not marked as speaker changes.
        quiet: Suppress progress output
        **kwargs: Additional args passed to generate_premiere_xml()

    Returns:
        dict with results:
        {
            'success': True,
            'clips_matched': 6,
            'clips_failed': 1,
            'clips_fuzzy': 0,
            'total_duration': 19.52,
            'output_path': '/path/to/output.xml',
            'matched_clips': [...],
            'failed_clips': [...]
        }
    """
    # Load transcript
    transcript = load_transcript(transcript_json)
    word_list = build_word_list(transcript)

    if not quiet:
        print(f"Loaded transcript: {len(word_list)} words")

    # Match producer's text
    matched_clips, failed_clips = match_producer_text(
        producer_text, word_list,
        fuzzy=fuzzy_matching,
        fuzzy_threshold=fuzzy_threshold,
        quiet=quiet
    )

    if not quiet:
        print(f"\nMatching complete:")
        print(f"  Matched: {len(matched_clips)}")
        print(f"  Failed:  {len(failed_clips)}")

    if not matched_clips and not failed_clips:
        return {
            'success': False,
            'error': 'No text chunks found in input',
            'clips_matched': 0,
            'clips_failed': 0
        }

    # Count fuzzy matches
    fuzzy_count = sum(1 for c in matched_clips if c.get('match_type') == 'fuzzy')
    if not quiet and fuzzy_count:
        print(f"  Fuzzy:   {fuzzy_count}")

    # Continuous mode: merge clips to avoid internal jump cuts
    jump_cuts = []
    if continuous_mode and matched_clips:
        framerate = kwargs.get('framerate', 29.97)
        merge_threshold = kwargs.get('merge_threshold', 1.0)
        original_count = len(matched_clips)
        matched_clips, jump_cuts = merge_continuous_clips(
            matched_clips, framerate, merge_threshold, crosstalk_threshold
        )

        if not quiet:
            print(f"\nContinuous mode enabled:")
            print(f"  Original clips: {original_count}")
            print(f"  After merging:  {len(matched_clips)}")
            print(f"  Jump cuts:      {len(jump_cuts)}")

    # Generate XML
    output_path = generate_premiere_xml(
        clips=matched_clips,
        failed_clips=failed_clips,
        source_file=source_media,
        output_path=output_xml,
        error_slug_duration=error_slug_duration,
        include_markers=include_markers,
        jump_cuts=jump_cuts,
        **kwargs
    )

    total_duration = sum(c['duration'] for c in matched_clips)
    total_duration += len(failed_clips) * error_slug_duration

    if not quiet:
        print(f"\nGenerated: {output_path}")
        print(f"Total duration: {total_duration:.2f}s")

        if failed_clips:
            print(f"\n{len(failed_clips)} error slug(s) added to timeline")

    return {
        'success': True,
        'clips_matched': len(matched_clips),
        'clips_failed': len(failed_clips),
        'clips_fuzzy': fuzzy_count,
        'total_duration': total_duration,
        'output_path': output_path,
        'matched_clips': matched_clips,
        'failed_clips': failed_clips
    }
