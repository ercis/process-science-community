# Keynote material

Two QR codes, both generated at error correction level H (the most robust) and
both verified by decoding them back to their URL.

| File | Encodes | Lands on |
| --- | --- | --- |
| `qr-join-anchor.*` | `https://process-science.org/#join` | the full landing page, scrolled to the form |
| `qr-join-page.*` | `https://process-science.org/join/` | the form on its own, nothing above it |

Both work. Measured on a phone viewport against the live site:

| | `/#join` | `/join/` |
| --- | --- | --- |
| Bytes over the wire | 156 KB | 43 KB |
| Time until the form is typeable | 0.72s | 0.51s |
| Distance scrolled to reach it | 12,563px | 0 |

**Pick `/#join` if you want people to land in the whole page** and discover the
platforms and the people by scrolling up. That is a real benefit right after a
keynote, and it is the reason to accept the extra weight.

**Pick `/join/` if the room's wifi worries you.** Two hundred people scanning at
once is the one moment the 3.6x difference in bytes could bite, and the
dedicated page links back to the landing page anyway ("New here? See what the
community is and what it has built"), so nothing is lost, only reordered.

## Using them

Use the `.svg` in the deck: it stays sharp at any projector resolution. The
`.png` is for tools that will not take SVG.

**Put the URL on the slide as readable text next to the code.** Some people will
not scan anything, and if the projector washes the code out, the text is the
only way in. `process-science.org/join` reads well out loud, which
`process-science.org/#join` does not, so that is a further argument for the
dedicated page.

## Robustness

Both codes were decoded back after nine degradations that stand in for a real
room: rendered at 200px and at 120px, Gaussian-blurred as if out of focus,
rotated 12 and 35 degrees, contrast cut to a third for a washed-out projector,
underexposed for a dark room, and small plus blurred plus rotated together.
Both passed all nine.

One note if you re-verify them yourself: **OpenCV's QR decoder fails to read
`qr-join-anchor.png` even though the code is perfectly valid.** That is a known
weakness in OpenCV, not a fault in the code. `zxing-cpp`, which is the engine
family phone cameras actually use, reads it every time under all nine
degradations. Do not regenerate the code on OpenCV's say-so.

## Before Tuesday

Scan the projected slide with a phone that is **not** on the university
network, and check that the form loads and submits. That is the only test that
covers DNS, the certificate, the reverse proxy and the collector at once.
