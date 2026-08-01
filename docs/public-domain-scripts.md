# Which screenplays can we actually use?

Short answer: far fewer than the lists circulating online claim, and almost none
that are both famous and usable.

This matters because the benchmark needs real scripts, and because getting it
wrong means shipping infringing files in a public repo.

## The mistake almost every list makes

**A film falling into the public domain does not put its screenplay there.**

They are separate copyrights. A film can lose protection through a missing
notice or a failed renewal while the underlying screenplay, registered and
published on its own, stays protected. The same goes for the novel or play the
script was adapted from.

The textbook case is **Charade (1963)**. The film is public domain because the
prints shipped without a copyright notice. The screenplay by Peter Stone was
published separately with notice and is still under copyright. Every list that
names Charade as a free script is repeating this error.

## Cross-check of the fifty-title list

The list of "50 famous movie scripts now in the public domain" that ChatGPT
produced does not survive checking. Sorting it:

**Silent films (roughly 20 of the titles).** Nosferatu, Caligari, The General,
Sherlock Jr., The Kid, The Gold Rush, The Sheik, Thief of Bagdad, Mark of Zorro,
The Lost World, Hunchback, Ten Commandments, Four Horsemen, Man with a Movie
Camera. Most of these films are genuinely public domain in the US. None has a
screenplay in modern format. What survives is intertitle lists and continuity
sheets. Running a linter built for `INT. LOCATION - DAY` against them produces
findings on nearly every line, which would make the precision numbers
meaningless rather than impressive.

**Foreign films with restored US copyright.** Nosferatu, Metropolis, Battleship
Potemkin. Foreign works had US copyright restored under the URAA in 1996.
Their status is contested and not something to rely on.

**Films in the public domain whose scripts are not.** Charade, The 39 Steps,
The Jazz Singer, The Last Man on Earth (adapted from Matheson's *I Am Legend*,
firmly in copyright), The Last Time I Saw Paris (from Fitzgerald), A Farewell to
Arms (from Hemingway), Scarlet Street, D.O.A., Kansas City Confidential,
Suddenly, The Stranger, Beat the Devil. Film-level lapse, script-level
protection, or a protected underlying work.

**Reefer Madness appears twice.**

**The Birth of a Nation is on the list.** It is public domain. It is also a
white-supremacist propaganda film, and putting it in a benchmark corpus for a
tool that wants industry adoption would be a serious mistake regardless of its
copyright status.

**Night of the Living Dead (1968)** is the strongest candidate on the list. The
film lost copyright through a missing notice, and it is in modern screenplay
format. But Project Gutenberg's entry (#23053), which several sources cite as
"the screenplay," is a container for the film itself. The text is boilerplate.
The screenplay's own status is debated rather than settled.

**Net result: zero titles from that list are both safely usable and useful.**

## What the two links actually say

The ScreenCraft article is about public-domain *source material to adapt*:
novels, plays, fairy tales you can write a new screenplay from. It is not about
existing screenplays being free to reuse. These are opposite things.

The theatrehaus article lists **stage plays** entering the public domain. Plays
are a different format with different conventions, and linting them against
screenplay rules would produce noise.

## Does posting a script publicly license it?

No. Scripts on IMSDb, Script Slug, Daily Script, and studio awards PDFs are
copyrighted. The studio posting a PDF for awards voters grants permission to
read it, not to redistribute it. "Most writers are probably fine with it" is not
a licence, and it does not help if a rights holder disagrees.

The distinction that matters:

| Action | Position |
|---|---|
| Reading a script you legally obtained | Fine |
| Running Sluglint on it locally | Fine |
| Publishing aggregate statistics across scripts you read | Likely fine, factual reporting |
| Committing the script text to this repo | Infringement |
| Publishing a named defect list for a living writer's script | Legally arguable, reputationally bad |

That last row is a judgment call rather than a legal one. A tool that wants
writers and production companies to adopt it should not open by publishing a
list of errors in named people's work.

## What is actually usable

- **Creative Commons screenplays.** The Creative Commons wiki lists a handful,
  and 26screenplays.com is a collection of CC-licensed shorts. Real format, real
  licence, unknown names. Each needs its exact licence version confirmed before
  use, and CC-BY requires attribution in the corpus manifest.
- **Your own scripts.** Legally unambiguous and probably the closest thing to
  the real target distribution. They just cannot be published.
- **Fault injection on any of the above.** This is what `benchmark/` does. It
  produces labelled defects without needing anyone's permission, and it measures
  recall exactly.

## Consequence for the benchmark

`benchmark/corpus/` ships empty, with `.gitignore` rules that stop a script
being committed there by accident. The runner falls back to the fixtures in
`examples/`, so the report always regenerates.

Recall is measured and reproducible today. **Precision on real produced
screenplays is not measured**, and the README says so rather than implying
otherwise. Closing that gap means either a CC corpus large enough to matter, or
a human reading every finding on a private corpus and marking it right or wrong.

Nothing here is legal advice. If real money starts depending on the answer, pay
a lawyer who does media licensing.
