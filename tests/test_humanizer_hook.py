"""Tests for humanizer_hook.py. Run: python3 -m unittest discover -s ~/.claude/hooks/humanizer/tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(HERE), "humanizer_hook.py")
sys.path.insert(0, os.path.dirname(HERE))
import humanizer_hook as hh  # noqa: E402

EM = "—"
SKILL = "---\nname: humanizer\n---\n\n# Humanizer: remove AI writing patterns\n\nTest copy of the skill.\n"

AI_DOC = """---
title: Caching guide
---

# Caching Guide

Let's dive into caching. Here's what you need to know.

Caching is not just a performance trick, it's a way of thinking about state.

```js
const cache = new Map(); // not just a map, it's a cache — keep this
```

> "It's not merely a tool, it's a mirror" — a quote that must stay.

| Layer | Purpose |
| ----- | ------- |
| CDN | It's not just fast, it's instant |

See [the docs](https://example.com/not-just-a-link) and run `npm run not-just-a-command`.
"""


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="humanizer-test-")
        self.state = os.path.join(self.tmp, "state")
        self.log = os.path.join(self.tmp, "calls.jsonl")
        skill_path = os.path.join(self.tmp, "SKILL.md")
        with open(skill_path, "w") as f:
            f.write(SKILL)
        fake = os.path.join(self.tmp, "claude")
        with open(fake, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, os.path.join(HERE, "fake_claude.py")))
        os.chmod(fake, 0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("HUMANIZER_", "FAKE_"))}
        self.env.update({
            "HUMANIZER_STATE_DIR": self.state,
            "HUMANIZER_CLAUDE_BIN": fake,
            "HUMANIZER_SKILL_PATH": skill_path,
            "FAKE_CLAUDE_LOG": self.log,
            "FAKE_CLAUDE_RULES": json.dumps([
                [r"Let's dive into caching\. Here's what you need to know\.", "Caching stores results for reuse."],
                [r"is not just a performance trick, it's a way of thinking about state",
                 "changes how you manage state"],
                [r"Caching Guide", "Caching guide"],
            ]),
        })
        os.environ.update({"HUMANIZER_STATE_DIR": self.state})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers
    def write(self, name, text):
        path = os.path.join(self.tmp, "proj", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def read(self, path):
        with open(path) as f:
            return f.read()

    def run_hook(self, mode, payload, **env):
        e = dict(self.env)
        e.update(env)
        proc = subprocess.run([sys.executable, HOOK, mode], input=json.dumps(payload) if not isinstance(
            payload, str) else payload, capture_output=True, text=True, env=e, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def assertQuiet(self, out):
        """No output beyond the writing-rules reminder."""
        if out is not None:
            self.assertEqual(out, {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                          "additionalContext": hh.RULES_REMINDER}})

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def post_write(self, path, **env):
        return self.run_hook("post", {"tool_name": "Write", "cwd": self.tmp,
                                      "tool_input": {"file_path": path, "content": self.read(path)},
                                      "tool_response": {"filePath": path, "type": "create"}}, **env)


class ProseDetection(HookTest):
    def test_classify(self):
        p = lambda rel: os.path.join(self.tmp, "proj", rel)  # noqa: E731
        self.assertEqual(hh.classify(p("README.md")), "md")
        self.assertEqual(hh.classify(p("docs/page.mdx")), "mdx")
        self.assertEqual(hh.classify(p("locales/en.json")), "json")
        # Code files count only when they are copy files.
        self.assertEqual(hh.classify(p("lib/copywriting.ts")), "js")
        self.assertEqual(hh.classify(p("lib/copy.ts")), "js")
        self.assertEqual(hh.classify(p("app/hero.copy.tsx")), "jsx")
        self.assertEqual(hh.classify(p("app/copy/onboarding.ts")), "js")
        self.assertEqual(hh.classify(p("bot/copywriting.py")), "py")
        for skipped in ("app/page.tsx", "lib/utils.ts", "main.py", "index.html", "app/Page.vue", "package.json",
                        "node_modules/x/README.md", "node_modules/x/copywriting.ts", "src/generated/copy.ts",
                        "config.yaml", "LICENSE.md", "copy.d.ts", "copy.min.js", "lib/copyright.ts"):
            self.assertIsNone(hh.classify(p(skipped)), skipped)
        self.assertIsNone(hh.classify(os.path.join(hh.claude_dir(), "CLAUDE.md")))

    def test_markdown_protects_non_prose(self):
        segs = hh.md_segments(AI_DOC)
        prose = "\n".join(s.raw for s in segs)
        self.assertIn("Let's dive into caching", prose)
        self.assertIn("# Caching Guide", prose)
        self.assertNotIn("title: Caching guide", prose)          # front matter
        self.assertNotIn("new Map()", prose)                     # fenced code
        self.assertNotIn("a quote that must stay", prose)        # blockquote
        self.assertNotIn("it's instant", prose)                  # table
        link = [s for s in segs if "See [the docs]" in s.raw][0]
        protected = [t for t, _ in link.tokens]
        self.assertIn("](https://example.com/not-just-a-link)", protected)
        self.assertIn("`npm run not-just-a-command`", protected)
        self.assertNotIn("example.com", link.text)

    def test_jsx_extraction(self):
        src = '''import { Button } from "@/components/ui/button-with-a-long-name-here";
export function Hero({ count }) {
  const label = count > 1 ? "You have several readings waiting for you" : "Nothing here yet";
  return (
    <section className="flex items-center gap-2 text-sm font-bold">
      <h1 title="This page shows your recent readings">Your readings are not just numbers, they are a story</h1>
      <p>You have {count} readings and it's not just data.</p>
      {/* a comment that is not just a comment, it's prose */}
      <Button onClick={() => go("/app/new-reading-path-here")}>Start</Button>
    </section>
  );
}
'''
        segs = hh.js_segments(src, jsx=True)
        raws = {s.raw for s in segs}
        self.assertIn("Your readings are not just numbers, they are a story", raws)
        self.assertIn("You have {count} readings and it's not just data.", raws)
        self.assertIn("This page shows your recent readings", raws)
        self.assertIn("You have several readings waiting for you", raws)
        for s in segs:
            self.assertNotIn("items-center", s.raw)
            self.assertNotIn("@/components", s.raw)
            self.assertNotIn("a comment", s.raw)
        text = [s for s in segs if s.raw.startswith("You have {count}")][0]
        self.assertEqual(text.tokens[0][0], "{count}")

    def test_ts_copy_file_skips_code_like_literals(self):
        src = '''import x from "a module path that has many words in it";
export const copy = { heading: "Your profile is ready for the first reading", "cta-key-name": "Start your first reading" };
throw new Error("Something went wrong while saving the profile data");
if (mode === "this is a comparison that should stay as written") {}
const cls = "flex items-center justify-between gap-4 px-2 py-1";
'''
        raws = [s.raw for s in hh.js_segments(src, jsx=False)]
        self.assertEqual(raws, ["Your profile is ready for the first reading", "Start your first reading"])

    def test_python_copy_file(self):
        src = '''"""Copy for the onboarding flow. This docstring is not copy."""
from app.strings import base_text_for_the_page

HEADLINE = "Your readings are not just numbers, they are a story"
CTA = 'Start your {count} readings and don\\'t stop'
TEMPLATE = f"Hello {name}, this is an f-string and stays"
PATTERN = r"\\d+ not just a regex pattern here"
BODY = """We read your profile
and tell you what it says."""
LABELS = {"button-label-key-name": "Upload your photos now"}
raise ValueError("Something went wrong while saving it")
'''
        segs = hh.py_segments(src)
        raws = [s.raw for s in segs]
        self.assertEqual(raws, ["Your readings are not just numbers, they are a story",
                                "Start your {count} readings and don\\'t stop",
                                "We read your profile\nand tell you what it says.",
                                "Upload your photos now"])
        cta = segs[1]
        self.assertEqual(cta.tokens[0][0], "{count}")
        self.assertIn("don't", cta.text)
        self.assertEqual(hh.finalize(cta, cta.text.replace("Start", "Begin")),
                         "Begin your {count} readings and don\\'t stop")

    def test_classify_is_language_agnostic(self):
        p = lambda rel: os.path.join(self.tmp, "proj", rel)  # noqa: E731
        for name, kind in (("internal/copy/copy.go", "generic.go"), ("App/Copy.swift", "generic.swift"),
                           ("app/copywriting.rb", "generic.rb"), ("src/onboarding.copy.kt", "generic.kt"),
                           ("Resources/copy/Localizable.strings", "generic.strings"), ("copy.yaml", "yaml"),
                           ("config/locales/en.yml", "yaml"), ("copywriting.json", "json"), ("copy.toml", "generic.toml")):
            self.assertEqual(hh.classify(p(name)), kind, name)
        for name in ("internal/server/main.go", "App/ContentView.swift", "config.yaml", "Cargo.toml"):
            self.assertIsNone(hh.classify(p(name)), name)

    def test_go_copy_file(self):
        src = '''package copy

import "fmt"

// Headline is not just a comment, it's prose that stays.
const Headline = "Your profile is not just photos, it is a story"
var Greeting = fmt.Sprintf("Welcome back, %s. You have %d new readings", name, n)
var Raw = `raw strings are not just strings, they stay`
var Labels = map[string]string{"upload-button-key": "Upload your photos now"}
func fail() error { return errors.New("the profile could not be saved right now") }
'''
        raws = [s.raw for s in hh.generic_segments(src, ".go")]
        self.assertEqual(raws, ["Your profile is not just photos, it is a story",
                                "Welcome back, %s. You have %d new readings", "Upload your photos now"])
        greeting = hh.generic_segments(src, ".go")[1]
        self.assertEqual([t for t, _ in greeting.tokens], ["%s", "%d"])

    def test_swift_and_ruby_interpolation(self):
        swift = 'let title = "You have \\(count) readings waiting for you"\nlet key = "plain"\n'
        seg = hh.generic_segments(swift, ".swift")[0]
        self.assertEqual(seg.tokens[0][0], "\\(count)")
        self.assertEqual(hh.finalize(seg, seg.text.replace("waiting for you", "ready")),
                         "You have \\(count) readings ready")
        ruby = "HEADLINE = 'Hi #{name}, your reading is ready to view'\n# a comment that is not just a comment here\n"
        seg = hh.generic_segments(ruby, ".rb")[0]
        self.assertEqual(seg.tokens[0][0], "#{name}")
        self.assertEqual(hh.finalize(seg, seg.text.replace("is ready to view", "can't wait")),
                         "Hi #{name}, your reading can\\'t wait")

    def test_yaml_copy_file(self):
        src = ('hero:\n  headline: Your profile is not just photos, it is a story\n'
               '  cta: "Start your first reading today"\n  note: \'It is ready when you are\'  # comment\n'
               '  body: |\n    Block scalars stay as they are written.\n  count: 3\n')
        segs = hh.yaml_segments(src)
        self.assertEqual([s.raw for s in segs], ["Your profile is not just photos, it is a story",
                                                 "Start your first reading today", "It is ready when you are"])
        plain, _, single = segs
        self.assertIsNone(hh.finalize(plain, "Note: a colon breaks it"))
        self.assertEqual(hh.finalize(single, "It's ready when you are"), "It''s ready when you are")

    def test_parse_json_with_trailing_text(self):
        self.assertEqual(hh.parse_json_object('{"segments": []}\n\nNo changes were needed.'), {"segments": []})
        self.assertEqual(hh.parse_json_object('Here you go: {"a": {"b": 1}} {"c": 2}'), {"a": {"b": 1}})


class FileModification(HookTest):
    def test_rewrites_prose_and_preserves_everything_else(self):
        path = self.write("guide.md", AI_DOC)
        out = self.post_write(path)
        new = self.read(path)
        self.assertIn("Caching stores results for reuse.", new)
        self.assertIn("Caching changes how you manage state.", new)
        self.assertIn("# Caching guide", new)
        # Non-prose is byte-identical.
        for keep in ("---\ntitle: Caching guide\n---", "const cache = new Map(); // not just a map, it's a cache " + EM,
                     '> "It\'s not merely a tool, it\'s a mirror" ' + EM, "| CDN | It's not just fast, it's instant |",
                     "[the docs](https://example.com/not-just-a-link)", "`npm run not-just-a-command`"):
            self.assertIn(keep, new)
        self.assertQuiet(out)  # only the reminder: the file change speaks for itself
        call = self.calls()[0]
        self.assertTrue(call["skill_loaded"])
        self.assertTrue(call["extra_loaded"])  # section 27 rides with the skill
        self.assertEqual(call["guard"], "1")
        self.assertIn('{"disableAllHooks": true}', call["argv"])

    def test_user_rules_applied_deterministically(self):
        path = self.write("note.md", "We shipped caching, retries, and logging.\n\nIt’s “done” now.\n")
        self.post_write(path, FAKE_CLAUDE_RULES="[]")
        self.assertEqual(self.read(path), "We shipped caching, retries and logging.\n\nIt's \"done\" now.\n")

    def test_rejects_rewrite_that_drops_protected_tokens(self):
        path = self.write("links.md", "See [the docs](https://example.com) and `npm test` for more on caching here.\n")
        before = self.read(path)
        self.post_write(path, FAKE_CLAUDE_MODE="drop-token", FAKE_CLAUDE_RULES='[["for more on caching here", "x"]]')
        self.assertEqual(self.read(path), before)

    def test_rejects_rewrite_that_changes_markdown_structure(self):
        doc = "## Setup\n\n- Install the package with the usual command today.\n- Run it once to make sure.\n"
        path = self.write("setup.md", doc)
        self.post_write(path, FAKE_CLAUDE_RULES=json.dumps([[r"^- Install.*\n- ", "Install it and "]]))
        self.assertEqual(self.read(path), doc)

    def test_rejects_rewrite_with_em_dash(self):
        doc = "This feature is not just fast, it is also reliable for every user.\n"
        path = self.write("dash.md", doc)
        self.post_write(path, FAKE_CLAUDE_RULES=json.dumps([["not just fast, it is also", "fast " + EM + " and"]]))
        self.assertEqual(self.read(path), doc)

    def test_jsx_text_rewrite_keeps_code(self):
        src = ('export default function A({ n }) {\n  return <p className="text-sm">You have {n} readings and it’s '
               'not just data, it is a story.</p>;\n}\n')
        path = self.write("app/A.copy.tsx", src)
        self.post_write(path, FAKE_CLAUDE_RULES=json.dumps([["not just data, it is a story", "worth a look"]]))
        self.assertEqual(self.read(path), src.replace(
            "it’s not just data, it is a story", "it&apos;s worth a look"))

    def test_cut_paragraphs_take_their_blank_line(self):
        doc = ("# Guide\n\nLet's dive in. Here's what you need to know about it.\n\n"
               "The cache keeps results for ten minutes and then drops them for good.\n\n"
               "In conclusion, caching matters a lot for every team. I hope this helps!\n")
        path = self.write("cut.md", doc)
        self.post_write(path, FAKE_CLAUDE_RULES=json.dumps([[r"^Let's dive in.*$", ""], [r"^In conclusion.*$", ""]]))
        self.assertEqual(self.read(path),
                         "# Guide\n\nThe cache keeps results for ten minutes and then drops them for good.\n")

    def test_never_cuts_headings_lists_or_paragraphs_with_links(self):
        doc = "- Install the package with the usual command today.\n\nRead [the docs](https://x.y) for every detail.\n"
        path = self.write("nocut.md", doc)
        self.post_write(path, FAKE_CLAUDE_RULES=json.dumps([[r"^.*$", ""]]))
        self.assertEqual(self.read(path), doc)

    def test_regular_code_files_are_never_touched(self):
        src = 'export const title = "Your readings are not just numbers, it’s a story, and more";\n'
        for name in ("app/page.tsx", "lib/utils.ts", "main.py", "index.html"):
            path = self.write(name, src)
            self.assertIsNone(self.post_write(path))
            self.assertEqual(self.read(path), src)
        self.assertEqual(self.calls(), [])

    def test_edit_only_touches_new_text(self):
        doc = ("Let's dive into caching. Here's what you need to know.\n\n"
               "Caching is not just a performance trick, it's a way of thinking about state.\n")
        path = self.write("edit.md", doc)
        payload = {"tool_name": "Edit", "tool_input": {
            "file_path": path, "old_string": "x",
            "new_string": "Caching is not just a performance trick, it's a way of thinking about state."}}
        self.run_hook("post", payload)
        new = self.read(path)
        self.assertIn("Let's dive into caching.", new)            # untouched: not part of this edit
        self.assertIn("Caching changes how you manage state.", new)
        sent = json.loads(self.calls()[0]["stdin"])
        self.assertEqual(len(sent["segments"]), 1)


class UnchangedTextAndRecursion(HookTest):
    def test_second_pass_is_skipped(self):
        path = self.write("guide.md", AI_DOC)
        self.post_write(path)
        after_first = self.read(path)
        self.assertIsNone(self.post_write(path))
        self.assertEqual(self.read(path), after_first)
        self.assertEqual(len(self.calls()), 1)

    def test_clean_text_is_reviewed_once(self):
        path = self.write("clean.md", "The cache keeps results for ten minutes and then drops them for good.\n")
        self.assertQuiet(self.post_write(path))
        self.assertQuiet(self.post_write(path))
        self.assertEqual(len(self.calls()), 1)

    def test_write_skips_text_from_original_file(self):
        original = "Let's dive into caching. Here's what you need to know.\n"
        path = self.write("orig.md", original + "\nA brand new paragraph that the assistant wrote about caching layers.\n")
        self.run_hook("post", {"tool_name": "Write", "tool_input": {"file_path": path},
                               "tool_response": {"type": "update", "originalFile": original}})
        self.assertIn("Let's dive into caching.", self.read(path))
        sent = json.loads(self.calls()[0]["stdin"])
        self.assertEqual([s["text"][:7] for s in sent["segments"]], ["A brand"])

    def test_short_change_skips_the_model(self):
        path = self.write("short.md", "Fixed the typo.\n")
        self.post_write(path)
        self.assertEqual(self.calls(), [])

    def test_guard_env_disables_hook(self):
        path = self.write("guide.md", AI_DOC)
        self.assertIsNone(self.post_write(path, HUMANIZER_HOOK_ACTIVE="1"))
        self.assertEqual(self.read(path), AI_DOC)
        self.assertEqual(self.calls(), [])
        out = self.run_hook("stop", {"last_assistant_message": "It is fine " + EM + " really."},
                            HUMANIZER_HOOK_ACTIVE="1")
        self.assertIsNone(out)

    def test_skipped_paths_never_call_the_model(self):
        path = self.write("node_modules/pkg/README.md", AI_DOC)
        self.assertIsNone(self.post_write(path))
        self.assertEqual(self.read(path), AI_DOC)
        self.assertEqual(self.calls(), [])


class FailureHandling(HookTest):
    def assert_untouched(self, **env):
        path = self.write("guide.md", AI_DOC)
        self.assertQuiet(self.post_write(path, **env))
        self.assertEqual(self.read(path), AI_DOC)

    def test_model_process_fails(self):
        self.assert_untouched(FAKE_CLAUDE_MODE="fail")
        self.assertTrue(os.path.exists(os.path.join(self.state, "errors.log")))

    def test_model_returns_garbage(self):
        self.assert_untouched(FAKE_CLAUDE_MODE="garbage")

    def test_model_times_out(self):
        self.assert_untouched(FAKE_CLAUDE_MODE="sleep", HUMANIZER_FILE_TIMEOUT="1")

    def test_claude_binary_missing(self):
        self.assert_untouched(HUMANIZER_CLAUDE_BIN=os.path.join(self.tmp, "missing"))

    def test_bad_stdin(self):
        self.assertIsNone(self.run_hook("post", "{not json"))
        self.assertIsNone(self.run_hook("stop", ""))

    def test_file_changed_during_processing_is_not_overwritten(self):
        path = self.write("guide.md", AI_DOC)
        self.post_write(path, FAKE_CLAUDE_TOUCH=path)
        self.assertEqual(self.read(path), AI_DOC + "\nA line the user typed while the hook was running.\n")

    def test_fenced_model_output_is_accepted(self):
        path = self.write("guide.md", AI_DOC)
        self.post_write(path, FAKE_CLAUDE_MODE="fenced")
        self.assertIn("Caching stores results for reuse.", self.read(path))

    def test_missing_skill_still_enforces_user_rules_without_model(self):
        path = self.write("note.md", "We shipped caching, retries, and logging for every single service.\n")
        self.post_write(path, HUMANIZER_SKILL_PATH=os.path.join(self.tmp, "nope.md"))
        self.assertEqual(self.read(path), "We shipped caching, retries and logging for every single service.\n")
        self.assertEqual(self.calls(), [])


class StopHook(HookTest):
    AI_REPLY = ("Great question! Here's the thing: the fix is not just a patch, it's a whole new way of thinking "
                "about caching. Let's dive in. I updated the handler so that it reads from the cache first and "
                "only falls back to the database when the entry is missing or stale. I hope this helps!")
    FINDINGS = json.dumps({"revise": True, "findings": [
        {"pattern": "1. Not X but Y", "quote": "not just a patch, it's", "fix": "State the change directly."},
        {"pattern": "22. Chatbot residue", "quote": "I hope this helps!", "fix": "Cut it."}]})

    def stop(self, message, **kw):
        payload = {"session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": False,
                   "last_assistant_message": message}
        payload.update(kw.pop("payload", {}))
        return self.run_hook("stop", payload, **kw)

    def test_blocks_ai_sounding_reply(self):
        out = self.stop(self.AI_REPLY, FAKE_CLAUDE_STOP=self.FINDINGS)
        ctx = out["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "Stop")
        self.assertIn("Not X but Y", ctx["additionalContext"])
        self.assertIn("I hope this helps!", ctx["additionalContext"])
        self.assertNotIn("decision", out)
        self.assertTrue(self.calls()[0]["skill_loaded"])
        self.assertTrue(self.calls()[0]["extra_loaded"])

    def test_cleared_findings_are_dropped(self):
        cleared = json.dumps({"revise": True, "findings": [
            {"pattern": "19. Bold", "quote": "**What moved**", "fix": "Acceptable here. No change needed."},
            {"pattern": "8. Dashes", "quote": "exact wording", "fix": "No dash present; reads fine."}]})
        self.assertIsNone(self.stop(self.AI_REPLY, FAKE_CLAUDE_STOP=cleared))

    def test_findings_on_quoted_examples_are_dropped(self):
        msg = ('The audit found 11 contrasts such as "a useful mirror, not a verdict" in the marketing copy. '
               'It also found 3 fragment closers, for example "Your account stays. Saved profiles stay." '
               'Both are listed in the report with file and line numbers for review later this week.')
        quoted = json.dumps({"revise": True, "findings": [
            {"pattern": "1. Not X but Y", "quote": "a useful mirror, not a verdict", "fix": "State it directly."},
            {"pattern": "2. Closers", "quote": "Your account stays. Saved profiles stay.", "fix": "Merge them."}]})
        self.assertIsNone(self.stop(msg, FAKE_CLAUDE_STOP=quoted))

    def test_allows_clean_reply(self):
        self.assertIsNone(self.stop(self.AI_REPLY))  # fake reviewer says revise: false

    def test_one_correction_pass(self):
        self.assertIsNone(self.stop(self.AI_REPLY, FAKE_CLAUDE_STOP=self.FINDINGS,
                                    payload={"stop_hook_active": True}))
        self.assertEqual(self.calls(), [])

    def test_same_message_reviewed_once(self):
        self.assertIsNotNone(self.stop(self.AI_REPLY, FAKE_CLAUDE_STOP=self.FINDINGS))
        self.assertIsNone(self.stop(self.AI_REPLY, FAKE_CLAUDE_STOP=self.FINDINGS))
        self.assertEqual(len(self.calls()), 1)

    def test_hard_rules_without_model(self):
        out = self.stop("Done " + EM + " the tests pass, the build works, and it’s merged.")
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("em dashes", text)
        self.assertIn("curly", text)
        self.assertIn('comma immediately before "and"', text)
        self.assertEqual(self.calls(), [])  # short message: no model call

    def test_code_and_quotes_are_ignored(self):
        msg = "Updated the parser.\n\n```sh\necho a, and b " + EM + " c\n```\n\nThe flag is `--a, and b`."
        self.assertIsNone(self.stop(msg))

    def test_inline_code_does_not_create_comma_before_and(self):
        self.assertIsNone(self.stop("Then I'll run `type-check`, `lint` and the tests."))

    def test_model_failure_fails_open(self):
        self.assertIsNone(self.stop(self.AI_REPLY, FAKE_CLAUDE_MODE="fail"))


FILLER = " ".join(["Light from a window shapes the face and puts a reflection in each eye."] * 4)
LONG_DOC = """# Choosing a photo

Picking a photo is hard. It is really, truly hard. Strangers judge a face in about 100 milliseconds, so the first look decides. %s

In other words, the first look matters a great deal, as we said and it is worth repeating again here for emphasis.

Ratings of different photos of one person vary as much as ratings of different people (Todorov and Porter, 2014). %s
""" % (FILLER, FILLER)


class BrevityLayer(HookTest):
    CUT = ["^In other words.*$", ""]
    TRIM = [" It is really, truly hard\\.", ""]

    def layers(self):
        return [c["layer"] for c in self.calls()]

    def test_runs_before_humanizer_and_humanizer_sees_its_output(self):
        path = self.write("post.md", LONG_DOC)
        self.post_write(path, FAKE_CLAUDE_BREVITY=json.dumps([self.CUT, self.TRIM]),
                        FAKE_CLAUDE_RULES=json.dumps([["Picking a photo is hard", "Picking a photo is difficult"]]))
        self.assertEqual(self.layers(), ["brevity", "humanizer"])
        humanizer_input = self.calls()[1]["stdin"]
        self.assertNotIn("In other words", humanizer_input)
        self.assertNotIn("really, truly", humanizer_input)
        new = self.read(path)
        self.assertNotIn("In other words", new)
        self.assertNotIn("really, truly", new)
        self.assertIn("Picking a photo is difficult.", new)
        self.assertIn("# Choosing a photo\n\nPicking", new)
        self.assertNotIn("\n\n\n", new)  # the cut paragraph took its blank line with it

    def test_skips_short_writing(self):
        path = self.write("guide.md", AI_DOC)
        self.post_write(path)
        self.assertEqual(self.layers(), ["humanizer"])

    def test_skips_a_single_paragraph(self):
        path = self.write("one.md", "# Title\n\n" + FILLER + " " + FILLER + " " + FILLER + "\n")
        self.post_write(path, FAKE_CLAUDE_RULES="[]")
        self.assertEqual(self.layers(), ["humanizer"])

    def test_never_drops_a_number_or_cuts_a_paragraph_holding_one(self):
        path = self.write("post.md", LONG_DOC)
        self.post_write(path, FAKE_CLAUDE_RULES="[]", FAKE_CLAUDE_BREVITY=json.dumps([
            [" in about 100 milliseconds", ""],
            ["^Ratings of different photos.*$", ""],
        ]))
        new = self.read(path)
        self.assertIn("about 100 milliseconds", new)
        self.assertIn("(Todorov and Porter, 2014)", new)

    def test_never_lengthens(self):
        path = self.write("post.md", LONG_DOC)
        self.post_write(path, FAKE_CLAUDE_RULES="[]", FAKE_CLAUDE_BREVITY=json.dumps([
            ["Picking a photo is hard\\.", "Picking a photo is hard, and here is a much longer sentence about why."],
        ]))
        self.assertEqual(self.read(path), LONG_DOC)

    def test_a_failed_brevity_layer_still_humanizes(self):
        path = self.write("post.md", LONG_DOC)
        self.post_write(path, FAKE_CLAUDE_BREVITY_MODE="fail",
                        FAKE_CLAUDE_RULES=json.dumps([["Picking a photo is hard", "Picking a photo is difficult"]]))
        self.assertIn("Picking a photo is difficult.", self.read(path))
        self.assertTrue(os.path.exists(os.path.join(self.state, "errors.log")))


class WritingRulesReminder(HookTest):
    def post(self, path, session="s1"):
        return self.run_hook("post", {"tool_name": "Write", "cwd": self.tmp, "session_id": session,
                                      "tool_input": {"file_path": path, "content": self.read(path)},
                                      "tool_response": {"type": "create"}}, FAKE_CLAUDE_RULES="[]")

    def test_once_per_markdown_file_per_session(self):
        path = self.write("post.mdx", "The cache keeps results for ten minutes and then drops them.\n")
        first = self.post(path)
        self.assertIn("writing-rules", first["hookSpecificOutput"]["additionalContext"])
        self.assertIn("final check", first["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.post(path))
        self.assertIsNotNone(self.post(path, session="s2"))
        other = self.write("notes.md", "Another file gets its own reminder in the same session.\n")
        self.assertIsNotNone(self.post(other))

    def test_not_for_copy_or_code_files(self):
        path = self.write("copy.ts", 'export const title = "Save your work before you leave the page"\n')
        self.assertIsNone(self.post(path))
        path = self.write("notes.txt", "Plain text is prose but not Markdown, so it gets no reminder.\n")
        self.assertIsNone(self.post(path))

    def test_session_start_hands_over_the_voice_file(self):
        voice = self.write("voice.md", "State a thesis someone could dispute.\n")
        out = self.run_hook("session", {"hook_event_name": "SessionStart", "source": "startup"},
                            CLAUDE_PLUGIN_OPTION_VOICE_FILE=voice)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("State a thesis someone could dispute.", ctx)
        self.assertIn("commit messages", ctx)
        self.assertEqual(self.calls(), [])  # no model call

    def test_session_start_without_a_voice_says_nothing(self):
        self.assertIsNone(self.run_hook("session", {"hook_event_name": "SessionStart"}))
        missing = os.path.join(self.tmp, "nope.md")
        self.assertIsNone(self.run_hook("session", {}, HUMANIZER_VOICE_FILE=missing))
        big = self.write("big.md", "x" * (hh.VOICE_MAX_BYTES + 1))
        self.assertIsNone(self.run_hook("session", {}, HUMANIZER_VOICE_FILE=big))

    def test_skill_files_are_left_alone(self):
        text = "---\nname: rules\n---\n\nLet's dive into caching. Here's what you need to know.\n"
        path = self.write(os.path.join("skills", "rules", "SKILL.md"), text)
        self.assertIsNone(self.post(path))
        self.assertEqual(self.read(path), text)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
