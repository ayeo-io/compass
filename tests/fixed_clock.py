"""Run the Compass CLI with the date and time held fixed. Test support only.

    python3 tests/fixed_clock.py --cli <cli folder> --at <ISO instant> -- <compass arguments>

The CLI has no setting for the clock and gets none here: this runner sits
outside `cli/`, so it applies unchanged to a copy of older code. It puts the
given `cli` folder first on `sys.path` and installs an import hook. After
each `compass_pkg` module runs, the hook rebinds that module's `datetime`
module name, and any name bound to the `date` or `datetime` class, to
stand-ins whose `today()`, `now()` and `utcnow()` return the fixed instant.

Every value a stand-in builds or returns is a real `date` or `datetime`, and
`isinstance` against a stand-in behaves as against the real class. The
vendored `yaml` package and the real `datetime` module are not touched, so
the types the parser reads and the dumper writes do not change.

`TZ` is set to UTC, so a naive local time equals the fixed instant.
"""
from __future__ import annotations

import argparse
import datetime as _real_datetime_module
import importlib.abc
import os
import runpy
import sys
import time
import types

_REAL_DATE = _real_datetime_module.date
_REAL_DATETIME = _real_datetime_module.datetime
_UTC = _real_datetime_module.timezone.utc


def _parse_instant(text):
    instant = _REAL_DATETIME.fromisoformat(text.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=_UTC)
    return instant.astimezone(_UTC)


def make_stand_ins(instant):
    """Return (date stand-in, datetime stand-in, datetime module stand-in)."""

    class _Meta(type):
        def __call__(cls, *args, **kwargs):
            return cls._real(*args, **kwargs)

        def __getattr__(cls, name):
            return getattr(cls._real, name)

        def __instancecheck__(cls, obj):
            return isinstance(obj, cls._real)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, cls._real)

    class FixedDate(metaclass=_Meta):
        _real = _REAL_DATE

        @classmethod
        def today(cls):
            return instant.date()

    class FixedDatetime(metaclass=_Meta):
        _real = _REAL_DATETIME

        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

        @classmethod
        def today(cls):
            return instant.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return instant.replace(tzinfo=None)

    module = types.ModuleType("datetime")
    module.__dict__.update({k: v for k, v in vars(_real_datetime_module).items()
                            if not k.startswith("__")})
    module.date = FixedDate
    module.datetime = FixedDatetime
    return FixedDate, FixedDatetime, module


def patch_module(module, stand_ins):
    """Rebind the clock names a module holds. Names that are not the real
    `datetime` module, `date` or `datetime` are left alone."""
    fixed_date, fixed_datetime, fixed_module = stand_ins
    for name, value in list(vars(module).items()):
        if value is _real_datetime_module:
            setattr(module, name, fixed_module)
        elif value is _REAL_DATETIME:
            setattr(module, name, fixed_datetime)
        elif value is _REAL_DATE:
            setattr(module, name, fixed_date)


class _PatchingLoader:
    """Wraps a module loader and patches the module after it runs."""

    def __init__(self, loader, stand_ins):
        self._loader = loader
        self._stand_ins = stand_ins

    def create_module(self, spec):
        return self._loader.create_module(spec)

    def exec_module(self, module):
        self._loader.exec_module(module)
        patch_module(module, self._stand_ins)

    def __getattr__(self, name):
        return getattr(self._loader, name)


class _ClockFinder(importlib.abc.MetaPathFinder):
    def __init__(self, stand_ins):
        self._stand_ins = stand_ins

    def find_spec(self, name, path=None, target=None):
        if name != "compass_pkg" and not name.startswith("compass_pkg."):
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _PatchingLoader(spec.loader, self._stand_ins)
                return spec
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fixed_clock")
    parser.add_argument("--cli", required=True, help="the cli folder to run")
    parser.add_argument("--at", required=True, help="the fixed instant, ISO 8601")
    parser.add_argument("compass_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    compass_args = args.compass_args
    if compass_args and compass_args[0] == "--":
        compass_args = compass_args[1:]
    os.environ["TZ"] = "UTC"
    time.tzset()
    cli = os.path.abspath(args.cli)
    sys.path.insert(0, cli)
    sys.meta_path.insert(0, _ClockFinder(make_stand_ins(_parse_instant(args.at))))
    sys.argv = [os.path.join(cli, "compass"), *compass_args]
    runpy.run_path(os.path.join(cli, "compass"), run_name="__main__")


if __name__ == "__main__":
    main()
