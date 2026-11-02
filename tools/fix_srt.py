#!/usr/bin/env python3
"""Apply tools/glossary.json to an SRT file. Cue numbers and timestamps are never changed.

Usage: python3 tools/fix_srt.py INPUT.srt OUTPUT.srt
Prints every correction made as "wrong -> right (count)".
"""
import json, os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
glossary = json.load(open(os.path.join(here, "glossary.json"), encoding="utf-8"))
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8-sig").read()
before = re.findall(r"^\d+\n[\d:,]+ --> [\d:,]+$", text, re.M)
for wrong, right in sorted(glossary.items(), key=lambda kv: -len(kv[0])):
    n = text.count(wrong)
    if n:
        text = text.replace(wrong, right)
        print(f"{wrong!r} -> {right!r} ({n})")
after = re.findall(r"^\d+\n[\d:,]+ --> [\d:,]+$", text, re.M)
assert before == after, "Cue numbers or timings changed; the glossary must not match timing lines."
open(dst, "w", encoding="utf-8").write(text)
print(f"Wrote {dst}: {len(after)} cues, timings unchanged.")
