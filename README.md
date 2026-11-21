# Four-Bar Overdub

Four-Bar Overdub is a desktop percussion sequencer. Place kick, snare, and hi-hat hits against one another in a four-bar loop, mute a lane to hear what it contributes, and save the groove as a WAV.

## Run

In Windows PowerShell, from the project folder with Python 3.13 installed:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m four_bar_overdub
```

The app starts playing a preset groove when audio is available. Click a step to toggle a hit. **Mute** silences a lane while keeping its hits in the grid. Press **Space** to stop or start from bar one. **Save WAV** or **Ctrl+S** writes the current mix to the `exports/` folder in the launch directory, even if the audio device is unavailable.

## Timing and mix

At 125 BPM in 4/4, each eighth-note step is 240 ms, or 11,520 samples at 48 kHz. Multiply the zero-based step index by 11,520 to find its starting sample. Each of the 32 steps contributes to one 7.68-second mono PCM16 buffer. Playback queues one step ahead, and edits take effect on the next step that has yet to be queued. WAV export writes the latest complete buffer.

The three bundled hits are original synthesized sounds with tails shorter than one step. Each plays at quarter gain, leaving at least 25% of full-scale amplitude as headroom when hits coincide.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests check the final-step impulse at sample 357,120, a four-bar all-muted WAV containing exactly 368,640 zero samples, and the peak with all three hits stacked. They can run without an audio device.
