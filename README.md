# Sheetscut

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![No Dependencies](https://img.shields.io/badge/dependencies-none-green.svg)]()

Convert producer paper edits into Premiere Pro sequences automatically.

## The Problem

Documentary and interview editors know this workflow: producers review transcripts and copy/paste the text chunks they want into a "paper edit" — essentially a text document of selected quotes arranged in order. The editor then manually finds each quote in the timeline and assembles the rough cut. It's tedious and time-consuming.

## The Solution

Sheetscut matches the producer's text selections back to word-level timecodes in the original transcript, then generates an FCP XML file that Premiere Pro imports as a ready-made sequence.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Video File     │────▶│  Transcribe     │────▶│  JSON Transcript│
│                 │     │  (Premiere Pro) │     │  (word-level TC)│
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│  Premiere Pro   │◀────│  Sheetscut      │◀─────────────┤
│  Rough Cut      │     │  (this tool)    │              │
└─────────────────┘     └────────┬────────┘              │
                                 │                       │
                        ┌────────┴────────┐              │
                        │  Producer       │◀─────────────┘
                        │  Paper Edit     │
                        │  (text chunks)  │
                        └─────────────────┘
```

## Installation

```bash
pip install sheetscut
```

Or install from source:

```bash
git clone https://github.com/mrescandon/sheetscut.git
cd sheetscut
pip install .
```

## Quick Start

```bash
# Basic usage - paste text interactively
sheetscut transcript.json

# Provide text inline
sheetscut transcript.json -t "The text you want to find in the transcript"

# Read text from a file
sheetscut transcript.json -i paper_edit.txt

# Specify output path
sheetscut transcript.json -i paper_edit.txt -o rough_cut.xml
```

Then import the generated XML file into Premiere Pro (File → Import).

## Usage

### Command Line

```bash
sheetscut TRANSCRIPT [OPTIONS]
```

**Arguments:**
- `TRANSCRIPT` — Path to Adobe JSON transcript file (required)

**Input Options:**
- `-t, --text TEXT` — Producer text inline
- `-i, --input FILE` — Producer text from file
- *(no flag)* — Reads from stdin interactively

**Output Options:**
- `-o, --output FILE` — Output XML path (default: `output_sequence.xml`)
- `-q, --quiet` — Suppress progress output

**Matching Options:**
- `--no-fuzzy` — Disable fuzzy matching (exact matches only)
- `--threshold FLOAT` — Fuzzy match threshold, 0.0-1.0 (default: 0.85)
- `--error-duration FLOAT` — Error slug duration in seconds (default: 3.0)

**Media Options:**
- `-m, --media PATH` — Source media path for XML
- `--framerate FLOAT` — Video framerate (default: 29.97)

**Pro Editing:**
- `--continuous` — Merge continuous clips and mark jump cuts (see below)

**Other:**
- `-v, --version` — Show version number

### Python Library

```python
from sheetscut import process_paper_edit

result = process_paper_edit(
    transcript_path="interview.json",
    producer_text="The quotes I want to use from the interview.",
    output_path="rough_cut.xml",
    fuzzy_matching=True,
    fuzzy_threshold=0.85,
    continuous_mode=True
)

print(f"Matched {result['matched']} clips, {result['failed']} failed")
```

## Features

### Fuzzy Matching

When exact text matching fails (due to typos, formatting differences, or transcription errors), Sheetscut uses fuzzy matching to find approximate matches. Fuzzy matches are flagged with markers in the timeline so you can verify them.

```bash
# Adjust sensitivity (0.0-1.0, higher = stricter)
sheetscut transcript.json -t "Text" --threshold 0.90

# Disable fuzzy matching entirely
sheetscut transcript.json -t "Text" --no-fuzzy
```

### Error Handling

When text cannot be matched at all, Sheetscut inserts a visible "error slug" on the timeline with the unmatched text, plus a marker. The sequence continues processing — one failed match doesn't stop the whole edit.

### Continuous Mode

For professional rough cuts, use `--continuous` to merge clips that are continuous in source timecode and mark actual discontinuities:

```bash
sheetscut transcript.json -i paper_edit.txt --continuous
```

**What it does:**
- Merges adjacent clips that are continuous in the source (no gap)
- Adds red markers at actual jump cuts (where content was removed)
- Marker comments show gap duration and source timecode range

**Why it matters:** When a producer selects consecutive sentences, they may or may not be continuous in the source. Continuous mode makes internal jump cuts visible so editors know where B-roll or cutaways are needed.

## Transcript Requirements

Sheetscut requires **word-level timecodes** in JSON format. Currently, this is available from:

- **Adobe Premiere Pro Beta 26.1+** — Export transcript as JSON
- **WhisperX** — With word-level timestamps enabled

The JSON structure should include word-level timing:

```json
{
  "segments": [
    {
      "speaker": "speaker-id",
      "words": [
        {"text": "Hello", "start": 1.2, "duration": 0.3},
        {"text": "world", "start": 1.5, "duration": 0.4}
      ]
    }
  ]
}
```

**Note:** Standard transcript exports (CSV, TXT, SRT) only have segment-level timing and won't work.

## Output Format

Sheetscut generates FCP XML (version 4), which Premiere Pro imports natively. The sequence includes:

- Video track with matched clips
- Stereo audio tracks (properly linked)
- Markers for fuzzy matches and errors
- Error slugs as text generators for failed matches

## Requirements

- Python 3.9 or higher
- No external dependencies (stdlib only)

## Examples

**Process a single quote:**
```bash
sheetscut interview.json -t "I think the most important thing is authenticity"
```

**Process a full paper edit from file:**
```bash
sheetscut interview.json -i producer_selects.txt -o rough_cut.xml --continuous
```

**Use with 23.976 footage:**
```bash
sheetscut interview.json -i selects.txt --framerate 23.976
```

**Strict matching only:**
```bash
sheetscut interview.json -i selects.txt --no-fuzzy
```

## Limitations

- Requires word-level JSON transcripts (segment-level formats won't work)
- Generated XML uses filenames only, not full paths — Premiere will prompt to relink media on import
- Marker colors are limited by FCP XML spec (Premiere shows all markers as olive)
- Cannot reference existing project items like multicam sequences

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

Created by Paul Escandon / [Media Pending, LLC](https://mediapending.net)
