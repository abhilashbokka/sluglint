# Benchmark corpus

Empty on purpose.

Sluglint ships no third-party screenplays, because almost none can legally be
redistributed. Scripts posted on IMSDb, Script Slug, or as studio awards PDFs
are copyrighted; publishing them here would be infringement no matter how
public the page they came from is. The reasoning, and a cross-check of the
public-domain lists that circulate online, is in
[docs/public-domain-scripts.md](../../docs/public-domain-scripts.md).

## Adding scripts

Drop any `.fountain` or `.txt` script into this directory and run:

```bash
python benchmark/run.py
```

With this directory empty the runner falls back to `examples/`, so the report
always regenerates.

Two ways to use it:

- **Free scripts.** Anything public domain or Creative Commons licensed can be
  committed here. Record the title, author, licence, and source URL in
  `MANIFEST.md` next to it. CC-BY requires attribution, so that file is the
  attribution.
- **Your own library, kept private.** Point the runner somewhere outside the
  repo and nothing is committed:

  ```bash
  python benchmark/run.py --dir ~/Documents/scripts --out /tmp/report.md
  ```

  This is the right way to test against produced screenplays you legally hold.
  Publish the aggregate numbers if you want; do not publish the text.

`.gitignore` excludes `*.fountain` and `*.txt` in this directory so a script
cannot be committed here by accident. Remove that rule deliberately, per file,
once you have checked the licence.
