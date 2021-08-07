# audiobook-split-ffmpeg

Split audiobook file into per-chapter files using chapter metadata and ffmpeg.

**NOTE**: Works only if the input file has chapter metadata (see example below)

# Usage

See the help:

    $ python3 audiobook-split-ffmpeg.py -h

In the simplest case you can just call

    $ python3 audiobook-split-ffmpeg.py --infile /path/to/audio.m4b

By default, the chapter files will be written into a temporary directory under
`/tmp`. You may specify alternative output directory with `--outdir <path>`,
which will be created if it does not exist. Note that this script will never
overwrite files, so you must delete conflicting files manually (or specify some
other empty/nonexistent directory)

The chapter titles will be included in the filenames if they are available in
the chapter metadata. You may prevent this behaviour with flag `--no-use-title-as-filename`,
in which case the filenames will include the input file basename instead (this
is useful is your metadata is crappy or malformed, for example).

# Dependencies:

- Python 3.5 or newer
- Obviously you need ffmpeg (and ffprobe) installed.

There are no 3rd party library dependencies. Everything is accomplished with just the python3 stdlib.

# Features

Uses chapter metadata to decide at which timestamps to split the file.
Obviously this script will only be able to split files with such metadata
included. Chapter metadata should be visible from `ffprobe <file>` output. If
not, this script will be useless. Example metadata is the form:

    Chapter #0:0: start 0.000000, end 1079.000000
    Metadata:
      title           : Chapter Zero
    Chapter #0:1: start 1079.000000, end 2040.000000
    Metadata:
      title           : Chapter One
    Chapter #0:2: start 2040.000000, end 2878.000000
    Metadata:
      title           : Chapter Two
    Chapter #0:3: start 2878.000000, end 3506.000000

This script will instruct ffmpeg to write metadata in the resulting chapter files, including:
- `track`: the chapter number; in the format X/Y, where X = chapter number, Y = total num of chapters.
- `title`: the chapter title, as-is (if available)

The chapter numbers are included in the output file names, padded with zeroes so that all
numbers are of equal length. This makes the files much easier to sort by name.

Work is done in parallel with the help of a thread pool. You may specify
how many parallel jobs you want with command line param `--concurrency`,
The default concurrency is equal to the number of cores available (although I think this
might be silly since this kind of processing isn't so much cpu-bound as it is IO-bound).

