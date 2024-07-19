from audiobook_split_ffmpeg import (
    compute_workitems,
)

from .testdata import beep


def test_compute_workitems():
    work_items = list(compute_workitems(beep['file'], 'foo'))
    assert len(work_items) == 3
    assert work_items == beep['expected_workitems']
