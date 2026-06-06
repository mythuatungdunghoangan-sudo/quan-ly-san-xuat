import sys, os, pathlib

_DIR = pathlib.Path(__file__).parent / "Phan loai tu dong"
sys.path.insert(0, str(_DIR))
os.chdir(str(_DIR))

_code = compile(
    (_DIR / "app.py").read_text(encoding="utf-8"),
    str(_DIR / "app.py"),
    "exec",
)
exec(_code, {"__file__": str(_DIR / "app.py"), "__name__": "__main__"})
