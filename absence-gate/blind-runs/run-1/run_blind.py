# Blind run 1: the frozen absence-gate over the reviewer's 20 unseen cases. Outputs are published unedited.
import hashlib, json, os, subprocess, sys
GATE = r"<repo>\absence-gate\absence_gate.py"
FROZEN = "E1B290B115E7110720B3272CC065BA22CD4134A55F45AA42AEF814E6AE58335A"
PACK = r"<pack>\blind_pack\cases"
OUT = r"<pack>\RESULTS_blind_run_1.md"

h = hashlib.sha256(open(GATE, "rb").read()).hexdigest().upper()
if h != FROZEN:
    sys.exit(f"GATE_NOT_FROZEN: {h}")
VERD = {0: "ALLOW", 4: "BLOCK", 5: "REVIEW"}
rows, full = [], []
for case in sorted(os.listdir(PACK)):
    cdir = os.path.join(PACK, case)
    man = json.load(open(os.path.join(cdir, "manifest.json"), encoding="utf-8"))
    claim_path = os.path.join(cdir, man["claim"])
    root = os.path.join(cdir, man["evidence_root"])
    claim = open(claim_path, encoding="utf-8").read().strip()
    cmd = [sys.executable, "-I", "-X", "utf8", GATE, man["claim"], "--root", man["evidence_root"]]
    p = subprocess.run(cmd, cwd=cdir, capture_output=True, text=True, encoding="utf-8", errors="replace")
    v = VERD.get(p.returncode, f"EXIT_{p.returncode}")
    first = (p.stdout.strip().splitlines() or [""])[0]
    why = next((l.strip()[5:] for l in p.stdout.splitlines() if l.strip().startswith("why:")), "")
    rows.append(f"| {case} | {claim} | {p.returncode} | **{v}** | {why or first} |")
    full.append(f"### {case}\n\ncwd: `{cdir}`\ncommand: `{' '.join(cmd[1:])}`\nexit: {p.returncode}\n\n```\n{p.stdout.strip()}\n{p.stderr.strip()}\n```\n")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("# absence-gate — blind run 1 (unedited)\n\n")
    f.write(f"Gate: tag `blind-run-1`, commit 5392227, absence_gate.py SHA-256 `{h}` (checked by this runner before the run).\n")
    f.write("Sealed answer key SHA-256 received before the run: `1bb6ec13c3463449e6712e96a5ddd2a38fbd46cd1c7973c3c4eba1a9a8fc91dd`.\n")
    f.write("Each case: the case's claim.txt, the gate pointed at only that case's files/ directory. Exit 0=ALLOW (PASS), 4=BLOCK, 5=REVIEW.\n")
    f.write("The frozen gate has no separate action layer (v0.6 not built): verdict only.\n\n")
    f.write("| case | claim | exit | verdict | gate's reason / first line |\n|---|---|---|---|---|\n")
    f.write("\n".join(rows) + "\n\n## Raw outputs\n\n" + "\n".join(full))
print(OUT)
print("\n".join(rows))
