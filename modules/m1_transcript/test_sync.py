import pytest

from modules.m1_transcript.sync import SpeakerSegment, TranscriptSync, Word, from_elevenlabs

# s1: Hello [0.0, 0.5) there [0.5, 1.0)   gap   s2: Hi [1.4, 1.8)  gap  friend [2.0, 2.6)   gap   s1: So [3.0, 3.3)
WORDS = [
    Word("Hello", 0.0, 0.5, "s1"),
    Word("there", 0.5, 1.0, "s1"),
    Word("Hi", 1.4, 1.8, "s2"),
    Word("friend", 2.0, 2.6, "s2"),
    Word("So", 3.0, 3.3, "s1"),
]

# Crosstalk: s1 says a long "Wait" while s2 starts and stops.
OVERLAPPING = [
    Word("Wait", 0.0, 2.0, "s1"),
    Word("yes", 0.5, 1.0, "s2"),
    Word("ok", 1.5, 2.5, "s2"),
    Word("right", 3.0, 3.5, "s1"),
]


@pytest.fixture
def sync():
    return TranscriptSync(WORDS)


@pytest.mark.parametrize(
    "t, expected",
    [
        (-0.1, None),      # before first word
        (0.0, "Hello"),    # exactly at start
        (0.25, "Hello"),   # mid-word
        (0.5, "there"),    # end of one word == start of next -> next
        (0.99, "there"),
        (1.0, None),       # exactly at end, then a gap
        (1.2, None),       # gap
        (1.4, "Hi"),
        (1.9, None),       # gap between same-speaker words
        (2.0, "friend"),
        (3.29, "So"),
        (3.3, None),       # transcript end
        (10.0, None),      # after last word
    ],
)
def test_active_word(sync, t, expected):
    word = sync.active_word(t)
    assert (word.text if word else None) == expected


@pytest.mark.parametrize(
    "t, expected",
    [
        (-0.1, None),   # before first word
        (0.25, "s1"),
        (1.2, "s1"),    # gap: holds previous speaker
        (1.4, "s2"),
        (1.9, "s2"),    # gap between same-speaker words
        (2.8, "s2"),    # holds until s1 starts
        (3.0, "s1"),
        (3.3, None),    # transcript end
        (10.0, None),
    ],
)
def test_active_speaker(sync, t, expected):
    assert sync.active_speaker(t) == expected


@pytest.mark.parametrize(
    "t, word, speaker",
    [
        (0.7, "yes", "s2"),    # most recently started word wins
        (1.2, "Wait", "s1"),   # "yes" ended; "Wait" still in progress
        (1.6, "ok", "s2"),
        (2.2, "ok", "s2"),     # "Wait" ended
        (2.7, None, "s2"),     # gap: s2 spoke last
        (3.2, "right", "s1"),
        (3.5, None, None),     # transcript end
    ],
)
def test_overlapping_words(t, word, speaker):
    sync = TranscriptSync(OVERLAPPING)
    active = sync.active_word(t)
    assert (active.text if active else None) == word
    assert sync.active_speaker(t) == speaker


def test_unsorted_input_matches_sorted():
    sorted_sync = TranscriptSync(WORDS)
    shuffled_sync = TranscriptSync(list(reversed(WORDS)))
    for t in [-0.1, 0.0, 0.5, 1.2, 1.4, 2.8, 3.0, 3.3]:
        assert shuffled_sync.active_word(t) == sorted_sync.active_word(t)
        assert shuffled_sync.active_speaker(t) == sorted_sync.active_speaker(t)


def test_empty_transcript():
    sync = TranscriptSync([])
    assert sync.active_word(0.0) is None
    assert sync.active_speaker(0.0) is None
    assert sync.speaker_segments == ()


def test_single_word():
    sync = TranscriptSync([Word("Hey", 1.0, 2.0, "s1")])
    assert sync.active_word(0.5) is None
    assert sync.active_word(1.5).text == "Hey"
    assert sync.active_speaker(1.5) == "s1"
    assert sync.active_speaker(2.0) is None


def test_zero_length_word_is_never_active():
    sync = TranscriptSync([Word("uh", 1.0, 1.0, "s1")])
    assert sync.active_word(1.0) is None


def test_speaker_segments(sync):
    assert sync.speaker_segments == (
        SpeakerSegment("s1", 0.0, 1.0),
        SpeakerSegment("s2", 1.4, 2.6),
        SpeakerSegment("s1", 3.0, 3.3),
    )


def test_from_elevenlabs_keeps_only_words():
    payload = {
        "words": [
            {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": " ", "start": 0.5, "end": 0.6, "type": "spacing", "speaker_id": "speaker_0"},
            {"text": "(laughs)", "start": 0.6, "end": 1.0, "type": "audio_event"},
            {"text": "there", "start": 1.0, "end": 1.4, "type": "word"},
        ]
    }
    assert from_elevenlabs(payload) == [
        Word("Hello", 0.0, 0.5, "speaker_0"),
        Word("there", 1.0, 1.4, None),   # no diarization -> no speaker
    ]


@pytest.mark.parametrize(
    "word",
    [
        Word("bad", -0.1, 0.5),   # negative start
        Word("bad", 1.0, 0.5),    # end before start
    ],
)
def test_invalid_word_raises(word):
    with pytest.raises(ValueError):
        TranscriptSync([word])
