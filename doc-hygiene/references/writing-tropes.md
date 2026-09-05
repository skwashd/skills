# Writing Tropes to Avoid

AI-generated documentation has a recognisable smell. Readers discount everything that smells of it, so a single trope can cost the whole document its credibility. Keep all of the following out of documentation, release notes, and any other prose.

## Banned Vocabulary

Words that appear constantly in generated text and rarely in text written by a busy engineer:

- delve, dive (deep dive), unpack, explore (for "describe")
- seamless, seamlessly, effortless, effortlessly
- robust, powerful, cutting-edge, state-of-the-art, blazingly fast
- comprehensive, holistic, all-encompassing
- leverage (as a verb — write "use")
- streamline, supercharge, elevate, empower, unlock, unleash
- crucial, vital, pivotal, game-changing, revolutionary
- landscape, ecosystem (unless literally about package ecosystems), realm, journey
- meticulous, meticulously, intricate, nuanced
- foster, facilitate, harness
- "a testament to", "underscores", "highlights the importance of"

None of these words is wrong in isolation. The ban is on the register they collectively create.

## Banned Constructions

- **"It's not just X, it's Y."** / "more than just a tool" — empty escalation.
- **"Whether you're a beginner or a seasoned professional..."** — audience-flattering filler.
- **Rule-of-three adjective chains**: "simple, fast, and reliable". Pick the one that's true.
- **The hedged superlative**: "one of the most powerful ways to...".
- **Conclusion fluff**: sections ending "In conclusion", "In summary", "Happy coding!", "The possibilities are endless", or a paragraph restating what was just said.
- **The mirrored opener**: restating the user's request or the section heading as the first sentence of the body.
- **Emoji bullet decoration** in technical docs. Emoji carry no information; the reader is scanning for facts. (A single badge row in a README is fine.)
- **Bold-lead bullet lists where the bold phrase just repeats the sentence**: "**Fast:** it is fast."
- **Exclamation marks** in documentation. Almost never warranted.
- **"Simply" / "just" / "easily"** before an instruction — if it were simple the reader wouldn't be reading docs. Also condescending when the step fails.
- **Marketing claims presented as fact**: "ensures", "guarantees", "eliminates" for things the code merely attempts. Overstated claims are bugs — someone will rely on them.
- **Projection-as-outcome**: describing planned or hoped-for behaviour in the present tense as though it already works.

## Structural Tropes

- **FAQ sections nobody asked** — questions invented to fill space.
- **A "Features" list that paraphrases the code** — features earn a mention when a user would choose the project because of them.
- **Symmetric section padding** — giving every section the same length regardless of how much there is to say. Length should follow content.
- **Tables for things that aren't tabular** — two-column tables whose second column is prose.
- **Redundant "Overview" sections** that say what the next section says.

## What Good Looks Like

Short declarative sentences. Concrete nouns and version numbers. The why behind decisions. Honest statements of limitations ("does not support X"). First person singular where the project has a single author-voice. When in doubt, cut.
