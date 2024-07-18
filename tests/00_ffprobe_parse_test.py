from audiobook_split_ffmpeg import (
    ffprobe_read_chapters,
)


from .testdata import beep, beep_nochap


def test_file_with_chapters():
    chapters = ffprobe_read_chapters(beep['file'])
    assert chapters == beep['expected_chapters']


def test_file_without_chapters():
    chapters = ffprobe_read_chapters(beep_nochap['file'])
    assert chapters == beep_nochap['expected_chapters']
