"""Loop transport for the rendered PCM buffer."""

import sys
from array import array
from collections import deque

import pygame

from .sequencer import SAMPLE_RATE, SAMPLE_WIDTH, STEP_COUNT, STEP_FRAMES


STEP_BYTES = STEP_FRAMES * SAMPLE_WIDTH
# One step spans exactly 45 mixer blocks, so handoffs land on block boundaries.
MIXER_BLOCK_FRAMES = 256


class Playback:
    def __init__(self) -> None:
        pygame.mixer.init(
            frequency=SAMPLE_RATE,
            size=-16,
            channels=1,
            buffer=MIXER_BLOCK_FRAMES,
            allowedchanges=0,
        )
        if pygame.mixer.get_init() != (SAMPLE_RATE, -16, 1):
            pygame.mixer.quit()
            raise pygame.error("Playback requires 48 kHz, 16-bit mono PCM")

        self._channel = pygame.mixer.Channel(0)
        self._running = False
        self._next_step = 0
        self._submitted: deque[tuple[int, pygame.mixer.Sound]] = deque(maxlen=2)

    def start(self, pcm: bytes) -> None:
        self._next_step = 0
        self._submitted.clear()
        self._channel.play(self._next_sound(pcm))
        self._channel.queue(self._next_sound(pcm))
        self._running = True

    def tick(self, pcm: bytes) -> int | None:
        if not self._running:
            return None

        queued = self._channel.get_queue()
        if queued is None:
            self._channel.queue(self._next_sound(pcm))
        elif self._channel.get_sound() is None:
            # If an underrun stranded a queued slice, resume with that slice.
            self._channel.play(queued)
            self._channel.queue(self._next_sound(pcm))

        active = self._channel.get_sound()
        for step, sound in self._submitted:
            if sound is active:
                return step
        return None

    def stop(self) -> None:
        self._running = False
        self._channel.stop()
        self._submitted.clear()

    def close(self) -> None:
        self.stop()
        pygame.mixer.quit()

    def _next_sound(self, pcm: bytes) -> pygame.mixer.Sound:
        step = self._next_step
        offset = step * STEP_BYTES
        step_pcm = pcm[offset : offset + STEP_BYTES]
        if sys.byteorder == "big":
            samples = array("h")
            samples.frombytes(step_pcm)
            samples.byteswap()
            step_pcm = samples.tobytes()

        sound = pygame.mixer.Sound(buffer=step_pcm)
        self._submitted.append((step, sound))
        self._next_step = (step + 1) % STEP_COUNT
        return sound
