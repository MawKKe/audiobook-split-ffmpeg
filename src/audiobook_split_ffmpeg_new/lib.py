import json
import subprocess
from pathlib import Path
import typing as t

from . import model


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

    return proc.stdout.decode(encoding or 'utf-8')


def parse_chapter_dict(chap: t.Dict[str, t.Any]) -> model.Chapter:
    have_chap_keys = set(chap.keys())

    if missing := (model.EXPECTED_CHAPTER_KEYS - have_chap_keys):
        raise FFProbeError(
            f'Expected chapter to have keys {model.EXPECTED_CHAPTER_KEYS}, got {have_chap_keys} (missing: {missing})'
        )

    start = float(chap['start_time'])
    end = float(chap['end_time'])

    if (end - start) <= 0:
        # extra validation for just in case
        raise FFProbeError(f'Invalid start..end time range in {chap}')

    return model.Chapter(
        id=int(chap['id']),
        start_time=str(chap['start_time']),
        end_time=str(chap['end_time']),
        tags=chap.get('tags', {}),
    )


def parse_metadata(content: str) -> model.Metadata:
    data = json.loads(content)

    chapters = []
    if 'chapters' in data.keys():
        chapters = [parse_chapter_dict(entry) for entry in data['chapters']]

    return model.Metadata(chapters)


def read_fileinfo(infile: Path, metadata_encoding: t.Optional[str] = None) -> model.FileInfo:
    meta_content = ffprobe(infile, encoding=metadata_encoding)
    return model.FileInfo(Path(infile), parse_metadata(meta_content))


def num_format_padded(num: int, padded_width: int) -> str:
    """
    >>> num_format_padded(123, 4)
    '0123'
    """
    return '{num:{fill}{width}}'.format(num=num, fill='0', width=padded_width)


def make_ffmpeg_split_cmd(
    info: model.FileInfo, ch: model.Chapter, outdir: Path, opts: model.Options
) -> t.List[str]:
    base_cmd = [
        'ffmpeg',
        '-nostdin',
        '-i',
        str(info.path),
        '-v',
        'error',
        '-map_chapters',
        '-1',
        '-vn',
        '-c',
        'copy',
        '-ss',
        str(ch.start_time),
        '-to',
        str(ch.end_time),
        ('-y' if opts.allow_overwriting_files else '-n'),
    ]

    ch_num = ch.id + opts.track_enumeration_offset
    ch_num_max = info.meta.max_chapter_num() + opts.track_enumeration_offset

    chapter_num_padded = num_format_padded(ch_num, padded_width=len(str(ch_num_max)))

    title = ch.title()

    def get_outfile_stem() -> str:
        if title and opts.use_title_in_name:
            return title
        return info.path.stem

    def metadata_track() -> t.List[str]:
        if not opts.use_track_num_in_meta:
            return []
        return ['-metadata', 'track={}/{}'.format(ch_num, ch_num_max)]

    def metadata_title() -> t.List[str]:
        if not (title and opts.use_title_in_meta):
            return []
        return ['-metadata', 'title={}'.format(title)]

    outfile_name = f'{chapter_num_padded} - {get_outfile_stem()}'
    outfile_path = (outdir / outfile_name).with_suffix(info.path.suffix)

    return base_cmd + metadata_title() + metadata_track() + [str(outfile_path)]


if __name__ == '__main__':
    import sys
    import shlex

    infile = sys.argv[1]
    encoding = sys.argv[2] if len(sys.argv) > 2 else None
    raw = ffprobe(Path(infile), encoding)
    print('>>> Raw ffprobe output and parsed chapters and commands')
    print(raw)
    print()

    file_info = read_fileinfo(Path(infile), encoding)

    opts = model.Options()
    for ch in file_info.meta.chapters:
        print(ch)
        cmd = make_ffmpeg_split_cmd(file_info, ch, Path('out'), opts)
        print()
        print(shlex.join(cmd))
        print('-' * 10)
