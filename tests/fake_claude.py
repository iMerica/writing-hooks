#!/usr/bin/env python3
"""Stand-in for `claude -p` used by the tests. Behavior comes from FAKE_* environment variables."""
import json
import os
import re
import sys
import time

argv = sys.argv[1:]
stdin = sys.stdin.read()
system = argv[argv.index("--system-prompt") + 1] if "--system-prompt" in argv else ""

log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": [a for a in argv if a != system], "stdin": stdin,
                            "guard": os.environ.get("HUMANIZER_HOOK_ACTIVE"),
                            "skill_loaded": "Humanizer: remove AI writing patterns" in system,
                            "extra_loaded": "### 27. Scripted relatability" in system and "### 28. Manufactured intimacy" in system,
                            "layer": "brevity" if "## Layer: brevity" in system else "humanizer"}) + "\n")

mode = os.environ.get("FAKE_CLAUDE_MODE", "rewrite")
brevity = "## Layer: brevity" in system
if brevity and os.environ.get("FAKE_CLAUDE_BREVITY_MODE") == "fail":
    sys.stderr.write("brevity boom\n")
    sys.exit(1)
if mode == "fail":
    sys.stderr.write("boom\n")
    sys.exit(1)
if mode == "garbage":
    print("not json at all")
    sys.exit(0)
if mode == "sleep":
    time.sleep(30)
touch = os.environ.get("FAKE_CLAUDE_TOUCH")
if touch:
    with open(touch, "a", encoding="utf-8") as f:
        f.write("\nA line the user typed while the hook was running.\n")

if "final response reviewer" in system:
    result = os.environ.get("FAKE_CLAUDE_STOP", '{"revise": false, "findings": []}')
else:
    request = json.loads(stdin)
    rules = json.loads(os.environ.get("FAKE_CLAUDE_BREVITY" if brevity else "FAKE_CLAUDE_RULES", "[]"))
    changed = []
    for seg in request["segments"]:
        text = seg["text"]
        for old, new in rules:
            text = re.sub(old, new, text)
        if mode == "drop-token":
            text = re.sub("⟦\\d+⟧", "", text)
        if text != seg["text"]:
            changed.append({"id": seg["id"], "text": text})
    result = json.dumps({"segments": changed})
    if mode == "fenced":
        result = "```json\n%s\n```" % result

print(json.dumps({"type": "result", "is_error": False, "result": result}))
