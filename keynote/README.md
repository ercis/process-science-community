# Keynote material

QR codes for the closing slide. Both were generated at error correction level H,
which is the most robust level, and both were decoded back to their URL to check
them before committing.

| File | Encodes | Use it when |
| --- | --- | --- |
| `qr-join-process-science-org.*` | `https://process-science.org/join/` | The DNS records are live and Pages has issued the certificate. **This is the one to use.** |
| `qr-join-github-pages-fallback.*` | `https://ercis.github.io/process-science-community/join/` | Only if the custom domain is not ready in time, **and** the `CNAME` file has been removed from the repository root first. While `CNAME` is present, GitHub redirects this URL to the custom domain, so the fallback would fail exactly when it is needed. |

Use the `.svg` in the slide deck: it stays sharp at any projector resolution.
The `.png` is there for tools that will not take SVG.

Test the real thing before Tuesday: scan the printed or projected slide with a
phone that is **not** on the university network, and check that the form loads
and submits.
