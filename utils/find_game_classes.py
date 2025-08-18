import importlib.util
import inspect
import pathlib
import sys


def find_game_classes(base_dir: str, base_class_module: str = "bases", base_class_name: str = "BaseGame"):
    """Find all subclasses of base_class in the given directory."""

    base_dir_path = pathlib.Path(base_dir).resolve()

    # Load the base class the way game modules do: from bases import BaseGame
    base_module = importlib.import_module(base_class_module)
    base_class = getattr(base_module, base_class_name)

    classes = []

    for file in base_dir_path.glob("*.py"):
        if file.name.startswith("_"):
            continue  # skip __init__.py, _private.py, etc.

        module_name = f"{base_dir_path.name}.{file.stem}"  # e.g., games.Game1

        if module_name in sys.modules:
            mod = sys.modules[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, file)
            if spec is None or spec.loader is None:
                raise ValueError("Neither spec nor spec.loader should not be None")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(cls, base_class)
                and cls is not base_class
                and cls.__module__ == module_name
                and not getattr(cls, "PROXY", False)
            ):
                classes.append(cls)

    return classes
