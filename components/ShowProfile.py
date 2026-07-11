"""Show profiles: bundles of venue-wide operating constraints.

A profile caps the whole installation — master volume, master light
brightness, and which games are selectable — without touching how any
game plays. GameController toggles between the normal and quiet-hours
profiles when both NEXT_GAME and RESET are held; play.py builds the
quiet profile from its command-line flags so the festival can retune
it without a code change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ShowProfile:
    name: str
    # Multiplies every mixed sound at the output (JackMixer applies it
    # per JACK block, so already-playing sounds duck too)
    master_volume: float = 1.0
    # Multiplies every color on its way into a LightSystem
    master_brightness: float = 1.0
    # Game class names selectable under this profile; None means all.
    # Names not in the run's roster are simply absent (a dev run with a
    # subset of games is normal), but an empty intersection falls back
    # to the full roster rather than an unselectable installation.
    allowed_games: frozenset[str] | None = None


NORMAL_PROFILE = ShowProfile(name="normal")

# Defaults for the quiet-hours profile; play.py exposes each as a flag
DEFAULT_QUIET_VOLUME = 0.5
DEFAULT_QUIET_BRIGHTNESS = 0.65
DEFAULT_QUIET_GAMES = ("Music", "Simon")

QUIET_PROFILE = ShowProfile(
    name="quiet hours",
    master_volume=DEFAULT_QUIET_VOLUME,
    master_brightness=DEFAULT_QUIET_BRIGHTNESS,
    allowed_games=frozenset(DEFAULT_QUIET_GAMES),
)
