# Code signing for `CrossDeskAgent.exe`

## What we do

Every release of `CrossDeskAgent.exe` is Authenticode-signed by the
**CrossDesk publisher leaf cert**, which chains to a self-issued
**CrossDesk publisher root CA**. The autounattend setup that
provisions every CrossDesk guest VM imports that root CA into
`Cert:\LocalMachine\Root` *inside the guest only*, and adds a
narrow Defender exclusion for the install path. The result, **inside
every guest we ever ship**, is:

- `CrossDeskAgent.exe` shows up as **Verified Publisher: CrossDesk
  Project** in Properties → Digital Signatures.
- Defender real-time scan + heuristic ML treat the binary as
  trusted; no quarantine, no false-positive on the NT-service +
  AF_VSOCK + gRPC pattern.
- Service registration via SCM completes silently, no UAC prompt,
  no SmartScreen blue screen.

This costs zero per year. There is no EV cert, no Sigstore issuance,
no third-party CA. The whole trust anchor is a key file we generate
once and keep on the signing host.

## Why this works (and where it stops working)

`CrossDeskAgent.exe` **never leaves a CrossDesk-orchestrated guest**.
The Linux host installer copies it from `/usr/share/crossdesk/` onto a
secondary "tools" CD-ROM that the guest sees as `D:\` during first
boot; from there autounattend copies it to `C:\Windows\System32\`.
Users do not download it from a browser, do not receive it by email,
do not run it on their Windows host. **No Mark-of-the-Web boundary is
crossed**, so SmartScreen reputation never enters the picture.

That also means our self-issued trust **only counts inside our
guests**. If somebody copies `CrossDeskAgent.exe` out of a guest and
runs it on their own Windows machine, Windows there will (correctly)
flag it as Unknown Publisher — our root is not in their store and we
never asked it to be.

This boundary is the whole point. We are not pretending to be a CA
that browsers or other Windows installations should trust. We are
adding our own signing key to *one* trust store that we ourselves
control via the install pipeline. Industry precedent: this is what
every device-manufacturer-controlled OEM image does on day one.

## What we are NOT doing (and why)

- **No EV code-signing certificate.** Cost (≈$300-500/year) plus
  hardware-token requirement plus business-identity verification, all
  in service of SmartScreen reputation we don't need because we never
  trip SmartScreen. Reconsider only if `CrossDeskAgent.exe` ever
  becomes something users download standalone.
- **No Sigstore for `CrossDeskAgent.exe`.** Sigstore would give a
  supply-chain attestation but Windows wouldn't honour it for trust
  decisions, so the Authenticode UX would still need *something* to
  cover. Sigstore is still on the table for **Linux artifacts**
  (host wheels, .deb/.rpm/AUR builds) — orthogonal scope, tracked
  separately.
- **No global Defender disable.** We add an exclusion only for
  `C:\CrossDesk\` plus the agent binary path plus the running process.
  Anything else in the guest still gets full Defender protection. A
  user who installs other software in the same VM is not weakened.
- **No SmartScreen disable.** It's irrelevant inside the guest for
  our binary, and disabling it system-wide would (a) be visible in
  Settings → Reputation-based protection, looking suspicious, and (b)
  weaken protection for any unrelated download the user does in the
  VM.

## Files

```
infra/code-signing/
├── README.md              # operator quick-start
├── generate.sh            # one-shot: produce CA + leaf + PFX
├── sign-agent.sh          # CI/dev: Authenticode-sign a built agent.exe
└── pki/
    ├── publisher-root-ca.crt   ← committed (public)
    ├── publisher-root-ca.key   ← gitignored (private; signing host only)
    ├── publisher-signing.crt   ← gitignored (regenerable)
    ├── publisher-signing.key   ← gitignored
    └── publisher-signing.pfx   ← gitignored (PKCS#12 bundle for sign-agent.sh)
```

## Operator flow

### One-time bootstrap (signing host)

```sh
cd infra/code-signing
./generate.sh
# Verify chain + EKU; output ends with the path to publisher-root-ca.crt
git add pki/publisher-root-ca.crt
git commit -m "chore(code-signing): bootstrap publisher root CA"
```

The PFX, both keys, and the leaf cert stay on the signing host (mode
0600). The root CA *cert* is committed because every guest install
ISO needs it.

### Per-release sign

After a successful cross-compile of `CrossDeskAgent.exe`:

```sh
./infra/code-signing/sign-agent.sh \
    target/x86_64-pc-windows-gnu/release/CrossDeskAgent.exe
```

The script wraps `osslsigncode` (cross-platform; available on macOS
via `brew install osslsigncode` and on Debian/Ubuntu via `apt
install osslsigncode`). It RFC3161-timestamps the signature so it
stays valid after the leaf cert expires.

### Leaf rotation (every 18-24 months, or on key compromise)

```sh
./infra/code-signing/generate.sh --rotate-leaf
```

Re-issues the leaf against the existing root. **Do not regenerate
the root** unless it is itself compromised — every guest ISO already
in the wild is anchored to it.

### Root rotation (catastrophic — root key compromise)

1. Generate a new root + leaf: `./generate.sh --force`.
2. Replace `infra/code-signing/pki/publisher-root-ca.crt` in git.
3. Cut a new release; every guest installed from this release on
   trusts the new root. **Guests installed before the rotation will
   still trust the old root** — there is no in-band revocation path.
   Document any compromise as a known issue and ship a v0.x.y+1
   release that uninstalls the old root via autounattend on upgrade.

## CI integration

The release workflow at [`.github/workflows/release.yml`](../.github/workflows/release.yml)
fires on every `v*.*.*` tag push. Job 2 (`sign-agent`) Authenticode-signs
the freshly-cross-compiled `CrossDeskAgent.exe` inside the runner using
the same `infra/code-signing/sign-agent.sh` wrapper that developers run
locally — same osslsigncode invocation, same RFC3161 timestamp, same
verify round-trip. The PFX is supplied through one secret.

### Secret: `CROSSDESK_SIGNING_PFX_BASE64`

Repository-level secret holding the **base64-encoded** contents of
`infra/code-signing/pki/publisher-signing.pfx`. Base64 is the
established pattern for binary GitHub Secrets — secrets are stored as
strings, and decoding the payload at job start avoids any chance of
embedded control characters tripping up the runner shell.

**Set it (one-time, after `./generate.sh` on the signing host):**

```sh
# macOS
base64 -i infra/code-signing/pki/publisher-signing.pfx | pbcopy
# Linux
base64 -w0 infra/code-signing/pki/publisher-signing.pfx | xclip -sel clip
```

Then **Settings → Secrets and variables → Actions → New repository
secret**, name `CROSSDESK_SIGNING_PFX_BASE64`, paste, save.

**Rotate it** every time the leaf is rotated:

```sh
./infra/code-signing/generate.sh --rotate-leaf
base64 -i infra/code-signing/pki/publisher-signing.pfx | pbcopy
# Then update the secret in the GitHub UI (it overwrites in place).
```

GitHub does not version secrets — overwriting is destructive. If a
release is mid-flight, wait for it to drain before rotating, or temp-
disable the workflow to avoid signing two releases with two different
leaves in the same window.

### Failure modes

The signing job is structured so that **a missing secret warns rather
than fails** the whole release:

- **Secret unset** (e.g., first run from a fork, before the bootstrap
  procedure above): the job emits `::warning::CrossDeskAgent.exe will
  be published UNSIGNED — set CROSSDESK_SIGNING_PFX_BASE64 before
  tagging the next release.` and lets the unsigned binary flow into
  the release. The release body advertises `signed = false` so users
  can avoid that build.
- **Secret set but PFX malformed / wrong password / leaf expired**:
  `osslsigncode sign` fails inside the wrapper, the job fails red,
  and `publish-release` never runs. Fix the PFX and re-run the
  workflow from the same tag (Actions UI → Re-run all jobs).

### Why no separate sign-only workflow

Combining build + sign in one workflow keeps the trust boundary tight:
the signed binary never leaves the GitHub Actions runner before
upload, and the runner is destroyed when the job finishes. A
sign-only workflow that consumed a previously-uploaded artifact would
widen the surface (artifact storage retention window, per-artifact
ACLs) for no reduction in operational cost.

## Threat model integration

Tracked in [docs/THREAT_MODEL.md](THREAT_MODEL.md) C2 (Guest agent)
"T (Tampering)" — the existing row already says `agent.exe signed
(Sigstore/EV)`. That row is now accurate-but-incomplete; the
implementation is "self-signed + per-guest trust seed". Update on
the next THREAT_MODEL revision (owner-approval territory per
AGENTS.md "File boundaries").

## Risk surface

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Root key leaks from signing host | Low (single-box discipline) | An attacker can sign binaries that look trusted *inside any CrossDesk guest*. They still can't get into a guest without going through the install pipeline. | Keep `publisher-root-ca.key` mode 0600 on the signing host; ship from a CI runner with a sealed secret if/when CI signing lands. Rotate root if leak suspected. |
| Leaf key leaks | Medium (more handlers — CI signing) | Same as above but bounded to the leaf cert validity (~2 years). | Rotate leaf annually; revoke via `--rotate-leaf` and re-release. |
| User runs `CrossDeskAgent.exe` outside a CrossDesk guest | Low (not a documented workflow) | Windows shows Unknown Publisher there; correctly. | Document in user-facing docs that the binary is intended for guest use only. |
| Defender exclusion creates a hole for other malware in the guest | Low | Path is narrow (`C:\CrossDesk\` + the System32 binary + the process image). Other Defender protections remain. | Keep exclusion narrow; revisit if MS changes the exclusion semantics. |

## Why the threat-model claim is "Low residual"

Inside the guest, the trust seed is *us* — we built the ISO, we
imported the root CA, we registered the service. There is no
adversary in that loop other than (a) something that compromises
the host before install (game over anyway) or (b) an attacker who
exfiltrated our signing key. (b) is the real risk; the mitigation
is operational discipline on the signing host plus rotation.

Outside the guest, the cert is meaningless — and that is by design.
We are not asking the world to trust this CA; we are asking *one
specific guest VM that we own end-to-end* to trust it.
