"""
Utility functions for Sheetscut.

Provides timecode conversion, text wrapping, and other helper functions.
"""


def seconds_to_frames(seconds: float, framerate: float = 29.97) -> int:
    """Convert seconds to frame count."""
    return int(round(seconds * framerate))


def frames_to_timecode(frames: int, framerate: float = 29.97, drop_frame: bool = True) -> str:
    """
    Convert frame count to SMPTE timecode string.

    Args:
        frames: Frame count
        framerate: Video framerate
        drop_frame: Whether to use drop-frame timecode for 29.97fps

    Returns:
        SMPTE timecode string (e.g., "00;01;23;15" for drop-frame)
    """
    if drop_frame and abs(framerate - 29.97) < 0.01:
        # Drop frame calculation for 29.97
        D = frames // 17982
        M = frames % 17982
        if M < 2:
            M = M + 2
        frames_adj = frames + 18 * D + 2 * ((M - 2) // 1798)

        ff = frames_adj % 30
        ss = (frames_adj // 30) % 60
        mm = (frames_adj // 1800) % 60
        hh = frames_adj // 108000

        return f"{hh:02d};{mm:02d};{ss:02d};{ff:02d}"
    else:
        # Non-drop frame
        fps = int(round(framerate))
        ff = frames % fps
        ss = (frames // fps) % 60
        mm = (frames // (fps * 60)) % 60
        hh = frames // (fps * 3600)

        return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def wrap_text(text: str, max_chars: int = 40) -> list:
    """
    Wrap text into lines of max_chars width, breaking at word boundaries.

    Args:
        text: The text to wrap
        max_chars: Maximum characters per line

    Returns:
        List of lines
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_len = len(word)
        # +1 for the space before the word (except for first word in line)
        space_needed = word_len + (1 if current_line else 0)

        if current_length + space_needed <= max_chars:
            current_line.append(word)
            current_length += space_needed
        else:
            # Start a new line
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_len

    # Don't forget the last line
    if current_line:
        lines.append(' '.join(current_line))

    return lines
