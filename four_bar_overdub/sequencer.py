"""Render and export the sequencer's shared mono PCM buffer."""

from array import array
from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys
import wave


BPM = 125
BARS = 4
STEPS_PER_BAR = 8
STEP_COUNT = BARS * STEPS_PER_BAR
SAMPLE_RATE = 48_000
STEP_FRAMES = SAMPLE_RATE * 60 // (BPM * 2)
LOOP_FRAMES = STEP_COUNT * STEP_FRAMES
SAMPLE_WIDTH = 2
LANE_NAMES = ("Kick", "Snare", "Hi-hat")
LANE_COUNT = len(LANE_NAMES)
_ASSETS = Path(__file__).with_name("assets")
_HIT_FILES = ("kick.wav", "snare.wav", "hi_hat.wav")


def load_hits() -> tuple[array, ...]:
    """Read the three bundled percussion hits in lane order."""
    hits = []
    for filename in _HIT_FILES:
        with wave.open(str(_ASSETS / filename), "rb") as source:
            audio_format = (source.getnchannels(), source.getsampwidth(), source.getframerate())
            if audio_format != (1, SAMPLE_WIDTH, SAMPLE_RATE):
                raise ValueError(f"{filename} must be mono PCM16 at {SAMPLE_RATE} Hz")

            frame_count = source.getnframes()
            if not 0 < frame_count <= STEP_FRAMES:
                raise ValueError(f"{filename} must fit within one step")

            samples = array("h")
            samples.frombytes(source.readframes(frame_count))
            if len(samples) != frame_count:
                raise ValueError(f"{filename} has incomplete sample data")
            hits.append(samples)
    return tuple(hits)


class LoopRenderer:
    """Mix the three hits, then assemble any pattern from the eight step mixes."""

    def __init__(self, hits: Sequence[Sequence[int]]) -> None:
        if len(hits) != LANE_COUNT or any(not 0 < len(hit) <= STEP_FRAMES for hit in hits):
            raise ValueError("Expected three hits, each between one sample and one step long")
        if any(not -32_768 <= sample <= 32_767 for hit in hits for sample in hit):
            raise ValueError("Hit samples must be signed 16-bit values")

        step_mixes = []
        for mask in range(1 << LANE_COUNT):
            accumulator = [0] * STEP_FRAMES
            for lane, hit in enumerate(hits):
                if mask & (1 << lane):
                    for frame, sample in enumerate(hit):
                        accumulator[frame] += sample

            # A fixed quarter gain leaves headroom even when all three hits coincide.
            samples = array("h", (round(sample / 4) for sample in accumulator))
            if sys.byteorder == "big":
                samples.byteswap()
            step_mixes.append(samples.tobytes())
        self._step_mixes = tuple(step_mixes)

    def render(self, pattern: Sequence[Sequence[bool]], muted: Sequence[bool]) -> bytes:
        """Return one complete loop as little-endian PCM16."""
        if len(pattern) != LANE_COUNT or any(len(row) != STEP_COUNT for row in pattern):
            raise ValueError(f"Expected a {LANE_COUNT} by {STEP_COUNT} pattern")
        if len(muted) != LANE_COUNT:
            raise ValueError("Expected one mute flag per lane")

        lane_bits = [0 if is_muted else 1 << lane for lane, is_muted in enumerate(muted)]
        return b"".join(
            self._step_mixes[sum(bit for bit, row in zip(lane_bits, pattern) if row[step])]
            for step in range(STEP_COUNT)
        )


def write_wav(path: str | Path, pcm: bytes) -> None:
    """Write one full loop to a WAV file without opening an audio device."""
    if len(pcm) != LOOP_FRAMES * SAMPLE_WIDTH:
        raise ValueError("WAV export requires exactly four bars of PCM")

    # wave.writeframes accepts native-endian samples and encodes a little-endian WAV.
    if sys.byteorder == "big":
        samples = array("h")
        samples.frombytes(pcm)
        samples.byteswap()
        pcm = samples.tobytes()

    destination = Path(path)
    temporary = NamedTemporaryFile(dir=destination.parent, delete=False)
    temporary_path = Path(temporary.name)
    try:
        with temporary, wave.open(temporary, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(SAMPLE_WIDTH)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(pcm)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
