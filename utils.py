import importlib.util
import inspect
import pathlib
import sys
from math import fmod
from typing import Any

from constants import ColorType


def cycle(cycle_source: list[Any]):
    if len(cycle_source) < 2:
        raise ValueError("Need at least two elements to cycle through")
    idx = 0
    while True:
        yield cycle_source[idx]
        idx += 1
        if idx >= len(cycle_source):
            idx = 0


def is_normalized(f: float) -> bool:
    return 0.0 <= f <= 1.0


def hsv_to_rgb(hue: float, sat: float, val:float) -> ColorType:
    """Convert normalized hue, saturation, and value to their red, green, blue representation"""
    if not all(map(is_normalized, (hue, sat, val))):
        raise ValueError("all hsv values need to be between [0.0-1.0] h,s,v=", hue, sat, val)

    chroma = sat * val
    x = chroma * (1.0 - abs(fmod(hue * 6, 2) - 1.0))
    step = 1.0/6.0
    if 0 <= hue < step:
        r1 = chroma
        g1 = x
        b1 = 0
    elif 1.0 * step <= hue < 2.0 * step:
        r1 = x
        g1 = chroma
        b1 = 0
    elif 2.0 * step <= hue < 3.0 * step:
        r1 = 0
        g1 = chroma
        b1 = x
    elif 3.0 * step <= hue < 4.0 * step:
        r1 = 0
        g1 = x
        b1 = chroma
    elif 4.0 * step <= hue < 5.0 * step:
        r1 = x
        g1 = 0
        b1 = chroma
    elif 5.0 * step <= hue < 6.0 * step:
        r1 = chroma
        g1 = 0
        b1 = x
    else:
        raise ValueError(f"out of range hue={hue}")
    r = r1 + (val - chroma)
    g = g1 + (val - chroma)
    b = b1 + (val - chroma)
    return r, g, b


def find_game_classes(base_dir: str, base_class_name: str = "BaseGame"):
    """A function to load all classes derived from a certain base class. AI helped, I embellished, can't you tell?"""

    def get_base_class(path: str, class_name: str = "BaseGame"):
        """The class must be in a Python file of the same name, ex: BaseGame from BaseGame.py"""
        # Set base directory
        base_dir = pathlib.Path(path)

        # Load base class from file manually
        base_game_path = base_dir / f"{class_name}.py"
        spec = importlib.util.spec_from_file_location(class_name, base_game_path)
        base_module = importlib.util.module_from_spec(spec)
        sys.modules[class_name] = base_module
        spec.loader.exec_module(base_module)

        return getattr(base_module, class_name)

    base_class = get_base_class(base_dir, base_class_name)
    this_file = pathlib.Path(__file__).name
    base_dir = pathlib.Path(base_dir)
    classes = []

    for file in base_dir.glob("*.py"):
        if file.name == f"{base_class.__name__}.py":
            continue  # skip the base definition
        if file.name == this_file:
            continue  # skip this file
        module_name = file.stem  # e.g. "Game1" from "Game1.py"
        spec = importlib.util.spec_from_file_location(module_name, file)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(cls, base_class)
                and cls is not base_class
                and cls.__module__ == module_name
            ):
                classes.append(cls)

    return classes

def main():
    classes = find_game_classes(".")
    print("Found subclasses:", classes)
    d = {c.__name__: c for c in classes}
    print(d)


if __name__ == "__main__":
    main()
