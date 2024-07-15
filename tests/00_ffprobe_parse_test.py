import datetime

from audiobook_split_ffmpeg import (
    ffprobe_read_chapters,
)

from audiobook_split_ffmpeg import util

from .testdata import beep, beep_nochap


def test_file_with_chapters():
    chapters = ffprobe_read_chapters(beep['file'])
    assert chapters == beep['expected_chapters']


def test_file_without_chapters():
    chapters = ffprobe_read_chapters(beep_nochap['file'])
    assert chapters == beep_nochap['expected_chapters']

def test_parse_duration():
    res = util.parse_duration('12h34m56s')
    assert res is not None
    assert res == datetime.timedelta(hours=12, minutes=34, seconds=56)
