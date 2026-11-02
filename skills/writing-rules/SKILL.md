---
name: writing-rules
description: Rules for drafting Markdown and MDX prose (blog posts, articles, docs, READMEs) so it does not read as machine-drafted. Covers rhythm, structure, voice, accuracy and honesty about purpose, with a final check. Use before writing or editing any .md or .mdx file.
---

# Writing rules

These rules are for you, the model writing Markdown or MDX prose: blog posts, articles, docs and READMEs. They stack on top of the hooks in this plugin (the brevity and humanizer layers and the user's style rules); where those already cover something, follow them. Posts that pass the humanizer can still read as machine-drafted because of patterns word-level cleanup misses. These rules target those deeper patterns: even rhythm, tidy closers, lists disguised as prose, dangling references and the absence of a real author. Apply them while drafting, then run the final check before returning the file.

Rules 11 and 14 apply to blog posts and articles. Every other rule applies to all Markdown and MDX prose.

If you were given a voice at session start, write in it as well. These rules win any conflict with it.

## Rhythm

1. Vary sentence length deliberately. In any paragraph of four or more sentences, include at least one sentence over 25 words and one under 8. Never write more than three consecutive sentences of similar length.
2. Limit punchline endings. At most one paragraph in three may end on a quotable, aphoristic line. Otherwise end the paragraph where the information ends.
3. Allow some asides. Use an occasional parenthetical, qualifying clause or second thought. Do not streamline every sentence to the same clean shape.
4. Scan for an even beat. After drafting, check each section for a run of sentences with the same structure. Rewrite until the run breaks.

## Structure

5. Do not disguise a list as prose. Sequences like "The first thing… Then comes… Next…" are a bulleted list with the bullets removed. Either use a real Markdown list or connect ideas by logic (because, which means, unless) rather than by order.
6. Pay off every setup. If the intro promises a cause, a reason or a secret, state it explicitly in the body. Delete any teaser you do not resolve.
7. Weight sections by importance. Do not give every H2 the same length. Spend the most words on the point that matters most; let minor points take a sentence or two.
8. Cut announcing transitions. Remove sentences whose only job is to introduce the next topic ("Now let's look at the deploy pipeline"). The heading already does that.

## Voice and specificity

9. Never invent experience. Do not fabricate anecdotes, clients, test results or first-person stories. Use first person only for experience supplied in the brief or source notes.
10. Mark where a human detail is needed. If a section would be stronger with real experience and none was supplied, leave a comment such as `{/* TODO: add a first-hand example here */}` in MDX or `<!-- TODO: add a first-hand example here -->` in Markdown rather than writing a generic archetype ("A seasoned engineer would…").
11. Take a position. Include at least one claim or recommendation a reasonable reader could disagree with, stated plainly.
12. Choose the less obvious example. Your first-choice example is usually the most expected one. Prefer a specific, concrete detail over the generic case.
13. Write idiomatically. Avoid phrasing that is grammatical but that a native writer would not use ("we realized the migration last quarter"). If a phrase sounds translated, rewrite it.
14. Set a real author. The post's author, in frontmatter or wherever the site records it, must be the person named in the brief, not the brand. If none is given, leave a TODO.

## Accuracy and consistency

15. Track your references. Every "also", "as mentioned", "the same study" or "these" must point to something already stated in the post. Before returning, check each one.
16. Cite only what you can verify. Name a study, statistic or source only if it was supplied or you have confirmed it exists and says what you claim. Link it. If unsure, leave a `TODO: verify source` comment instead of the claim.
17. Hedge only real uncertainty. Do not add "tends to" or "can" to every claim. State established facts plainly and qualify only what is genuinely uncertain.

## Honesty about purpose

18. Do not plant setups for the product. No line may exist only to make the product pitch feel necessary later. If the post promotes a product, mention it openly rather than engineering a lead-in.
19. Write for the reader, not the keyword. Keywords belong in the title, description and headings where they read naturally. Cut or rewrite any body sentence that exists only to hit a search term.

## Final check before returning the file

- [ ] No run of more than three similar-length sentences
- [ ] No more than one paragraph in three ends on a punchline
- [ ] Every setup in the intro is paid off
- [ ] Every "also" or "as mentioned" points to something in the post
- [ ] Every citation supplied or verified, and linked; otherwise a TODO
- [ ] No invented anecdotes; TODO comments where a real example is needed
- [ ] At least one stated position (posts and articles)
- [ ] The author is a real person or a TODO (posts and articles)
- [ ] No sentence exists only for SEO or to set up the pitch
