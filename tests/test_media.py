"""Tests for media spells."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path


class _TemporaryDirectory:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> str:
        return str(self.path)

    def __exit__(self, *args: object) -> None:
        return None


class _Context:
    def __init__(self, temp_dir: Path) -> None:
        self.commands: list[str] = []
        self.config = SimpleNamespace(run=SimpleNamespace(dry=False))
        self.temp_dir = temp_dir

    def run(self, command: str) -> None:
        self.commands.append(command)
        if command.startswith("whisper "):
            (self.temp_dir / "audio.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")


def test_video_to_srt_extracts_audio_and_moves_subtitle(tmp_path: Path) -> None:
    from conjuring.spells.media import video_to_srt

    video = tmp_path / "my video.mp4"
    video.touch()
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    c = _Context(temp_dir)

    with patch("conjuring.spells.media.tempfile.TemporaryDirectory", return_value=_TemporaryDirectory(temp_dir)):
        video_to_srt.body(c, video, language="en", model="small")

    subtitle = video.with_suffix(".srt")
    assert subtitle.read_text() == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert c.commands == [
        f"ffmpeg -nostdin -i '{video}' -vn -ac 1 -ar 16000 -c:a pcm_s16le {temp_dir / 'audio.wav'}",
        f"whisper {temp_dir / 'audio.wav'} --model small --language en --output_dir {temp_dir} --output_format srt",
    ]


def test_video_to_srt_does_not_replace_existing_subtitle(tmp_path: Path) -> None:
    from conjuring.spells.media import video_to_srt

    video = tmp_path / "video.mp4"
    subtitle = video.with_suffix(".srt")
    video.touch()
    subtitle.write_text("existing")
    c = _Context(tmp_path)

    video_to_srt.body(c, video)

    assert subtitle.read_text() == "existing"
    assert c.commands == []
