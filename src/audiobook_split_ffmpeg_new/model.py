import typing as t
from pathlib import Path
from dataclasses import dataclass, fields


@dataclass
class Chapter:
    id: int
    start_time: str
    end_time: str
    tags: t.Dict[str, str]

    def title(self) -> t.Optional[str]:
        return self.tags.get('title', None)


EXPECTED_CHAPTER_KEYS = set(field.name for field in fields(Chapter)) - {'tags'}


@dataclass
class Metadata:
    chapters: t.List[Chapter]

    def max_chapter_num(self) -> int:
        return max(ch.id for ch in self.chapters)


@dataclass
class FileInfo:
    path: Path
    meta: Metadata


@dataclass
class Options:
    use_title_in_name: bool = True
    use_title_in_meta: bool = True
    use_track_num_in_meta: bool = True
    track_enumeration_offset: int = 1
    allow_overwriting_files: bool = True
