"""
FCP XML generation for Sheetscut.

Generates Premiere Pro compatible XML sequences from matched clips.
"""

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from .utils import seconds_to_frames, frames_to_timecode, wrap_text


def create_text_generator_element(
    item_id: str,
    name: str,
    text: str,
    duration_frames: int,
    timebase: int,
    ntsc: bool,
    vert_position: float = 0.0
) -> Element:
    """
    Create an Outline Text generatoritem element for use inside a nested sequence.

    Args:
        item_id: Unique ID for this generatoritem
        name: Display name
        text: Text content to display
        duration_frames: Duration in frames
        timebase: Frame rate timebase
        ntsc: Whether NTSC timing
        vert_position: Vertical position (-0.5 to 0.5, 0=center)

    Returns:
        generatoritem Element
    """
    gen = Element('generatoritem', id=item_id)
    SubElement(gen, 'name').text = name
    SubElement(gen, 'duration').text = str(duration_frames)

    rate = SubElement(gen, 'rate')
    SubElement(rate, 'timebase').text = str(timebase)
    SubElement(rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    # Inside nested sequence, generators always start at 0
    SubElement(gen, 'start').text = "0"
    SubElement(gen, 'end').text = str(duration_frames)
    SubElement(gen, 'in').text = "0"
    SubElement(gen, 'out').text = str(duration_frames)
    SubElement(gen, 'enabled').text = "TRUE"
    SubElement(gen, 'anamorphic').text = "FALSE"
    SubElement(gen, 'alphatype').text = "black"

    effect = SubElement(gen, 'effect')
    SubElement(effect, 'name').text = "Outline Text"
    SubElement(effect, 'effectid').text = "Outline Text"
    SubElement(effect, 'effectcategory').text = "Text"
    SubElement(effect, 'effecttype').text = "generator"
    SubElement(effect, 'mediatype').text = "video"

    # Text parameter
    param_text = SubElement(effect, 'parameter')
    SubElement(param_text, 'parameterid').text = "str"
    SubElement(param_text, 'name').text = "Text"
    SubElement(param_text, 'value').text = text

    # Origin parameter for vertical positioning
    param_origin = SubElement(effect, 'parameter')
    SubElement(param_origin, 'parameterid').text = "origin"
    SubElement(param_origin, 'name').text = "Origin"
    origin_value = SubElement(param_origin, 'value')
    SubElement(origin_value, 'horiz').text = "0"
    SubElement(origin_value, 'vert').text = str(vert_position)

    return gen


def create_error_slug_nested_sequence(
    error_id: str,
    chunk_num: int,
    text_lines: list,
    duration_frames: int,
    start_frame: int,
    end_frame: int,
    timebase: int,
    ntsc: bool,
    width: int = 1920,
    height: int = 1080
) -> Element:
    """
    Create a nested sequence clipitem containing multi-line error text.

    This creates a compound clip that appears as a single item on the main
    timeline, with all text lines contained within.

    Args:
        error_id: Base ID for this error slug
        chunk_num: The chunk number this error corresponds to
        text_lines: List of text strings, one per line
        duration_frames: Duration in frames
        start_frame: Timeline start position (main sequence)
        end_frame: Timeline end position (main sequence)
        timebase: Frame rate timebase
        ntsc: Whether NTSC timing
        width: Video width
        height: Video height

    Returns:
        clipitem Element containing nested sequence
    """
    # Create the outer clipitem
    clipitem = Element('clipitem', id=f"nested-error-{error_id}")
    SubElement(clipitem, 'name').text = f"Error Slug {chunk_num}"
    SubElement(clipitem, 'duration').text = str(duration_frames)

    rate = SubElement(clipitem, 'rate')
    SubElement(rate, 'timebase').text = str(timebase)
    SubElement(rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    SubElement(clipitem, 'start').text = str(start_frame)
    SubElement(clipitem, 'end').text = str(end_frame)
    SubElement(clipitem, 'in').text = "0"
    SubElement(clipitem, 'out').text = str(duration_frames)

    # Create the nested sequence inside the clipitem
    nested_seq = SubElement(clipitem, 'sequence', id=f"error-seq-{error_id}")
    SubElement(nested_seq, 'name').text = f"Error Slug {chunk_num}"
    SubElement(nested_seq, 'duration').text = str(duration_frames)

    seq_rate = SubElement(nested_seq, 'rate')
    SubElement(seq_rate, 'timebase').text = str(timebase)
    SubElement(seq_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    # Nested sequence media
    media = SubElement(nested_seq, 'media')
    video = SubElement(media, 'video')

    # Video format
    v_format = SubElement(video, 'format')
    v_sample = SubElement(v_format, 'samplecharacteristics')
    SubElement(v_sample, 'width').text = str(width)
    SubElement(v_sample, 'height').text = str(height)
    v_rate = SubElement(v_sample, 'rate')
    SubElement(v_rate, 'timebase').text = str(timebase)
    SubElement(v_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    # Calculate vertical positions for text lines
    # Center the block vertically with 0.12 spacing
    line_spacing = 0.12
    num_lines = len(text_lines)
    total_height = (num_lines - 1) * line_spacing
    start_vert = -total_height / 2

    # Create a track for each line
    for line_idx, line_text in enumerate(text_lines):
        track = SubElement(video, 'track')
        vert_pos = start_vert + line_idx * line_spacing

        gen_elem = create_text_generator_element(
            item_id=f"text-{error_id}-{line_idx + 1}",
            name=f"Line {line_idx + 1}",
            text=line_text,
            duration_frames=duration_frames,
            timebase=timebase,
            ntsc=ntsc,
            vert_position=vert_pos
        )
        track.append(gen_elem)

    return clipitem


def generate_premiere_xml(
    clips: list,
    failed_clips: list,
    source_file: str,
    output_path: str,
    sequence_name: str = "Producer_Rough_Cut",
    framerate: float = 29.97,
    width: int = 1920,
    height: int = 1080,
    audio_channels: int = 2,
    audio_sample_rate: int = 48000,
    error_slug_duration: float = 3.0,
    include_markers: bool = True,
    jump_cuts: list = None
) -> str:
    """
    Generate FCP XML 4 format that Premiere Pro can import.

    Args:
        clips: List of matched clip dicts from match_producer_text()
        failed_clips: List of failed clip dicts to create error slugs for
        source_file: Path to source media file
        output_path: Where to save the XML
        sequence_name: Name for the sequence in Premiere
        framerate: Video framerate (default 29.97)
        width: Video width
        height: Video height
        audio_channels: Number of audio channels (1=mono, 2=stereo)
        audio_sample_rate: Audio sample rate in Hz
        error_slug_duration: Duration of error placeholder slugs in seconds
        include_markers: Whether to add markers for errors and fuzzy matches
        jump_cuts: List of jump cut dicts from merge_continuous_clips() for red markers

    Returns:
        Path to generated XML file
    """
    if jump_cuts is None:
        jump_cuts = []
    # Merge clips and failed_clips in order by chunk_num
    all_items = []
    for clip in clips:
        all_items.append(('clip', clip))
    for failed in failed_clips:
        all_items.append(('error', failed))

    all_items.sort(key=lambda x: x[1]['chunk_num'])

    # Determine timebase for FCP XML
    if abs(framerate - 29.97) < 0.01:
        timebase = 30
        ntsc = True
    elif abs(framerate - 23.976) < 0.01:
        timebase = 24
        ntsc = True
    elif abs(framerate - 25.0) < 0.01:
        timebase = 25
        ntsc = False
    else:
        timebase = int(round(framerate))
        ntsc = False

    # Calculate total duration
    total_frames = 0
    for item_type, item in all_items:
        if item_type == 'clip':
            total_frames += seconds_to_frames(item['duration'], framerate)
        else:
            total_frames += seconds_to_frames(error_slug_duration, framerate)

    # Build XML structure
    xmeml = Element('xmeml', version="4")
    sequence = SubElement(xmeml, 'sequence')
    SubElement(sequence, 'name').text = sequence_name
    SubElement(sequence, 'duration').text = str(total_frames)

    # Sequence rate
    rate = SubElement(sequence, 'rate')
    SubElement(rate, 'timebase').text = str(timebase)
    SubElement(rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    # Timecode
    timecode_elem = SubElement(sequence, 'timecode')
    SubElement(timecode_elem, 'string').text = "00:00:00:00"
    tc_rate = SubElement(timecode_elem, 'rate')
    SubElement(tc_rate, 'timebase').text = str(timebase)
    SubElement(tc_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"
    SubElement(timecode_elem, 'displayformat').text = "DF" if ntsc else "NDF"

    # Media container
    media = SubElement(sequence, 'media')

    # === VIDEO ===
    video = SubElement(media, 'video')

    v_format = SubElement(video, 'format')
    v_sample = SubElement(v_format, 'samplecharacteristics')
    SubElement(v_sample, 'width').text = str(width)
    SubElement(v_sample, 'height').text = str(height)
    v_rate = SubElement(v_sample, 'rate')
    SubElement(v_rate, 'timebase').text = str(timebase)
    SubElement(v_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

    video_track = SubElement(video, 'track')

    # Get source filename for clip naming
    source_filename = Path(source_file).name

    # Create file element for source media
    def create_file_element():
        file_elem = Element('file', id="file-1")
        SubElement(file_elem, 'name').text = source_filename

        abs_path = str(Path(source_file).resolve())
        SubElement(file_elem, 'pathurl').text = f"file://localhost{abs_path}"

        f_rate = SubElement(file_elem, 'rate')
        SubElement(f_rate, 'timebase').text = str(timebase)
        SubElement(f_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

        SubElement(file_elem, 'duration').text = str(seconds_to_frames(300, framerate))

        f_media = SubElement(file_elem, 'media')

        f_video = SubElement(f_media, 'video')
        fv_sample = SubElement(f_video, 'samplecharacteristics')
        SubElement(fv_sample, 'width').text = str(width)
        SubElement(fv_sample, 'height').text = str(height)
        fv_rate = SubElement(fv_sample, 'rate')
        SubElement(fv_rate, 'timebase').text = str(timebase)
        SubElement(fv_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

        f_audio = SubElement(f_media, 'audio')
        fa_sample = SubElement(f_audio, 'samplecharacteristics')
        SubElement(fa_sample, 'samplerate').text = str(audio_sample_rate)
        SubElement(fa_sample, 'depth').text = "16"
        SubElement(f_audio, 'channelcount').text = str(audio_channels)

        # Define individual audio tracks for each channel (required for Premiere to see stereo)
        for ch in range(1, audio_channels + 1):
            audio_track = SubElement(f_audio, 'track')
            SubElement(audio_track, 'channelindex').text = str(ch)
            SubElement(audio_track, 'samplerate').text = str(audio_sample_rate)
            SubElement(audio_track, 'depth').text = "16"

        return file_elem

    # Markers list (to add to sequence)
    markers = []

    # Add video clips and error slugs
    timeline_pos = 0
    file_defined = False
    clip_index = 0

    for item_type, item in all_items:
        if item_type == 'clip':
            # Regular matched clip
            clip_index += 1
            in_frames = seconds_to_frames(item['in_seconds'], framerate)
            out_frames = seconds_to_frames(item['out_seconds'], framerate)
            duration_frames = out_frames - in_frames

            clipitem = SubElement(video_track, 'clipitem', id=f"clipitem-{clip_index}")
            SubElement(clipitem, 'name').text = source_filename
            SubElement(clipitem, 'duration').text = str(duration_frames)

            c_rate = SubElement(clipitem, 'rate')
            SubElement(c_rate, 'timebase').text = str(timebase)
            SubElement(c_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

            SubElement(clipitem, 'start').text = str(timeline_pos)
            SubElement(clipitem, 'end').text = str(timeline_pos + duration_frames)
            SubElement(clipitem, 'in').text = str(in_frames)
            SubElement(clipitem, 'out').text = str(out_frames)

            if not file_defined:
                clipitem.append(create_file_element())
                file_defined = True
            else:
                SubElement(clipitem, 'file', id="file-1")

            # Link to audio clips
            for ch in range(1, audio_channels + 1):
                link = SubElement(clipitem, 'link')
                SubElement(link, 'linkclipref').text = f"audio-clipitem-{clip_index}-{ch}"

            # Add marker for fuzzy matches with full context
            if include_markers and item.get('match_type') == 'fuzzy':
                tc_start = frames_to_timecode(timeline_pos, framerate, ntsc)
                tc_end = frames_to_timecode(timeline_pos + duration_frames, framerate, ntsc)
                source_tc_in = frames_to_timecode(in_frames, framerate, ntsc)
                source_tc_out = frames_to_timecode(out_frames, framerate, ntsc)

                markers.append({
                    'start': timeline_pos,
                    'name': f"FUZZY #{item['chunk_num']} ({item['match_score']:.0%}) @ {tc_start}",
                    'comment': f"TIMELINE: {tc_start} - {tc_end}\nSOURCE: {source_tc_in} - {source_tc_out}\n\nREQUESTED:\n{item['text']}\n\nMATCHED ({item['match_score']:.0%}):\n{item['matched_text']}"
                })

            timeline_pos += duration_frames

        else:
            # Error - create nested sequence error slug on the main video track
            duration_frames = seconds_to_frames(error_slug_duration, framerate)

            # Calculate timecode for this position
            tc_in = frames_to_timecode(timeline_pos, framerate, ntsc)
            tc_out = frames_to_timecode(timeline_pos + duration_frames, framerate, ntsc)

            # Full text from producer (don't truncate for marker)
            full_error_text = item['text']

            # Wrap the error text into lines for display
            header = "COULD NOT MATCH:"
            body_lines = wrap_text(item['text'], max_chars=40)
            text_lines = [header] + body_lines

            # Create nested sequence error slug
            error_slug = create_error_slug_nested_sequence(
                error_id=str(item['chunk_num']),
                chunk_num=item['chunk_num'],
                text_lines=text_lines,
                duration_frames=duration_frames,
                start_frame=timeline_pos,
                end_frame=timeline_pos + duration_frames,
                timebase=timebase,
                ntsc=ntsc,
                width=width,
                height=height
            )
            video_track.append(error_slug)

            # Add marker for error with full context
            if include_markers:
                markers.append({
                    'start': timeline_pos,
                    'name': f"[MISSING] #{item['chunk_num']}",
                    'comment': f"TIMELINE: {tc_in} - {tc_out}\nCHUNK #{item['chunk_num']} EXPECTED:\n\n{full_error_text}"
                })

            timeline_pos += duration_frames

    # === AUDIO ===
    audio = SubElement(media, 'audio')

    a_format = SubElement(audio, 'format')
    a_sample = SubElement(a_format, 'samplecharacteristics')
    SubElement(a_sample, 'samplerate').text = str(audio_sample_rate)
    SubElement(a_sample, 'depth').text = "16"

    # Create audio tracks for matched clips only (errors have no audio)
    for ch in range(1, audio_channels + 1):
        audio_track = SubElement(audio, 'track')
        SubElement(audio_track, 'outputchannelindex').text = str(ch)

        timeline_pos = 0
        clip_index = 0

        for item_type, item in all_items:
            if item_type == 'clip':
                clip_index += 1
                in_frames = seconds_to_frames(item['in_seconds'], framerate)
                out_frames = seconds_to_frames(item['out_seconds'], framerate)
                duration_frames = out_frames - in_frames

                clipitem = SubElement(audio_track, 'clipitem', id=f"audio-clipitem-{clip_index}-{ch}")
                SubElement(clipitem, 'name').text = source_filename
                SubElement(clipitem, 'duration').text = str(duration_frames)

                c_rate = SubElement(clipitem, 'rate')
                SubElement(c_rate, 'timebase').text = str(timebase)
                SubElement(c_rate, 'ntsc').text = "TRUE" if ntsc else "FALSE"

                SubElement(clipitem, 'start').text = str(timeline_pos)
                SubElement(clipitem, 'end').text = str(timeline_pos + duration_frames)
                SubElement(clipitem, 'in').text = str(in_frames)
                SubElement(clipitem, 'out').text = str(out_frames)

                SubElement(clipitem, 'file', id="file-1")

                # Sourcetrack with proper nested structure for channel selection
                sourcetrack = SubElement(clipitem, 'sourcetrack')
                SubElement(sourcetrack, 'mediatype').text = "audio"
                SubElement(sourcetrack, 'trackindex').text = str(ch)

                timeline_pos += duration_frames
            else:
                # Skip error slugs in audio - leave gap
                duration_frames = seconds_to_frames(error_slug_duration, framerate)
                timeline_pos += duration_frames

    # Add sequence markers
    if markers:
        for marker in markers:
            marker_elem = SubElement(sequence, 'marker')
            SubElement(marker_elem, 'name').text = marker['name']
            SubElement(marker_elem, 'comment').text = marker['comment']
            SubElement(marker_elem, 'in').text = str(marker['start'])
            SubElement(marker_elem, 'out').text = "-1"

    # Add edit point markers from continuous mode
    # jump_cuts parameter now contains edit_points with 'type' field
    if jump_cuts:
        # Calculate timeline positions for edit points
        # We need to map from original timeline position to merged timeline position
        timeline_pos = 0
        for i, clip in enumerate(clips):
            clip_frames = seconds_to_frames(clip['duration'], framerate)

            # Check if any edit point occurs at the start of this clip
            for ep in jump_cuts:
                # Edit point occurs between chunks - find the right position
                to_chunk = clip.get('merged_chunks', [clip['chunk_num']])[0] if 'merged_chunks' in clip else clip['chunk_num']
                if ep['to_chunk'] == to_chunk:
                    # This edit point happens at the start of this clip
                    gap_str = f"{abs(ep['gap_seconds']):.2f}s"
                    source_from = frames_to_timecode(seconds_to_frames(ep['from_timecode'], framerate), framerate, ntsc)
                    source_to = frames_to_timecode(seconds_to_frames(ep['to_timecode'], framerate), framerate, ntsc)

                    edit_type = ep.get('type', 'jump_cut')
                    from_speaker = ep.get('from_speaker', 'UNKNOWN')
                    to_speaker = ep.get('to_speaker', 'UNKNOWN')

                    marker_elem = SubElement(sequence, 'marker')

                    if edit_type == 'jump_cut':
                        # Red marker for jump cuts (same speaker, time gap - needs B-roll)
                        SubElement(marker_elem, 'name').text = f"JUMP CUT ({gap_str} gap)"
                        SubElement(marker_elem, 'comment').text = (
                            f"JUMP CUT DETECTED - SAME SPEAKER ({from_speaker})\n\n"
                            f"Source jumps from {source_from} to {source_to}\n"
                            f"Gap: {gap_str}\n\n"
                            f"Cover with B-roll or camera cut."
                        )
                        SubElement(marker_elem, 'color').text = "red"
                    elif edit_type == 'speaker_change':
                        # Blue marker for speaker changes (natural transition)
                        SubElement(marker_elem, 'name').text = f"{from_speaker} → {to_speaker}"
                        SubElement(marker_elem, 'comment').text = (
                            f"SPEAKER CHANGE\n\n"
                            f"From: {from_speaker}\n"
                            f"To: {to_speaker}\n"
                            f"Source: {source_from} → {source_to}\n"
                            f"Gap: {gap_str}"
                        )
                        SubElement(marker_elem, 'color').text = "blue"
                    else:
                        # Default marker for other transitions
                        SubElement(marker_elem, 'name').text = f"EDIT ({gap_str})"
                        SubElement(marker_elem, 'comment').text = f"Source: {source_from} → {source_to}"
                        SubElement(marker_elem, 'color').text = "white"

                    SubElement(marker_elem, 'in').text = str(timeline_pos)
                    SubElement(marker_elem, 'out').text = "-1"

            timeline_pos += clip_frames

    # Pretty print and save
    xml_str = minidom.parseString(tostring(xmeml)).toprettyxml(indent="  ")

    with open(output_path, 'w') as f:
        f.write(xml_str)

    return output_path
