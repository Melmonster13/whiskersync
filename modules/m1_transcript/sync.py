"""Active word / speaker lookup for a transcript player, using bisect on word start times.

Rules:
1. A word is active on the half-open interval [start, end).
2. Overlapping words (crosstalk): the active word is the most recently started one still in progress.
3. Gaps: no active word, but the speaker holds as whoever spoke last, until the next word starts.
   Before the first word and after the transcript ends, there is no speaker.
"""

from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    speaker_id: str | None = None


@dataclass(frozen=True)
class SpeakerSegment:
    speaker_id: str | None
    start: float
    end: float


def from_elevenlabs(payload: dict) -> list[Word]:
    """Words from an ElevenLabs speech-to-text response; drops spacing and audio events."""
    return [
        Word(w["text"], w["start"], w["end"], w.get("speaker_id"))
        for w in payload["words"]
        if w.get("type", "word") == "word"
    ]


class TranscriptSync:
    def __init__(self, words: list[Word]):
        for w in words:
            if w.start < 0 or w.end < w.start:
                raise ValueError(f"invalid word timing: {w}")
        self._words = sorted(words, key=lambda w: w.start)
        self._starts = [w.start for w in self._words]

        # _latest_end[i]: index of the word with the latest end among words[0..i].
        # Ties go to the later word, i.e. the more recent speaker.
        self._latest_end: list[int] = []
        for i, w in enumerate(self._words):
            if i == 0 or w.end >= self._words[self._latest_end[-1]].end:
                self._latest_end.append(i)
            else:
                self._latest_end.append(self._latest_end[-1])

        self.speaker_segments = self._build_segments()

    def _build_segments(self) -> tuple[SpeakerSegment, ...]:
        segments: list[SpeakerSegment] = []
        for w in self._words:
            if segments and segments[-1].speaker_id == w.speaker_id:
                last = segments[-1]
                segments[-1] = SpeakerSegment(last.speaker_id, last.start, max(last.end, w.end))
            else:
                segments.append(SpeakerSegment(w.speaker_id, w.start, w.end))
        return tuple(segments)

    def _active_index(self, t: float) -> int | None:
        i = bisect_right(self._starts, t) - 1
        # Walk back past words that already ended; stop once nothing earlier ends after t.
        while i >= 0:
            if t < self._words[i].end:
                return i
            if i == 0 or self._words[self._latest_end[i - 1]].end <= t:
                return None
            i -= 1
        return None

    def active_word(self, t: float) -> Word | None:
        i = self._active_index(t)
        return None if i is None else self._words[i]

    def active_speaker(self, t: float) -> str | None:
        i = bisect_right(self._starts, t) - 1
        if i < 0:
            return None
        active = self._active_index(t)
        if active is not None:
            return self._words[active].speaker_id
        last = self._words[self._latest_end[i]]
        if t >= self._words[self._latest_end[-1]].end:
            return None
        return last.speaker_id
