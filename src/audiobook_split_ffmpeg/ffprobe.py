import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
import typing as t


@dataclass
class Chapter:
    id: int
    start: int
    end: int
    start_time: str
    end_time: str
    time_base: t.Tuple[int, int]
    tags: t.Dict[str, str]

    def title(self) -> t.Optional[str]:
        return self.tags.get('title', None)


@dataclass
class Metadata:
    chapters: t.List[Chapter]

    def max_chapter_num(self) -> int:
        return max(ch.id for ch in self.chapters)


@dataclass
class FileInfo:
    path: Path
    meta: Metadata


class FFProbeError(Exception):
    pass


def ffprobe(infile: Path, encoding: t.Optional[str] = None) -> str:
    """
    Read metadata of 'infile' using ffprobe and return it as dictionary.

    The file metadata is assumed to be UTF-8 encoded; the default encoding
    can be overridden with the 'encoding' argument.
    """

    command = [
        'ffprobe',
        '-i',
        str(infile),
        '-v',
        'error',
        '-print_format',
        'json',
        '-show_chapters',
    ]

    # ffmpeg & ffprobe write output into stderr, except when
    # using -show_XXXX and -print_format. Strange.
    # Had we ran ffmpeg instead of ffprobe, this would throw since ffmpeg without
    # an output file will exit with exitcode != 0
    proc = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # .decode() will most likely explode if the ffprobe json output (chapter metadata)
    # was written with some weird encoding, and even more so if the data contains text in
    # multiple different text encodings...

    # TODO how does this handle non-ascii/utf8 metadata? # pylint: disable=fixme
    # https://stackoverflow.com/questions/10009753/python-dealing-with-mixed-encoding-files
    return proc.stdout.decode(encoding or 'utf-8')


EXPECT_CHAPTER_KEYS = {'id', 'start', 'start_time', 'end', 'end_time', 'time_base'}


def _parse_raw_chapter_dict(chap: t.Dict[str, t.Any]) -> Chapter:
    have_chap_keys = set(chap.keys())

    if missing := EXPECT_CHAPTER_KEYS - have_chap_keys:
        raise FFProbeError(
            f'Expected chapter to have keys {EXPECT_CHAPTER_KEYS}, got {have_chap_keys} (missing: {missing})'
        )

    def parse_timebase(base: str) -> t.Tuple[int, int]:
        a, b = base.split('/')
        return (int(a), int(b))

    return Chapter(
        id=int(chap['id']),
        start=int(chap['start']),
        start_time=str(chap['start_time']),
        end=int(chap['end']),
        end_time=str(chap['end_time']),
        time_base=parse_timebase(chap['time_base']),
        tags=chap.get('tags', {}),
    )


def parse_metadata(content: str) -> Metadata:
    data = json.loads(content)

    chapters = []
    if 'chapters' in data.keys():
        chapters = [_parse_raw_chapter_dict(entry) for entry in data['chapters']]

    return Metadata(chapters)


def read_fileinfo(infile: Path, metadata_encoding: t.Optional[str] = None) -> FileInfo:
    meta_content = ffprobe(infile, encoding=metadata_encoding)
    return FileInfo(Path(infile), parse_metadata(meta_content))


if __name__ == '__main__':
    import sys

    infile = sys.argv[1]
    encoding = sys.argv[2] if len(sys.argv) > 2 else None
    raw = ffprobe(Path(infile), encoding)
    print('Raw ffprobe output:')
    print(raw)
    print('-' * 10)
    file_info = read_fileinfo(Path(infile), encoding)
    print('Fully parsed chapters:')
    for chap in file_info.meta.chapters:
        print(chap)
