from datetime import datetime
from pathlib import Path

import pygame

from .playback import Playback
from .sequencer import (
    BARS,
    BPM,
    LANE_NAMES,
    STEP_COUNT,
    STEPS_PER_BAR,
    LoopRenderer,
    load_hits,
    write_wav,
)

WINDOW_SIZE = (1064, 470)
PANEL = pygame.Rect(34, 126, 996, 272)
TRANSPORT_BUTTON = pygame.Rect(778, 42, 112, 42)
SAVE_BUTTON = pygame.Rect(902, 42, 128, 42)
GRID_LEFT = 219
GRID_TOP = 206
CELL_WIDTH = 20
CELL_HEIGHT = 44
STEP_SPACING = 24
BAR_SPACING = 200
LANE_SPACING = 56

BACKGROUND = "#16191c"
PANEL_COLOR = "#202429"
SURFACE = "#2c3238"
BORDER = "#41484f"
TEXT = "#f4f1e9"
SECONDARY = "#b6bec7"
ACCENTS = ("#f3b27c", "#b4a5fa", "#9bddbc")
MUTED_ACCENTS = ("#987864", "#7b739d", "#688f7d")


def starter_pattern():
    groove = (
        ((0, 4), (0, 4, 7), (0, 3, 4), (0, 4)),
        ((2, 6), (2, 6), (2, 6), (2, 6, 7)),
        ((1, 3, 5, 7), (1, 3, 5), (1, 3, 5, 7), (1, 3, 4, 5)),
    )
    pattern = [[False] * STEP_COUNT for _ in LANE_NAMES]
    for lane, bars in zip(pattern, groove):
        for bar, hits in enumerate(bars):
            for step in hits:
                lane[bar * STEPS_PER_BAR + step] = True
    return pattern


def _cell_rect(lane, step):
    bar, column = divmod(step, STEPS_PER_BAR)
    return pygame.Rect(
        GRID_LEFT + bar * BAR_SPACING + column * STEP_SPACING,
        GRID_TOP + lane * LANE_SPACING,
        CELL_WIDTH,
        CELL_HEIGHT,
    )


def _mute_rect(lane):
    return pygame.Rect(137, GRID_TOP + lane * LANE_SPACING + 8, 64, 28)


class SequencerApp:
    def __init__(self, screen):
        self.screen = screen
        self.title_font = pygame.font.SysFont("segoeui,dejavusans,arial", 35, bold=True)
        self.label_font = pygame.font.SysFont("segoeui,dejavusans,arial", 17, bold=True)
        self.body_font = pygame.font.SysFont("segoeui,dejavusans,arial", 15)
        self.small_font = pygame.font.SysFont("segoeui,dejavusans,arial", 13)
        self.cells = [
            [_cell_rect(lane, step) for step in range(STEP_COUNT)]
            for lane in range(len(LANE_NAMES))
        ]
        self.mute_buttons = [_mute_rect(lane) for lane in range(len(LANE_NAMES))]
        self.pattern = starter_pattern()
        self.muted = [False] * len(LANE_NAMES)
        self.renderer = LoopRenderer(load_hits())
        self.pcm = self.renderer.render(self.pattern, self.muted)
        self.status = "Click a step to toggle a hit."
        self.status_color = SECONDARY
        self.playback = None
        self.playing = False
        self.active_step = None
        try:
            self.playback = Playback()
        except pygame.error:
            self._audio_unavailable()
        else:
            self.toggle_transport()

    def _audio_unavailable(self):
        self.close()
        self.playing = False
        self.active_step = None
        self.status = "Audio unavailable. You can still edit and save a WAV."
        self.status_color = ACCENTS[0]

    def close(self):
        if self.playback is not None:
            self.playback.close()
            self.playback = None

    def toggle_transport(self):
        if self.playback is None:
            return
        try:
            if self.playing:
                self.playback.stop()
                self.active_step = None
            else:
                self.playback.start(self.pcm)
            self.playing = not self.playing
        except pygame.error:
            self._audio_unavailable()

    def update(self):
        if self.playing:
            try:
                self.active_step = self.playback.tick(self.pcm)
            except pygame.error:
                self._audio_unavailable()

    def _save(self):
        name = f"four-bar-overdub-{datetime.now():%Y%m%d-%H%M%S-%f}.wav"
        path = Path("exports") / name
        try:
            path.parent.mkdir(exist_ok=True)
            write_wav(path, self.pcm)
        except OSError as error:
            self.status = f"Could not save WAV. {error.strerror or error}"
            self.status_color = ACCENTS[0]
        else:
            self.status = f"Saved {path.as_posix()}"
            self.status_color = ACCENTS[2]

    def _click(self, position):
        if TRANSPORT_BUTTON.collidepoint(position):
            self.toggle_transport()
            return
        if SAVE_BUTTON.collidepoint(position):
            self._save()
            return
        for lane, mute_button in enumerate(self.mute_buttons):
            if mute_button.collidepoint(position):
                self.muted[lane] = not self.muted[lane]
                self.pcm = self.renderer.render(self.pattern, self.muted)
                return
            for step, cell in enumerate(self.cells[lane]):
                if cell.collidepoint(position):
                    self.pattern[lane][step] = not self.pattern[lane][step]
                    self.pcm = self.renderer.render(self.pattern, self.muted)
                    return

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.toggle_transport()
            elif event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
                self._save()

    def _text(self, value, font, color=TEXT, **anchor):
        text = font.render(value, True, color)
        self.screen.blit(text, text.get_rect(**anchor))

    def _button(self, rect, label, mouse, *, accent=None, disabled=False):
        hovered = rect.collidepoint(mouse) and not disabled
        fill = accent or ("#3a424a" if hovered else SURFACE)
        outline = TEXT if hovered else BORDER
        text_color = BACKGROUND if accent else SECONDARY if disabled else TEXT
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, outline, rect, width=1, border_radius=8)
        self._text(label, self.body_font, text_color, center=rect.center)

    def _draw_grid(self, mouse):
        pygame.draw.rect(self.screen, PANEL_COLOR, PANEL, border_radius=14)
        pygame.draw.rect(self.screen, BORDER, PANEL, width=1, border_radius=14)
        for bar in range(BARS):
            first_step = bar * STEPS_PER_BAR
            left = self.cells[0][first_step].left
            last_step = first_step + STEPS_PER_BAR - 1
            right = self.cells[0][last_step].right
            bar_rect = pygame.Rect(left - 5, 171, right - left + 10, 204)
            pygame.draw.rect(self.screen, BACKGROUND, bar_rect, border_radius=8)
            self._text(f"Bar {bar + 1}", self.label_font, topleft=(left, 143))
        if self.active_step is not None:
            x = self.cells[0][self.active_step].left
            playhead = pygame.Rect(x - 1, 174, CELL_WIDTH + 2, 194)
            pygame.draw.rect(self.screen, "#394a43", playhead, border_radius=6)
        for step, rect in enumerate(self.cells[0]):
            color = ACCENTS[2] if step == self.active_step else SECONDARY
            number = str(step % STEPS_PER_BAR + 1)
            self._text(number, self.small_font, color, center=(rect.centerx, 187))
        for lane, name in enumerate(LANE_NAMES):
            y = self.cells[lane][0].centery
            accent = MUTED_ACCENTS[lane] if self.muted[lane] else ACCENTS[lane]
            pygame.draw.circle(self.screen, accent, (56, y), 4)
            self._text(name, self.label_font, midleft=(69, y))
            mute_label = "Muted" if self.muted[lane] else "Mute"
            self._button(
                self.mute_buttons[lane],
                mute_label,
                mouse,
                accent=ACCENTS[lane] if self.muted[lane] else None,
            )
            for step, rect in enumerate(self.cells[lane]):
                on = self.pattern[lane][step]
                fill = accent if on and not self.muted[lane] else SURFACE
                pygame.draw.rect(self.screen, fill, rect, border_radius=5)
                if rect.collidepoint(mouse) or step == self.active_step:
                    pygame.draw.rect(self.screen, TEXT, rect, width=1, border_radius=5)
                if on:
                    mark = BACKGROUND if not self.muted[lane] else accent
                    pygame.draw.circle(self.screen, mark, rect.center, 3)

    def draw(self):
        mouse = pygame.mouse.get_pos()
        self.screen.fill(BACKGROUND)
        self._text("Four-Bar Overdub", self.title_font, topleft=(34, 32))
        timing = f"{BPM} BPM  ·  {BARS} bars  ·  {STEPS_PER_BAR} steps per bar"
        self._text(timing, self.body_font, SECONDARY, topleft=(36, 80))
        transport = "Stop" if self.playing else "Play"
        if self.playback is None:
            transport = "Audio offline"
        self._button(TRANSPORT_BUTTON, transport, mouse, disabled=self.playback is None)
        self._button(SAVE_BUTTON, "Save WAV", mouse, accent=ACCENTS[2])
        self._draw_grid(mouse)
        self.screen.set_clip(pygame.Rect(36, 410, 674, 40))
        self._text(self.status, self.body_font, self.status_color, topleft=(36, 421))
        self.screen.set_clip(None)
        self._text(
            "Space  Play / Stop      Ctrl+S  Save WAV",
            self.small_font,
            SECONDARY,
            topright=(1030, 423),
        )
        pygame.display.flip()


def main():
    pygame.display.init()
    pygame.font.init()
    app = None
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Four-Bar Overdub")
        app = SequencerApp(screen)
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                app.handle_event(event)
            if running:
                app.update()
                app.draw()
                clock.tick(60)
    finally:
        if app is not None:
            app.close()
        pygame.quit()
