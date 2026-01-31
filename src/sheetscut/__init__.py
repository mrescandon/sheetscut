"""
Sheetscut - Producer Paper Edit to Premiere Pro Sequence Generator

This package takes a producer's text selection (copied from a transcript)
and matches it against a word-level JSON transcript to generate a
Premiere Pro XML sequence.
"""

__version__ = "0.1.0"
__author__ = "Paul Escandon / Media Pending, LLC"

from .core import process_paper_edit
from .transcript import load_transcript, build_word_list
from .matcher import match_producer_text, normalize_text
from .xml_generator import generate_premiere_xml

__all__ = [
    '__version__',
    'process_paper_edit',
    'load_transcript',
    'build_word_list',
    'match_producer_text',
    'normalize_text',
    'generate_premiere_xml',
]
