import subprocess
from pathlib import Path


def test_that_chaptered_file_produces_three_files(tmpdir):
    proc = subprocess.run(
        [
            'audiobook-split-ffmpeg-ng',
            '--infile',
            'tests/beep.m4a',
            '--outdir',
            str(tmpdir),
        ]
    )

    assert proc.returncode == 0

    new_files = list(Path(tmpdir).glob('*.m4a'))

    assert len(new_files) == 3


def test_that_chapterless_file_produces_no_files(tmpdir):
    proc = subprocess.run(
        [
            'audiobook-split-ffmpeg-ng',
            '--infile',
            'tests/beep-nochap.m4a',
            '--outdir',
            str(tmpdir),
        ]
    )

    assert proc.returncode != 0

    new_files = list(Path(tmpdir).glob('*.m4a'))

    assert len(new_files) == 0
