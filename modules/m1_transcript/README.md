# m1 — Transcript word + speaker sync

**Problem:** a transcript player has to highlight the word being spoken and show who's speaking, on every playback tick, for transcripts with thousands of words and real-world messiness: pauses, crosstalk, and unsorted input. **Approach:** sort words once, then use `bisect` on start times to find the candidate word in O(log n); a precomputed "latest end so far" index handles overlapping words and gives the last speaker during pauses in O(1). `from_elevenlabs()` turns an ElevenLabs speech-to-text response into words, dropping spacing and audio events. **Result:** 37 table-driven tests cover boundaries, gaps, crosstalk, unsorted input, empty and degenerate transcripts, and ElevenLabs parsing.

## Usage

```python
from modules.m1_transcript.sync import TranscriptSync, from_elevenlabs

sync = TranscriptSync(from_elevenlabs(stt_response))
sync.active_word(12.34)        # Word(text=..., start=..., end=..., speaker_id=...) or None
sync.active_speaker(12.34)     # "speaker_0" or None
sync.speaker_segments          # (SpeakerSegment(speaker_id, start, end), ...)
```

## Rules

1. A word is active on `[start, end)`. At a shared boundary the next word wins, so two words are never active at once.
2. With overlapping words, the most recently started word that's still in progress wins.
3. In a pause there's no active word, but the speaker holds as whoever spoke last until the next word starts. Before the first word and after the transcript ends, there's no speaker.

## Edge cases

| Case | Behaviour | Test |
|---|---|---|
| Time before the first word | No word, no speaker | `test_active_word`, `test_active_speaker` |
| Exactly at a word's start | That word | `test_active_word` |
| End of one word == start of the next | The next word | `test_active_word` |
| Exactly at a word's end, followed by a gap | No word | `test_active_word` |
| Gap between words | No word; previous speaker holds | `test_active_word`, `test_active_speaker` |
| Gap before a different speaker | Previous speaker holds until the new one starts | `test_active_speaker` |
| At or after the transcript end | No word, no speaker | `test_active_word`, `test_active_speaker` |
| Short word nested inside a long one | Short word while it lasts, then the long word again | `test_overlapping_words` |
| Pause after crosstalk | Speaker of the word that ended last | `test_overlapping_words` |
| Unsorted input | Same results as sorted | `test_unsorted_input_matches_sorted` |
| Empty transcript | Everything `None`, no segments | `test_empty_transcript` |
| Single word | Active only inside it | `test_single_word` |
| Zero-length word | Never active | `test_zero_length_word_is_never_active` |
| Consecutive words by one speaker | Merged into one segment | `test_speaker_segments` |
| STT spacing / audio events | Dropped by `from_elevenlabs` | `test_from_elevenlabs_keeps_only_words` |
| No diarization (`speaker_id` missing) | `speaker_id=None` | `test_from_elevenlabs_keeps_only_words` |
| Negative start, or end before start | `ValueError` | `test_invalid_word_raises` |

**Known limit:** with heavy crosstalk, `active_word` walks back past every overlapping word that already ended, so the worst case is O(n). Normal speech overlaps rarely and briefly.

## Trade-offs

See `DECISIONS.md`: half-open intervals; speaker holds through pauses; overlaps allowed with most-recent-wins.

## Run

```bash
.venv/bin/pytest modules/m1_transcript
```
