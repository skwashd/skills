---
name: doc-hygiene
description: Create, review, or update a project's documentation files — README.md, CLAUDE.md, AGENTS.md, and similar standalone docs — with a strict humans-vs-agents split, zero duplication between files, and no AI-slop writing tropes. Covers doc files only, never docstrings or inline code comments. Use this whenever the user asks to create or improve a README, CLAUDE.md, or AGENTS.md, asks "does any documentation need updating?", asks whether docs reflect the current code, complains about duplicated docs, or after a change that alters commands, configuration, or behaviour, to check the doc files for drift.
allowed-tools: Read Glob Grep Edit Write
license: MIT
compatibility: >
  No external tooling required. Runs a project's own documentation generators
  (e.g. terraform-docs) only where the project already uses them.
metadata:
  author: skwashd
  version: "1.0.0"
---

# Doc Hygiene

Keep a repository's documentation split cleanly between human readers and coding agents, free of duplication, and free of drift from the code.

Scope: standalone documentation files only. Docstrings and inline code comments are part of the code — they belong to the change that touches them, not to this skill.

## The Document Taxonomy

Each file has exactly one audience. Content in the wrong file, or in two files, is a maintenance bug: the copies drift apart and one of them starts lying.

- **README.md** — for humans. The purpose of the repo, how to set it up, how to use it, how to deploy it. This is the canonical home for anything a person needs.
- **CLAUDE.md / AGENTS.md** — for coding agents. Standards, conventions, hard-won gotchas, the commands to run, the mistakes not to repeat. It should read like briefing notes, not a manual.

The rule that binds them: **never duplicate — reference.** If something matters to both audiences, it lives in the README, and the agent doc points at it ("Setup: see README.md § Getting Started"). When you find an agent doc that restates the README, the fix is to delete the restated content and replace it with references, keeping only the agent-specific additions.

The same rule applies vertically in monorepos: the top-level file consolidates what's shared; lower-level files reference upward and add only what's specific to their package. Consolidate duplication upward when you find it.

## Generated Regions Are Sacred

Never hand-edit content between generator markers — the next generator run destroys your edit:

```
<!-- BEGIN_TF_DOCS --> ... <!-- END_TF_DOCS -->
```

If that content is stale, run the generator (`terraform-docs`, etc.) instead. When editing a file containing such a block, verify after your edit that the generated region is byte-identical. The same applies to any clearly machine-managed region.

## Writing Standards

- **Headings are titles, so use Title Case.**
- **Match the project's existing spelling variant.** Default to Australian English for new docs ("organise", "behaviour") unless the project already uses US spelling; never mix variants within a project.
- **Docs explain why, not what.** The code shows what; write down intent, constraints, and the reasoning behind non-obvious choices. A doc that paraphrases the code is a liability.
- **Every section must earn its place.** No contribution-guide boilerplate (assume PR authors know open-source etiquette), no auto-generated filler sections, no restating what a heading already says. If a section adds zero value, deleting it is the improvement.
- **No AI writing tropes.** Before writing any prose, read `references/writing-tropes.md` and keep the output clean of everything on it. This matters most for READMEs — they're the public face of the project. When the user asks for a strict controlled-language rewrite, that's the `simple-english` skill (ASD-STE100) — note its Rule 1.14 mandates US spelling, which overrides the variant rule above for that rewrite only.

## The Drift Check

Run this after any change that touches behaviour, and whenever asked "do the docs need updating?":

1. List what changed: commands, flags, environment variables, config keys, context variables, tool versions, workflow steps, states/statuses.
2. Grep the docs for each item. Anything the docs mention that no longer exists, or that exists but the docs don't mention, is drift.
3. Fix drift in the canonical file for its audience (per the taxonomy above), and check the other files reference rather than restate it.
4. Pay special attention to enumerations that grow — supported tools, CLI flags, module inputs. These rot fastest. If a generator exists for the list, use it rather than maintaining it by hand.

Answer explicitly: either "docs updated: <files, what changed>" or "no doc changes needed because <reason>". Silence is not an answer.

## Lessons-Learned Capture

When a session surfaced a rule the hard way — a mistake got fixed, a convention was clarified, a security issue was corrected — record it in the nearest CLAUDE.md so it never has to be relearned. Write the rule plus the one-line why ("Pin runner toolchains explicitly — image updates broke the build on 2026-03-04"). Rules for agents go in CLAUDE.md; procedures for humans go in the README. Before adding, check the rule isn't already there in different words.
