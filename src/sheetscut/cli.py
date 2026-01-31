"""
Command-line interface for Sheetscut.

Provides argparse-based CLI with all configuration options.
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import process_paper_edit


def main(argv=None):
    """Main entry point for sheetscut CLI."""
    parser = argparse.ArgumentParser(
        prog='sheetscut',
        description='Producer paper edit to Premiere Pro sequence generator',
        epilog='Example: sheetscut transcript.json -t "Selected text here" -o rough_cut.xml'
    )

    parser.add_argument(
        'transcript',
        help='Path to Adobe JSON transcript with word-level timecodes'
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        '-t', '--text',
        metavar='TEXT',
        help='Producer text (inline)'
    )
    input_group.add_argument(
        '-i', '--input',
        metavar='FILE',
        help='Producer text file'
    )

    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        default='output_sequence.xml',
        help='Output XML file (default: output_sequence.xml)'
    )

    parser.add_argument(
        '-m', '--media',
        metavar='PATH',
        help='Source media path (default: derived from transcript path)'
    )

    parser.add_argument(
        '--framerate',
        type=float,
        default=29.97,
        help='Video framerate (default: 29.97)'
    )

    parser.add_argument(
        '--no-fuzzy',
        action='store_true',
        help='Disable fuzzy matching'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.85,
        help='Fuzzy match threshold 0.0-1.0 (default: 0.85)'
    )

    parser.add_argument(
        '--error-duration',
        type=float,
        default=3.0,
        help='Error slug duration in seconds (default: 3.0)'
    )

    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Pro mode: merge continuous clips, add red markers for jump cuts'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args(argv)

    # Validate transcript exists
    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Error: Transcript file not found: {args.transcript}", file=sys.stderr)
        sys.exit(1)

    # Get producer text from various sources
    if args.text:
        producer_text = args.text
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        producer_text = input_path.read_text()
    else:
        # Read from stdin
        if not args.quiet:
            print("Paste producer's text selection (Ctrl+D when done):", file=sys.stderr)
            print("-" * 40, file=sys.stderr)
        producer_text = sys.stdin.read()
        if not args.quiet:
            print("-" * 40, file=sys.stderr)
            print(file=sys.stderr)

    if not producer_text.strip():
        print("Error: No producer text provided", file=sys.stderr)
        sys.exit(1)

    # Determine source media path
    if args.media:
        source_media = args.media
    else:
        # Derive from transcript path (remove .json extension)
        source_media = str(transcript_path).replace('.json', '')

    # Print configuration
    if not args.quiet:
        print(f"Transcript: {args.transcript}")
        print(f"Source media: {source_media}")
        print(f"Output: {args.output}")
        fuzzy_status = 'OFF' if args.no_fuzzy else f'ON (threshold: {args.threshold})'
        print(f"Fuzzy matching: {fuzzy_status}")
        if args.continuous:
            print(f"Continuous mode: ON (merge clips, mark jump cuts)")
        print()

    # Process the paper edit
    result = process_paper_edit(
        transcript_json=args.transcript,
        producer_text=producer_text,
        source_media=source_media,
        output_xml=args.output,
        fuzzy_matching=not args.no_fuzzy,
        fuzzy_threshold=args.threshold,
        error_slug_duration=args.error_duration,
        continuous_mode=args.continuous,
        framerate=args.framerate,
        quiet=args.quiet
    )

    if result['success']:
        if not args.quiet:
            print()
            print("=== SEQUENCE SUMMARY ===")

            # Merge and sort by chunk_num for display
            all_items = [(c, 'match') for c in result['matched_clips']]
            all_items += [(c, 'error') for c in result['failed_clips']]
            all_items.sort(key=lambda x: x[0]['chunk_num'])

            for item, item_type in all_items:
                if item_type == 'match':
                    match_indicator = "+" if item.get('match_type') == 'exact' else f"~ ({item.get('match_score', 1.0):.0%})"
                    speaker = item.get('speaker', 'SPEAKER')
                    print(f"  {match_indicator} {item['chunk_num']}. [{item['in_seconds']:.2f}s - {item['out_seconds']:.2f}s] {speaker}")
                else:
                    print(f"  x {item['chunk_num']}. [ERROR SLUG] Could not match")

                preview = item['text'][:50] + '...' if len(item['text']) > 50 else item['text']
                print(f"       \"{preview}\"")

        sys.exit(0)
    else:
        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
