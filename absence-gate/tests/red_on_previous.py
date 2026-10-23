"""Run the CURRENT selftest (fixture + cases) with the check() of an EARLIER commit swapped in.
Every case added since that commit must fail there — a test that was never red proves nothing.

usage: python tests/red_on_previous.py <commit> [CASES_V06|CASES_V061]   (from the absence-gate folder; needs git and rg)
"""
import importlib.util, io, os, re, subprocess, sys, tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(commit):
    old_src = subprocess.run(["git", "show", f"{commit}:absence-gate/absence_gate.py"], cwd=HERE,
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
    with tempfile.TemporaryDirectory() as d:
        old_path = os.path.join(d, "absence_gate_old.py")
        open(old_path, "w", encoding="utf-8").write(old_src)
        new, old = load(os.path.join(HERE, "absence_gate.py"), "ag_new"), load(old_path, "ag_old")
        new.check = old.check                       # the old policy, the new fixture and cases
        buf = io.StringIO()
        with redirect_stdout(buf):
            new.selftest()
    since = sys.argv[2] if len(sys.argv) > 2 else "CASES_V06"          # which case list is «new» relative to <commit>
    added = {name for name, _, _ in getattr(new, since)}
    red = []
    for line in buf.getvalue().splitlines():
        m = re.match(r"\[(.+?)\] exit (\d) \| expect (\d)", line)
        if m and m.group(1) in added:
            print(("RED  " if m.group(2) != m.group(3) else "GREEN") + f"  {line}")
            red.append(m.group(2) != m.group(3))
    print(f"{sum(red)}/{len(red)} new cases are red on {commit}")
    return 0 if red and all(red) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "HEAD"))
