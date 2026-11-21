from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import wave

from four_bar_overdub.sequencer import LoopRenderer, load_hits, write_wav


class SequencerTests(unittest.TestCase):
    def test_impulse_on_final_step_lands_at_exact_sample(self):
        renderer = LoopRenderer(((4_000,), (0,), (0,)))
        pattern = [[False] * 32 for _ in range(3)]
        pattern[0][31] = True

        pcm = renderer.render(pattern, (False, False, False))

        expected = bytearray(368_640 * 2)
        struct.pack_into("<h", expected, 357_120 * 2, 1_000)
        self.assertEqual(pcm, expected)

    def test_all_muted_wav_contains_exactly_four_bars_of_silence(self):
        renderer = LoopRenderer(load_hits())
        pcm = renderer.render([[True] * 32 for _ in range(3)], (True, True, True))

        with TemporaryDirectory() as folder:
            path = Path(folder) / "silent.wav"
            write_wav(path, pcm)
            with wave.open(str(path), "rb") as exported:
                self.assertEqual(exported.getparams(), (1, 2, 48_000, 368_640, "NONE", "not compressed"))
                self.assertEqual(exported.readframes(368_641), bytes(368_640 * 2))

    def test_coincident_hits_keep_headroom_and_fixed_lane_gain(self):
        renderer = LoopRenderer(((32_767, -32_768),) * 3)
        pattern = [[True] + [False] * 31 for _ in range(3)]

        unmuted = renderer.render(pattern, (False, False, False))
        solo = renderer.render(pattern, (False, True, True))

        self.assertEqual(struct.unpack_from("<hh", unmuted), (24_575, -24_576))
        self.assertEqual(struct.unpack_from("<hh", solo), (8_192, -8_192))
