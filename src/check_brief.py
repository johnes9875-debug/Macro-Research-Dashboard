"""Check that every number in a drafted brief exists in data/outputs/brief_facts.json.

Usage: python src/check_brief.py brief.txt
Exit code 0 = all numbers verified; 1 = prints the numbers it could not find (fix the draft or
send the brief as numbers only). Dates, times, years and day counts next to month names are ignored.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
facts = json.loads((ROOT / "data" / "outputs" / "brief_facts.json").read_text())


def numbers(o, out):
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        out.append(float(o))
    elif isinstance(o, str):
        for m in re.findall(r"-?\d+(?:\.\d+)?", o):
            out.append(float(m))
    elif isinstance(o, dict):
        for v in o.values():
            numbers(v, out)
    elif isinstance(o, list):
        for v in o:
            numbers(v, out)


known = []
numbers(facts, known)
known_abs = [abs(v) for v in known]

text = Path(sys.argv[1]).read_text()
MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
clean = re.sub(r"https?://\S+", " ", text)                             # links
clean = re.sub(r"(?<=\d),(?=\d{3})", "", clean)                          # thousands separators
clean = re.sub(r"\b25bp hike\b", " ", clean)                           # the standard hike size
clean = re.sub(r"\b\d{1,2}:\d{2}\b", " ", clean)                       # times
clean = re.sub(rf"\b\d{{1,2}}\s+{MONTHS}\b", " ", clean)              # 29 Oct
clean = re.sub(rf"\b{MONTHS}\s+\d{{1,2}}\b", " ", clean)              # Oct 29
clean = re.sub(r"\b20[2-3]\d\b", " ", clean)                          # years
clean = re.sub(r"\b(?:2s10s|5s30s|5s20s|2s5s10s|5y5y|G10|10y|2y|5y|30y|20y|1y|1m|3m|6m|12m|Q[1-4])\b", " ", clean)  # tenor labels
bad = []
for tok in re.findall(r"[−\-+]?\d+(?:\.\d+)?", clean):
    t = tok.replace("−", "-").replace("+", "")
    x = abs(float(t))
    dec = len(t.split(".")[1]) if "." in t else 0
    tol = 0.5 * 10 ** (-dec) + 1e-9
    # allow the value or its bp/% re-expression (e.g. 0.99% term premium written as 99bp)
    if not any(abs(x - k) <= tol or abs(x - k * 100) <= tol or abs(x * 100 - k) <= tol * 100 for k in known_abs):
        bad.append(tok)
if bad:
    print("UNVERIFIED NUMBERS:", ", ".join(sorted(set(bad))))
    sys.exit(1)
print("All numbers verified against brief_facts.json")
