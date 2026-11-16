# Fixing anything: root cause first

Adapted from obra/superpowers `systematic-debugging` (MIT). Use it for every fix: a task whose test won't go green, a review `R<n>`, a QA `Q<n>`, a CI failure, a broken build.

**The rule: no fix until you know the root cause.** A fix that makes the symptom disappear without explaining it is a guess, and guesses come back as the next finding.

## 1. Find the root cause

- **Read the error completely** — message, stack trace, file and line, exit code. It often names the answer.
- **Reproduce it.** Exact command or steps; does it happen every time? Can't reproduce → gather more data (logs, inputs), don't guess.
- **Check what changed.** `git log` / `git diff` on this branch, new dependencies, config, environment (CI vs local).
- **Across layers** (UI → API → database, CI → build → test), check what goes in and comes out at each boundary to find *where* it breaks before asking *why*.
- **Trace bad values backwards** to where they're first wrong; fix there, not where they crash.

## 2. Compare with a working example

Find similar code in this repo that works. List every difference, however small. If you're following a pattern, read the reference completely rather than skimming it.

## 3. Test one hypothesis

State it: "X is the cause because Y." Check it with the smallest possible change, one variable at a time. Wrong → form a new hypothesis from what you learned; don't stack another change on top.

## 4. Fix

1. Write a **failing test** that reproduces the problem (the simplest one that shows it). Run it; watch it fail for this reason.
2. Make **one** change that fixes the root cause. No "while I'm here" edits.
3. Run that test, then the full suite (`agent-team test <slug>`). Both green, or it isn't fixed.

## When fixes keep failing

Count your attempts. After **3 fixes** that didn't work, stop: each failed fix exposing a new problem somewhere else means a **design problem**, not a bad hypothesis. Don't try a fourth. Report `<id>: 3 fixes failed — design problem` with what you tried and what each attempt revealed; the workflow stops for the owner.

If the cause turns out to be truly external (timing, a flaky service), say what you checked, handle it properly (retry with a limit, a clear error, a wait on a condition rather than a fixed sleep) and note it in your report.

## Red flags — go back to step 1

"Quick fix for now", "let me just try X", several changes in one go, skipping the test "I'll verify by hand", proposing a fix before reproducing, "one more attempt" after two failures.
