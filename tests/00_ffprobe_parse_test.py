import json
from pathlib import Path

from audiobook_split_ffmpeg import (
    ffprobe_read_chapters,
    ffprobe,
)

from audiobook_split_ffmpeg.model import Chapter

from .testdata import beep, beep_nochap


def test_file_with_chapters():
    chapters = ffprobe_read_chapters(beep['file'])
    assert chapters == beep['expected_chapters']


def test_file_without_chapters():
    chapters = ffprobe_read_chapters(beep_nochap['file'])
    assert chapters == beep_nochap['expected_chapters']


_raw_ffprobe_metadata_json = """
{
    "chapters": [
        {
            "id": 0,
            "time_base": "1/1000",
            "start": 0,
            "start_time": "0.000000",
            "end": 20000,
            "end_time": "20.000000",
            "tags": {
                "title": "It All Started With a Simple BEEP"
            }
        },
        {
            "id": 1,
            "time_base": "1/1000",
            "start": 20000,
            "start_time": "20.000000",
            "end": 40000,
            "end_time": "40.000000",
            "tags": {
                "title": "All You Can BEEP Buffee"
            }
        },
        {
            "id": 2,
            "time_base": "1/1000",
            "start": 40000,
            "start_time": "40.000000",
            "end": 60000,
            "end_time": "60.000000",
            "tags": {
                "title": "The Final Beep"
            }
        }
    ]
}
"""

here = Path(__file__).resolve().parent


def test_ffprobe():
    content = ffprobe.ffprobe(here / 'beep.m4a')
    assert len(content) > 0
    res = json.loads(content)
    assert isinstance(res, dict)


def test_parse_metadata():
    meta = ffprobe.parse_metadata(_raw_ffprobe_metadata_json)
    assert len(meta.chapters) == 3
    expect_chapters = [
        ffprobe.Chapter(
            id=0,
            start=0,
            start_time='0.000000',
            end=20000,
            end_time='20.000000',
            time_base=(1, 1000),
            tags={'title': 'It All Started With a Simple BEEP'},
        ),
        ffprobe.Chapter(
            id=1,
            start=20000,
            start_time='20.000000',
            end=40000,
            end_time='40.000000',
            time_base=(1, 1000),
            tags={'title': 'All You Can BEEP Buffee'},
        ),
        ffprobe.Chapter(
            id=2,
            start=40000,
            start_time='40.000000',
            end=60000,
            end_time='60.000000',
            time_base=(1, 1000),
            tags={'title': 'The Final Beep'},
        ),
    ]
    assert meta.chapters == expect_chapters


import pytest


def test_parse_metadata_should_not_crash_when_chapters_are_missing():
    meta1 = ffprobe.parse_metadata('{}')  # ok
    assert len(meta1.chapters) == 0
    meta2 = ffprobe.parse_metadata('{"chapters": []}')
    assert len(meta2.chapters) == 0


def test_parse_metadata_raises_when_unexpected_or_incomplete_chapter_entry_encountered():
    with pytest.raises(ffprobe.FFProbeError):
        _ = ffprobe.parse_metadata('{"chapters": [{"id": 0, "rest-are-missing": true}]}')


def test_read_fileinfo():
    info = ffprobe.read_fileinfo(here / 'beep.m4a')
    assert len(info.meta.chapters) == 3
    assert info.path == here / 'beep.m4a'
