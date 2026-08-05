# The hosting proxy

Between visitors and the S3 buckets sits an **nginx proxy on `185.105.252.28`**.
Every `pycon.de` hostname resolves there, and nginx decides which bucket answers.

This layer is not in this repository and is not deployed by any workflow here.
It is documented because nothing else records it, and because that gap has bitten
us: a deploy can be green while the bucket it wrote to is not the one nginx
serves.

## Hosts

| Host | Serves |
| --- | --- |
| `pycon.de`, `www.pycon.de` | Redirect only — see below |
| `2027.pycon.de` | The current site, from the buckets in `databags/deploy_targets.yaml` |
| `2016`–`2026.pycon.de` | The standalone site each edition was published as, each from its own bucket |

The per-year sites are still live and independent. They are **not** the
`/archive/{YYYY}/` pages on the current site — that is a second copy of the same
content on a different domain.

## The apex redirect

`pycon.de` and `www.pycon.de` redirect everything to the current site. The
redirect **must preserve the path**:

```nginx
return 302 https://2027.pycon.de$request_uri;
```

`$request_uri` carries the path and the query string.

**Keep this a 302; do not change it to 301.** The apex is meant to serve the site
directly one day (`PyconDE.lektorproject:7`, `databags/branding.yaml:60`). A 301
is cached indefinitely by browsers and crawlers and would make that switch
painful to undo. This redirect is genuinely temporary.

A version of this rule without `$request_uri` sends every path to the homepage.
That was live until August 2026 and is why `canonical_host` points at
`2027.pycon.de` rather than the apex — see the note at
`databags/branding.yaml:57-62`. If the rule is ever rewritten, this is the thing
to get right.

Check it with:

```bash
curl -sSI https://pycon.de/talks/BFL7MQ/ | grep -i '^location'
# → https://2027.pycon.de/talks/BFL7MQ/    (not https://2027.pycon.de/)
```

## Legacy talk URLs, per edition

Measured against the live sites in August 2026. The shape differs by edition
because each was built with a different generator. This is the input for any
future work redirecting the old domains into `/archive/{YYYY}/`.

| Host | Talk URL that resolves today | Notes |
| --- | --- | --- |
| `2026.pycon.de` | `/talks/{CODE}/` | `/talks/{slug}/` 404s |
| `2025.pycon.de` | `/talks/{CODE}/` | `/talks/{slug}/` 404s |
| `2024.pycon.de` | `/program/{CODE}/` | `/talks/*` 404s |
| `2023.pycon.de` | `/program/{CODE}/` | |
| `2022.pycon.de` | `/program/{CODE}/` | |
| `2019.pycon.de` | `/program/{slug-with-code}/` | e.g. `/program/pyconde-trfd98-10-ways-to-debug-python-code-christoph-deil/` |
| `2018.pycon.de` | none | `/schedule/` is a single page; no per-talk URLs |
| `2017.pycon.de` | none | as above |
| `2016.pycon.de` | — | NXDOMAIN |

Three things worth knowing before designing redirects off this table:

- **`/talks/{slug}/` never existed on the old domains.** 2025 and 2026 were
  deployed before the slug migration, so their talk pages are keyed by Pretalx
  code. The slug form only exists on the current site.
- **Codes are unique; slugs are not.** All 847 Pretalx codes are unique across
  every edition, but 6 slugs appear in two editions each (`lightning-talks-2` in
  2026 and 2016, `write-your-own-decorators` in 2019 and 2018, …). A scheme keyed
  on slug without a year is ambiguous for those.
- **2025 and 2026 carry a catch-all 404 rule** on their buckets (any missing key
  301s to `/index.html`), so a 404 there looks like a redirect to the homepage
  rather than an error. The same misconfiguration the current site had.

## Redirecting the old domains — not done yet

Deferred by decision: the per-year sites stay as they are for now, and redirects
will be added there later. When that happens:

- Each edition needs its own rule shape, per the table above.
- `/talks/{CODE}/` and `/program/{CODE}/` can both redirect to
  `https://2027.pycon.de/talks/{CODE}/` and let the existing permalinks resolve
  the rest — no per-talk lookup table is needed on the proxy. See
  [Talk permalinks](redirects.md#talk-permalinks).
- 2019's slug-with-code form would need a lookup, or a regex extracting the code.
- Redirecting a whole per-year domain retires a working website. That is a
  content decision, not a hosting one.

## See also

- [docs/deployment.md](deployment.md) — how and when the site is updated
- [docs/redirects.md](redirects.md) — the four redirect layers inside the site
