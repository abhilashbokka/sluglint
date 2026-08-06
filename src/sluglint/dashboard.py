"""The stats view as a self-contained HTML page.

Same numbers `sluglint stats` prints, laid out to be scanned rather than read.
A producer opening a script for the first time wants the summary before the
detail, so the page runs: totals, then the script as a strip board, then who
and where, then the numbers against their bands, then a table of everything.

Design notes worth keeping if this is ever restyled:

  * Day is warm and night is cool everywhere on the page. It is the one colour
    decision a reader should never have to look up, and the pair validates for
    colour-vision deficiency against both the light and dark surface.
  * Nothing is encoded by colour alone. Every bar carries its own number, every
    band check carries a word (within, above, below), and the table at the
    bottom holds everything the charts hold.
  * The strip board is the signature view because it is the one a first AD
    already has on a wall: the whole script end to end, each scene as wide as
    it is long, coloured by when it shoots.

No script text is written into the page, only counts and names, because a
dashboard is the artifact most likely to get shared.
"""
from __future__ import annotations

import html
import json

# Light and dark are both selected rather than one being flipped from the other.
TOKENS = """
:root {
  --page:#f7f6f2; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --rule:#c3c2b7; --ring:rgba(11,11,11,.10);
  --day:#eb6834; --night:#2a78d6; --unset:#c3c2b7;
  --ok:#0ca30c; --warn:#fab219;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --rule:#383835; --ring:rgba(255,255,255,.10);
    --day:#d95926; --night:#3987e5; --unset:#383835;
  }
}
:root[data-theme="dark"] {
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --rule:#383835; --ring:rgba(255,255,255,.10);
  --day:#d95926; --night:#3987e5; --unset:#383835;
}
"""

STYLE = TOKENS + """
* { box-sizing:border-box; }
body {
  margin:0; padding:32px 20px 72px; background:var(--page); color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap { max-width:1080px; margin:0 auto; display:flex; flex-direction:column; gap:28px; }
h1 { font-size:26px; margin:0; letter-spacing:-.01em; text-wrap:balance; }
h2 { font-size:13px; margin:0 0 2px; text-transform:uppercase; letter-spacing:.09em;
     color:var(--ink-2); font-weight:650; }
.sub { color:var(--muted); font-size:13.5px; margin:0; max-width:66ch; }
.card { background:var(--surface); border:1px solid var(--ring); border-radius:10px;
        padding:20px 22px; display:flex; flex-direction:column; gap:14px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:1px;
         background:var(--ring); border:1px solid var(--ring); border-radius:10px;
         overflow:hidden; }
.tile { background:var(--surface); padding:16px 18px; display:flex; flex-direction:column; gap:3px; }
.tile .v { font-size:27px; font-weight:600; letter-spacing:-.02em;
           font-variant-numeric:tabular-nums; }
.tile .k { font-size:11.5px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.tile .n { font-size:12px; color:var(--ink-2); }
.legend { display:flex; gap:16px; align-items:center; font-size:12.5px; color:var(--ink-2);
          flex-wrap:wrap; }
.swatch { width:10px; height:10px; border-radius:2px; display:inline-block;
          margin-right:6px; vertical-align:-1px; }
.rows { display:flex; flex-direction:column; gap:7px; }
.row { display:grid; grid-template-columns:150px 1fr 96px; gap:12px; align-items:center; }
.row .label { font-size:13px; color:var(--ink); overflow:hidden; text-overflow:ellipsis;
              white-space:nowrap; }
.row .num { font-size:12.5px; color:var(--ink-2); text-align:right;
            font-variant-numeric:tabular-nums;
            font-family:ui-monospace,"SF Mono",Menlo,monospace; }
.track { height:15px; background:var(--grid); border-radius:4px; overflow:hidden;
         display:flex; gap:2px; }
.seg { height:100%; }
.seg:first-child { border-radius:4px 0 0 4px; }
.seg:last-child { border-radius:0 4px 4px 0; }
.seg:only-child { border-radius:4px; }
.scroll { overflow-x:auto; }
svg { display:block; max-width:100%; }
table { border-collapse:collapse; width:100%; font-size:13px;
        font-variant-numeric:tabular-nums; }
th, td { text-align:left; padding:6px 12px 6px 0; border-bottom:1px solid var(--grid);
         white-space:nowrap; }
th { font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
     font-weight:600; }
td.n { text-align:right; font-family:ui-monospace,"SF Mono",Menlo,monospace; }
.band { display:grid; grid-template-columns:150px 1fr 132px; gap:12px; align-items:center;
        font-size:13px; }
.pill { font-size:11px; padding:2px 8px; border-radius:999px; letter-spacing:.03em;
        border:1px solid var(--ring); text-transform:uppercase; font-weight:600; }
.pill.in { color:var(--ok); }
.pill.out { color:var(--warn); }
details { border-top:1px solid var(--grid); padding-top:12px; }
summary { cursor:pointer; font-size:13px; color:var(--ink-2); }
summary:focus-visible { outline:2px solid var(--night); outline-offset:3px; }
footer { color:var(--muted); font-size:12.5px; max-width:70ch; }
code { font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:12.5px;
       background:var(--grid); padding:1px 5px; border-radius:4px; }
"""


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _tile(value, key, note="") -> str:
    note_html = f'<span class="n">{_esc(note)}</span>' if note else ""
    return (f'<div class="tile"><span class="v">{_esc(value)}</span>'
            f'<span class="k">{_esc(key)}</span>{note_html}</div>')


def _bar_row(label: str, segments: list[tuple[float, str, str]], peak: float,
             number: str, title: str) -> str:
    """One labelled bar. Segments are (value, css colour var, name)."""
    total = sum(v for v, _, _ in segments) or 0.0
    width = (total / peak * 100) if peak else 0.0
    parts = "".join(
        f'<span class="seg" style="background:var({colour});'
        f'width:{(v / total * 100) if total else 0:.3f}%" title="{_esc(name)}"></span>'
        for v, colour, name in segments if v > 0)
    return (f'<div class="row"><span class="label" title="{_esc(title)}">{_esc(label)}</span>'
            f'<span class="track" style="width:{width:.3f}%">{parts}</span>'
            f'<span class="num">{_esc(number)}</span></div>')


def _strip_board(scenes: list, width: int = 1040, height: int = 96) -> str:
    """The whole script end to end: each scene as wide as it is long.

    This is the one view a first AD already has on a wall, which is why it
    leads. Scene order runs left to right, bar width is page length, and colour
    is when it shoots.
    """
    total = sum(s.pages for s in scenes) or 1.0
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Every scene in order, width by page length, coloured day or night.">']
    x = 0.0
    for s in scenes:
        w = max(0.7, s.pages / total * width)
        tod = (s.time_of_day or "").upper()
        colour = "--night" if tod in {"NIGHT", "DUSK", "DAWN", "EVENING", "MIDNIGHT"} else (
            "--day" if tod else "--unset")
        tip = (f"Scene {s.index + 1}: {s.heading} | {s.eighths} pages | "
               f"{len(s.characters)} speaking")
        out.append(f'<rect x="{x:.2f}" y="0" width="{max(w - 0.6, 0.4):.2f}" height="{height - 22}" '
                   f'fill="var({colour})" rx="1"><title>{_esc(tip)}</title></rect>')
        x += w
    # A ruler in tenths, because "where am I in the script" is the question the
    # strip is actually being scanned for.
    for i in range(11):
        tx = width * i / 10
        out.append(f'<line x1="{tx:.1f}" y1="{height - 22}" x2="{tx:.1f}" y2="{height - 16}" '
                   f'stroke="var(--rule)" stroke-width="1"/>')
        anchor = "start" if i == 0 else ("end" if i == 10 else "middle")
        out.append(f'<text x="{tx:.1f}" y="{height - 4}" text-anchor="{anchor}" '
                   f'font-size="10" fill="var(--muted)" '
                   f'font-family="system-ui,sans-serif">{i * 10}%</text>')
    out.append("</svg>")
    return "".join(out)


def _braid(characters: list, scene_count: int, width: int = 1040, top: int = 8) -> str:
    """Who is in the script, and where. One row per character, in scene order.

    The gaps are the point. A row that goes quiet for a third of the page count
    is a character a rewrite dropped, and it is far easier to see than to count.
    """
    rows = characters[:top]
    if not rows or not scene_count:
        return ""
    row_h, pad = 22, 26
    height = pad + row_h * len(rows)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Each character\'s appearances across the script in scene order.">']
    label_w = 150
    plot = width - label_w - 8
    for i, c in enumerate(rows):
        y = pad + i * row_h
        out.append(f'<text x="0" y="{y + 4}" font-size="12" fill="var(--ink)" '
                   f'font-family="system-ui,sans-serif">{_esc(c.name[:22])}</text>')
        out.append(f'<line x1="{label_w}" y1="{y}" x2="{width}" y2="{y}" '
                   f'stroke="var(--grid)" stroke-width="1"/>')
        first = min(c.scenes) if c.scenes else 0
        last = max(c.scenes) if c.scenes else 0
        x1 = label_w + plot * first / max(scene_count - 1, 1)
        x2 = label_w + plot * last / max(scene_count - 1, 1)
        out.append(f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" '
                   f'stroke="var(--night)" stroke-width="2" opacity="0.28"/>')
        for idx in c.scenes:
            cx = label_w + plot * idx / max(scene_count - 1, 1)
            out.append(f'<circle cx="{cx:.1f}" cy="{y}" r="3.2" fill="var(--night)">'
                       f'<title>{_esc(c.name)} in scene {idx + 1}</title></circle>')
    for i in range(11):
        tx = label_w + plot * i / 10
        anchor = "start" if i == 0 else ("end" if i == 10 else "middle")
        out.append(f'<text x="{tx:.1f}" y="12" text-anchor="{anchor}" font-size="10" '
                   f'fill="var(--muted)" font-family="system-ui,sans-serif">{i * 10}%</text>')
    out.append("</svg>")
    return "".join(out)


def _band_row(check) -> str:
    """A measurement on its band. The number is always printed next to it."""
    lo, hi = check.low, check.high
    span = (hi - lo) or 1.0
    # Give the track a margin either side of the band so 'outside' is visible.
    axis_lo, axis_hi = lo - span * 0.6, hi + span * 0.6
    axis = (axis_hi - axis_lo) or 1.0
    band_x = (lo - axis_lo) / axis * 100
    band_w = span / axis * 100
    pos = min(max((check.value - axis_lo) / axis, 0.0), 1.0) * 100
    state = "in" if check.inside else "out"
    return (
        f'<div class="band"><span>{_esc(check.signal.replace("_", " "))}</span>'
        f'<span style="position:relative;height:16px;display:block">'
        f'<span style="position:absolute;inset:6px 0;background:var(--grid);'
        f'border-radius:2px"></span>'
        f'<span style="position:absolute;top:5px;height:6px;left:{band_x:.2f}%;'
        f'width:{band_w:.2f}%;background:var(--night);opacity:.30;border-radius:2px"></span>'
        f'<span style="position:absolute;top:2px;left:{pos:.2f}%;width:3px;height:12px;'
        f'margin-left:-1.5px;background:var(--ink);border-radius:1px"></span></span>'
        f'<span class="num">{check.value:g} '
        f'<span class="pill {state}">{_esc(check.verdict)}</span></span></div>')


def render(metrics, genres=None, comparables=None, profile: str = "", top: int = 12) -> str:
    """The whole page, self-contained. No network, no script text."""
    m = metrics
    title = m.title or "Untitled script"
    # The chart is titled by presence, so it sorts by presence. `m.characters`
    # is ordered by line count, which is the right order for the table and the
    # wrong one for a bar whose length is pages.
    by_presence = sorted(m.characters, key=lambda c: (-c.present_pages, c.name))
    peak_char = max((c.present_pages for c in m.characters), default=1.0) or 1.0
    peak_loc = max((loc.pages for loc in m.locations), default=1.0) or 1.0

    cast_rows = "".join(
        _bar_row(c.name, [(c.present_pages, "--night", "present pages")], peak_char,
                 f"{c.present_pages:.1f}pp",
                 f"{c.dialogue_lines} lines, {c.words} words, {len(c.scenes)} scenes")
        for c in by_presence[:top])
    loc_rows = "".join(
        _bar_row(loc.name,
                 [(loc.pages * (loc.day_scenes / max(loc.day_scenes + loc.night_scenes, 1)),
                   "--day", "day"),
                  (loc.pages * (loc.night_scenes / max(loc.day_scenes + loc.night_scenes, 1)),
                   "--night", "night")]
                 if (loc.day_scenes or loc.night_scenes)
                 else [(loc.pages, "--unset", "no time of day")],
                 peak_loc, loc.eighths,
                 f"{len(loc.scenes)} scenes, {loc.day_scenes} day, {loc.night_scenes} night")
        for loc in m.locations[:top])

    genre_html = ""
    if genres:
        cards = "".join(
            f'<div class="band"><span>{_esc(g.name)}</span>'
            f'<span style="color:var(--ink-2);font-size:12.5px">'
            f'{_esc(", ".join(c.signal.replace("_", " ") for c in g.checks if c.inside) or "no bands matched")}'
            f'</span><span class="num">{g.matched}/{g.total}</span></div>'
            for g in genres[:4])
        genre_html = (
            '<section class="card"><h2>Genre signature</h2>'
            '<p class="sub">Bands over the measurements below, counted. Not a verdict, and '
            'not measured from a corpus: these are conventional heuristics, so read a match '
            'as a prompt to look.</p>' + cards + "</section>")

    band_html = ""
    if comparables:
        band_html = (
            f'<section class="card"><h2>Against the {_esc(profile)} bands</h2>'
            f'<p class="sub">Where each headline number falls relative to what the profile '
            f'conventionally expects.</p>' + "".join(_band_row(c) for c in comparables)
            + "</section>")

    signal_rows = "".join(
        f'<tr><td>{_esc(k.replace("_", " "))}</td><td class="n">{v:g}</td></tr>'
        for k, v in (m.signals.as_dict().items() if m.signals else []))
    cast_table = "".join(
        f"<tr><td>{_esc(c.name)}</td><td class=\"n\">{c.dialogue_lines}</td>"
        f"<td class=\"n\">{c.words}</td><td class=\"n\">{len(c.scenes)}</td>"
        f"<td class=\"n\">{c.present_pages:.1f}</td><td class=\"n\">{c.speaking_share:.1%}</td>"
        f"<td class=\"n\">{c.first_scene + 1}</td><td class=\"n\">{c.last_scene + 1}</td>"
        f"<td class=\"n\">{c.longest_absence}</td></tr>"
        for c in m.characters)
    loc_table = "".join(
        f"<tr><td>{_esc(loc.name)}</td><td class=\"n\">{loc.eighths}</td>"
        f"<td class=\"n\">{len(loc.scenes)}</td><td class=\"n\">{loc.day_scenes}</td>"
        f"<td class=\"n\">{loc.night_scenes}</td>"
        f"<td>{'INT/EXT' if loc.interior and loc.exterior else ('EXT' if loc.exterior else 'INT')}"
        f"</td></tr>"
        for loc in m.locations)

    return f"""<style>{STYLE}</style>
<div class="wrap">
  <header>
    <h1>{_esc(title)}</h1>
    <p class="sub">Production numbers only. Nothing on this page is a judgement about the
    writing, and every figure is arithmetic over the page you can redo by hand.
    Profile: <code>{_esc(profile or "default")}</code>.</p>
  </header>

  <div class="tiles">
    {_tile(f"{m.pages:.0f}", "pages", f"~{m.runtime_minutes:.0f} min at a page a minute")}
    {_tile(m.scene_count, "scenes", f"{m.company_moves} company moves")}
    {_tile(m.speaking_cast, "speaking cast", f"{m.dialogue_lines} dialogue lines")}
    {_tile(m.location_count, "locations", f"{m.action_lines} action lines")}
    {_tile(f"{m.night_share:.0%}", "night", f"{m.night_pages:.0f}pp of {m.day_pages + m.night_pages:.0f}pp timed")}
    {_tile(f"{m.exterior_pages:.0f}", "exterior pages", f"{m.interior_pages:.0f}pp interior")}
  </div>

  <section class="card">
    <h2>The script end to end</h2>
    <p class="sub">Every scene in order. Width is how long it runs, colour is when it shoots.
    A wide bar is a day on one set; a run of hairlines is a montage or a sequence of
    cutaways.</p>
    <div class="legend">
      <span><span class="swatch" style="background:var(--day)"></span>Day</span>
      <span><span class="swatch" style="background:var(--night)"></span>Night</span>
      <span><span class="swatch" style="background:var(--unset)"></span>No time of day</span>
    </div>
    <div class="scroll">{_strip_board(m.scenes)}</div>
  </section>

  <section class="card">
    <h2>Cast by presence</h2>
    <p class="sub">Pages of the scenes each character appears in. An upper bound on screen
    time rather than a measurement of it, because screen time is decided in the edit.</p>
    <div class="rows">{cast_rows}</div>
  </section>

  <section class="card">
    <h2>Where the schedule goes</h2>
    <p class="sub">Page load per location, split by day and night. This is the order a
    strip board gets built in, and the top few sets usually carry a third of the shoot.</p>
    <div class="legend">
      <span><span class="swatch" style="background:var(--day)"></span>Day scenes</span>
      <span><span class="swatch" style="background:var(--night)"></span>Night scenes</span>
    </div>
    <div class="rows">{loc_rows}</div>
  </section>

  <section class="card">
    <h2>Who is on screen, and when</h2>
    <p class="sub">Each row is one character across the script in scene order. The gaps are
    what to look at: a long quiet stretch in the middle is usually a thread a rewrite
    dropped.</p>
    <div class="scroll">{_braid(m.characters, m.scene_count)}</div>
  </section>

  {band_html}
  {genre_html}

  <section class="card">
    <h2>Everything, as a table</h2>
    <p class="sub">The same data the charts hold, for reading and for copying out.</p>
    <details open><summary>Cast ({len(m.characters)})</summary>
      <div class="scroll"><table>
        <thead><tr><th>Character</th><th>Lines</th><th>Words</th><th>Scenes</th>
        <th>Pages</th><th>Share</th><th>First</th><th>Last</th><th>Longest gap</th></tr></thead>
        <tbody>{cast_table}</tbody></table></div>
    </details>
    <details><summary>Locations ({len(m.locations)})</summary>
      <div class="scroll"><table>
        <thead><tr><th>Location</th><th>Pages</th><th>Scenes</th><th>Day</th><th>Night</th>
        <th>Shot</th></tr></thead><tbody>{loc_table}</tbody></table></div>
    </details>
    <details><summary>Raw signals</summary>
      <div class="scroll"><table>
        <thead><tr><th>Signal</th><th>Value</th></tr></thead>
        <tbody>{signal_rows}</tbody></table></div>
    </details>
  </section>

  <footer>Generated by Sluglint. Page counts are estimated from formatted line counts,
  and a page is read as a minute, which is the convention every schedule uses and is
  rough for both dialogue-heavy and action-heavy pages. No text from the script appears
  on this page.</footer>
</div>
"""


def to_html(metrics, genres=None, comparables=None, profile: str = "", top: int = 12) -> str:
    return render(metrics, genres, comparables, profile, top)


def data_blob(metrics, genres=None, comparables=None, profile: str = "") -> str:
    """The same numbers as JSON, for anything that wants to plot them elsewhere."""
    from .report import stats_to_json  # noqa: PLC0415 - avoids a circular import
    return json.dumps(json.loads(stats_to_json(metrics, genres, comparables, profile)))
