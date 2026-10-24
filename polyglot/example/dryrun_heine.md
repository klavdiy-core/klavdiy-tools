> A blind dry run: a smaller model (Claude Haiku) was given only SKILL.md and the first stanza of Heine's «Du bist wie eine Blume» (public domain), and asked to teach it to a 50-word learner and to say where the skill was unclear. Its six points were folded into SKILL.md the same evening (setup questions, file paths, metre notation beyond Russian, glosses for beginners, the preview fallback, when to mark [unsure]). Kept as it came out.

# polyglot dry run: Heine, «Du bist wie eine Blume» (1827), stanza 1

Learner: native English speaker, knows the German alphabet and about 50 words, 20 minutes a day.
Text: public domain (Heinrich Heine, 1827). Only the first stanza is used here.

Abbreviations used in the glosses: nom./acc./dat. = case (nominative, accusative, dative); sg. = singular;
fem./masc./neut. = grammatical gender; 1st/2nd/3rd = person.

---

## 1. The original

Du bist wie eine Blume
So hold und schön und rein;
Ich schau dich an, und Wehmut
Schleicht mir ins Herz hinein.

German uses the Latin alphabet, so no transliteration is needed. Stress, capitals = stressed syllable, hyphen = syllable break:

Du BIST wie EI-ne BLU-me
So HOLD und SCHÖN und REIN
Ich SCHAU dich AN, und WEH-mut
SCHLEICHT mir ins HERZ hin-EIN

---

## 2. Interlinear gloss

**Line 1: Du bist wie eine Blume**
- Du — *you* [2nd sg., familiar, nom.]
- bist — *are* [2nd sg. of *sein*]
- wie — *like, as*
- eine — *a* [indefinite article, fem. nom. sg.]
- Blume — *flower* [fem. nom. sg.]

**Line 2: So hold und schön und rein;**
- So — *so, thus* (here: "so ... that")
- hold — *gracious, lovely, sweet* [poetic, old-fashioned; [unsure] exact nuance]
- und — *and*
- schön — *beautiful* (predicate adjective, no ending)
- und — *and*
- rein — *pure, clean, clear* (predicate adjective, no ending)

**Line 3: Ich schau dich an, und Wehmut**
- Ich — *I* [1st sg., nom.]
- schau — *look* [1st sg., colloquial/poetic form of *schaue*; [unsure] that this is the only reading]
- dich — *you* [2nd sg., familiar, acc.]
- an — *at* [separable prefix of *anschauen*, "to look at"; it goes to the end of the clause]
- und — *and*
- Wehmut — *wistful sadness, longing* [fem. nom. sg.; [unsure] exact English word]

**Line 4: Schleicht mir ins Herz hinein.**
- Schleicht — *creeps, sneaks* [3rd sg. of *schleichen*; agrees with *Wehmut*]
- mir — *to me* [1st sg., dat.: the one affected]
- ins — *into the* (= *in das*; *in* + accusative because of movement into)
- Herz — *heart* [neut. acc. sg.]
- hinein — *in, inward* [separable part of *hineinschleichen*; goes to the end of the clause]

**Plain translation (mine, [unsure] on "gracious" and "wistfulness"):**
You are like a flower, / so gracious and beautiful and pure; / I look at you, and wistfulness / creeps into my heart.

---

## 3. Sound

**Metre:** iambic trimeter (three stressed beats per line; unstressed-stressed pairs). Lines 1-3 are regular.
Line 1 ends on an unstressed syllable (feminine ending). Lines 2 and 4 end on a stressed syllable (masculine ending).
- du BIST wie EI-ne BLU-me
- so HOLD und SCHÖN und REIN
- ich SCHAU dich AN, und WEH-mut
- SCHLEICHT mir ins HERZ hin-EIN  [unsure: line 4 opens with a stressed syllable, so the first foot is inverted; I read it as a trochee followed by iambs]

**Rhyme scheme:** ABCB. Only lines 2 and 4 rhyme: *rein* / *hinein* (both -*ein*). Lines 1 and 3 do not rhyme.

**Sounds that do work:**
- *sch* in *schön*, *schau*, *schleicht*: three hushing sounds in lines 2-4. They slow the reading, like breath.
- *und* four times (lines 2 and 3): the "and ... and ... and" list makes the stanza sound like a sigh that keeps going.

**How to hear it without audio:** say each line slowly, one syllable per beat, and clap only on the capitals.

---

## 4. What a translation loses here

1. **"Du" vs "Sie".** The poem uses *du*, the familiar "you", the one for close people, children and lovers. "You" in English is neutral, so the intimacy of the address is gone. Grammar here is "2nd sg., familiar". [unsure] that this register is meant as intimate and not just poetic.
2. **The rhyme *rein* / *hinein*.** *Rein* (pure) and *hinein* (in, inward) share a sound. The poem links purity with the movement of the sadness going inward. English "pure" and "into" do not rhyme, so that link is lost.
3. **Wehmut.** One German word for a sweet, bittersweet longing. The word holds *weh* (pain, "ouch") and *Mut* (mood, spirit; old sense, not "courage"; [unsure] on this etymology). "Melancholy" is too heavy; "sadness" is too flat; "wistfulness" is the closest but does not hold both the pain and the mood in one word.

---

## 5. Words to keep (7)

Chosen because they are in this stanza and common in German (*Herz*, *schön*, *rein*, *hinein*, *Blume* recur often; *Wehmut* is literary, kept for the poem).

```json
{"poem": "Heine, «Du bist wie eine Blume» (1827), stanza 1", "lang": "de",
 "cards": [
 {"word": "Blume", "lemma": "Blume", "meaning": "flower (fem.)", "line": "Du bist wie eine Blume"},
 {"word": "schön", "lemma": "schön", "meaning": "beautiful", "line": "So hold und schön und rein;"},
 {"word": "rein", "lemma": "rein", "meaning": "pure, clean, clear", "line": "So hold und schön und rein;"},
 {"word": "schau", "lemma": "schauen", "meaning": "look (I look); anschauen = to look at", "line": "Ich schau dich an, und Wehmut"},
 {"word": "Wehmut", "lemma": "Wehmut", "meaning": "wistful sadness, longing (fem.) [unsure: exact nuance]", "line": "Ich schau dich an, und Wehmut"},
 {"word": "Herz", "lemma": "Herz", "meaning": "heart (neut.)", "line": "Schleicht mir ins Herz hinein."},
 {"word": "hinein", "lemma": "hinein", "meaning": "in, inward, into", "line": "Schleicht mir ins Herz hinein."}
 ]}
```

Note: `cards.py` is not run in this dry run. Running `cards.py add` would write `polyglot/progress.json`, which is outside what was asked.

---

## 6. Homework (about 15 minutes)

1. Read the stanza aloud three times. The last time, do not look at the gloss.
2. Cover the gloss and write out the gloss for lines 1 and 2. Check against section 2.
3. Write one line of your own in the same metre (three stressed beats, unstressed-stressed pairs), about anything. It can be clumsy; the beat is the point. Example shape: *ich SEH den TAG, es REGNET leis*.
4. Preview of the next stanza: **not available.** The provided text is only stanza 1, and I will not reproduce the next stanza from memory [unsure whether the poem continues in the form I recall]. Send the next stanza and this item is done.

**Review:** none yet. This is the first lesson, so there are no due cards.

---

## SKILL FEEDBACK

- **Setup vs. dry run conflict:** "Before the first lesson" asks questions and says to create `polyglot/` in the project, but this learner's profile was already given and the run was limited to one file. I skipped both; SKILL.md does not say whether the profile counts as the answer or whether the folder is required for a one-off lesson.
- **Card storage is unspecified:** Step 5 says to write a JSON block and run `python cards.py add <lesson.json>`, but SKILL.md does not say where `cards.py`, `lesson.json` or `polyglot/progress.json` live, or whether the JSON goes in the lesson file or a separate one. I could not verify the script exists, so I wrote the block and did not run it.
- **Stress and metre notation are only shown for Russian:** the capitals-and-hyphen style is shown only with the Russian example, and "name the metre" has no list of names for stress-timed languages like German. I guessed the caps-and-hyphen notation and the name "iambic trimeter", and marked the one line I was not sure of.
- **Gloss density for this learner is not defined:** "short" brackets with form labels such as "fem. nom. sg." assume grammar vocabulary a 50-word learner may not have. I defined the abbreviations inline, but the skill gives no rule for that, nor for whether to skip words the learner already knows.
- **Preview item has no fallback:** homework item 4 asks for "the first line of the next stanza", but the learner may only have the first stanza, and the skill does not say what to do when the next stanza is not in the provided text. I could not reproduce it from memory, so I marked it not available.
- **"[unsure]" granularity is unclear:** the skill asks to mark any uncertainty, but it does not say whether a marker goes per word, per line or per section, nor how many are acceptable before the gloss stops being useful. I put it on the specific points and used "[unsure: ...]" where the reason mattered.

