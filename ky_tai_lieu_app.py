import sys, os, pathlib

_DIR = pathlib.Path(__file__).parent / "Ky tai lieu"
sys.path.insert(0, str(_DIR))
os.chdir(str(_DIR))

_code = compile(
    (_DIR / "ky_tai_lieu.py").read_text(encoding="utf-8"),
    str(_DIR / "ky_tai_lieu.py"),
    "exec",
)
exec(_code, {"__file__": str(_DIR / "ky_tai_lieu.py"), "__name__": "__main__"})
