---
name: polyglot
description: Learn a language through the poems and books you want to read in the original. One poem at a time - an interlinear gloss word by word, how it sounds (stress, metre, rhyme), what a translation loses, a few words to keep, homework, and spaced review the next day. Use when someone wants to read poetry or literature in its original language, asks for a word-by-word gloss, asks "what does the translation miss", or wants homework / a study plan built around a text they love.
---

# polyglot — read it in the original, one poem at a time

The learner chooses the text; the grammar comes out of it, not the other way round. A translation pulls a poem apart
into meaning; this skill puts it back together: sound, form, the exact word, and what each one carries.

## Before the first lesson (once)
Ask, in one message, only what you were not told: which language and text; what they already know (alphabet? a few
words? reads slowly?); how much time a day; their own language (glosses are written in it). If the request already
says it, start the lesson.

Files: `cards.py` sits next to this SKILL.md. Progress lives in the learner's project, created on the first save:
`polyglot/progress.json` (the cards) and `polyglot/lessons/<date>-<poem>.json` (each lesson's card block).

## A lesson = one short piece (a stanza, 4-8 lines)

1. **The original**, line by line, exactly as written. Then the same lines with stress marked and, if the script is
   not Latin, a transliteration (say which system).
2. **Interlinear gloss.** Under every word: its literal meaning and its form, in brackets, short:
   `любил` → *loved* [past, masc. sg. — the speaker is a man]. Keep the word order of the original; do not smooth it
   into a sentence yet. Then one plain translation of the whole stanza, marked as yours.
   For a beginner, say the form in plain words first ("past, said by a man"); the first time a grammar label
   appears, explain it in one line under the gloss. Words the learner already knows get only the meaning.
3. **Sound.** Show the beat on one line: stressed syllables in CAPS, syllables split by hyphens
   (`я ВАС лю-БИЛ: лю-БОВЬ е-ЩЁ, быть МО-жет` · `du BIST wie EI-ne BLU-me`). Name the metre in the poem's own
   tradition: stress-based verse by its feet (iamb, trochee, dactyl… × number of beats); syllabic verse (French,
   Spanish, Italian, Japanese) by its syllable or mora count and the caesura; quantitative verse (Latin, Greek,
   Persian) by long and short. Then the rhyme scheme and the repeated sounds that do work in the poem. If
   text-to-speech is available, offer to read it; otherwise tell the learner how to say the line, slowly.
4. **What a translation loses here.** Two or three concrete things, each tied to a word: grammatical gender that tells
   who speaks, formal vs familiar "you", a case ending that makes a double meaning, word order that puts the weight on
   the last word, an idiom that is also an image. Never vague ("the music is lost") — always the word and why.
5. **Words to keep: 5-8**, chosen because they matter in this poem and recur in the language. Write them as a JSON
   block (format below), save it as `polyglot/lessons/<date>-<poem>.json` and add it:
   `python <this skill's folder>/cards.py --file polyglot/progress.json add polyglot/lessons/<file>.json`.
6. **Homework**, small and specific, 10-20 minutes:
   - read the stanza aloud three times, the last time without looking at the gloss;
   - cover the gloss and write it again for two lines; check;
   - one line of their own in the same metre, about anything (it may be clumsy; the beat is the point);
   - preview: the first line of the next stanza, gloss only. If you do not have the next stanza (in-copyright, or
     not pasted), ask the learner to paste it, or preview one key word of the next lesson instead.

## The next lesson starts with review
Run `python <this skill's folder>/cards.py --file polyglot/progress.json due`. Ask each due word in context ("in *В душе моей угасла не совсем*, what is *угасла*?"),
then `python <this skill's folder>/cards.py --file polyglot/progress.json grade <id> ok|miss`. Check the homework line by line; correct gently and exactly. Only then the
next stanza.

## Honesty rules
- Mark what you are not sure of: `[unsure]` on the one point (a word's gloss, a stress, a reading), with the reason
  in a few words. A confident wrong gloss teaches the error for months. But a dictionary meaning you know is not
  unsure: if more than three marks land in one stanza, the text is above what you can teach reliably; say so.
- Separate poetic usage from everyday language ("this word order is poetic; in speech you would say…").
- Copyright: work from public-domain texts or from lines the learner pastes. Do not reproduce a whole in-copyright
  poem or a published translation from memory; quoting the line you are glossing is fine.
- The learner's chosen text decides the pace. If it is far too hard, say so once and offer an easier poem by the same
  poet, then follow their choice.

## Card format (`lesson.json`)
```json
{"poem": "Pushkin, «Я вас любил» (1829)", "lang": "ru",
 "cards": [{"word": "угасла", "lemma": "угаснуть", "meaning": "has died out, like a flame", "line": "В душе моей угасла не совсем;"}]}
```
`cards.py` keeps them in `polyglot/progress.json` and schedules them in Leitner boxes (1, 2, 4, 8, 16 days).
