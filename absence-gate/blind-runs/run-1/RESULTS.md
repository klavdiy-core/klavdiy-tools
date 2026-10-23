# absence-gate — blind run 1 (unedited)

Gate: tag `blind-run-1`, commit 5392227, absence_gate.py SHA-256 `E1B290B115E7110720B3272CC065BA22CD4134A55F45AA42AEF814E6AE58335A` (checked by this runner before the run).
Sealed answer key SHA-256 received before the run: `1bb6ec13c3463449e6712e96a5ddd2a38fbd46cd1c7973c3c4eba1a9a8fc91dd`.
Each case: the case's claim.txt, the gate pointed at only that case's files/ directory. Exit 0=ALLOW (PASS), 4=BLOCK, 5=REVIEW.
The frozen gate has no separate action layer (v0.6 not built): verdict only.

## Author's note — written after the run, before the key was opened

**All 20 cases returned ALLOW with "no absence claim".** Every claim in the corpus is a *positive existence* claim
("The document for Alice about X-918 exists."). The frozen gate, by design, evaluates only *absence* claims ("I couldn't
find…", "there is no record of…") and lets every other sentence through untouched. So the gate never reached its
evidence or policy layers on any case: this run measured the gate's **scope**, not its judgment.

This is a real mismatch, and it is the main result: the corpus and the gate understood differently what the gate is
for. I am not rewriting the claims into negations — that would change the corpus after receiving it, which the protocol
forbids. Two honest ways on, the corpus author's call: (a) open the key as is, and score this run as "out of scope ×20";
(b) a separate run-2 with absence-form claims written by the corpus author, frozen and sealed the same way.

Where the mismatch is mine: the README's first line says what the gate blocks ("I don't have it / there's no record"),
but nowhere says plainly that a positive claim is never evaluated and that ALLOW then means *not looked at*. That is now
a known gap in the documentation; it will be fixed only after this run is closed.

| case | claim | exit | verdict | gate's reason / first line |
|---|---|---|---|---|
| C01 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C02 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C03 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C04 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C05 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C06 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C07 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C08 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C09 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C10 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C11 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C12 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C13 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C14 | The invoice for Dana about Q-204 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C15 | The invoice for Dana about Q-204 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C16 | The report for team Orion about INC-441 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C17 | The document for Alice about X-918 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C18 | The invoice for Dana about Q-204 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C19 | The report for team Orion about INC-441 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |
| C20 | The document for Rowan about K-77 exists. | 0 | **ALLOW** | ABSENCE_GATE_OK: no absence claim |

## Raw outputs

### C01

cwd: `<pack>\blind_pack\cases\C01`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C02

cwd: `<pack>\blind_pack\cases\C02`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C03

cwd: `<pack>\blind_pack\cases\C03`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C04

cwd: `<pack>\blind_pack\cases\C04`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C05

cwd: `<pack>\blind_pack\cases\C05`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C06

cwd: `<pack>\blind_pack\cases\C06`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C07

cwd: `<pack>\blind_pack\cases\C07`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C08

cwd: `<pack>\blind_pack\cases\C08`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C09

cwd: `<pack>\blind_pack\cases\C09`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C10

cwd: `<pack>\blind_pack\cases\C10`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C11

cwd: `<pack>\blind_pack\cases\C11`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C12

cwd: `<pack>\blind_pack\cases\C12`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C13

cwd: `<pack>\blind_pack\cases\C13`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C14

cwd: `<pack>\blind_pack\cases\C14`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C15

cwd: `<pack>\blind_pack\cases\C15`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C16

cwd: `<pack>\blind_pack\cases\C16`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C17

cwd: `<pack>\blind_pack\cases\C17`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C18

cwd: `<pack>\blind_pack\cases\C18`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C19

cwd: `<pack>\blind_pack\cases\C19`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```

### C20

cwd: `<pack>\blind_pack\cases\C20`
command: `-I -X utf8 <repo>\absence-gate\absence_gate.py claim.txt --root files`
exit: 0

```
ABSENCE_GATE_OK: no absence claim

```
