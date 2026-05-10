# Code-signing PKI for `CrossDeskAgent.exe`

Operator quick-start. Full background, threat model and rotation
procedure live in [docs/CODE_SIGNING.md](../../docs/CODE_SIGNING.md).

## Bootstrap (run once on the signing host)

```sh
./generate.sh
git add pki/publisher-root-ca.crt
git commit -m "chore(code-signing): bootstrap publisher root CA"
```

Produces under `./pki/`:

| File | Public? | Committed? | Purpose |
|---|---|---|---|
| `publisher-root-ca.crt` | yes | **yes** | Imported by autounattend into every guest's `Cert:\LocalMachine\Root` |
| `publisher-root-ca.key` | NO | no | Signs the leaf; keep on signing host only |
| `publisher-signing.crt` | yes | no | Regenerable via `--rotate-leaf` |
| `publisher-signing.key` | NO | no | Used by `sign-agent.sh` |
| `publisher-signing.pfx` | NO | no | PKCS#12 bundle consumed by osslsigncode |

## Sign a release binary

**Production path:** every `v*.*.*` tag pushed to GitHub triggers
[`.github/workflows/release.yml`](../../.github/workflows/release.yml),
which cross-compiles `CrossDeskAgent.exe` and runs `sign-agent.sh`
against the PFX decoded from the `CROSSDESK_SIGNING_PFX_BASE64`
repository secret. See `docs/CODE_SIGNING.md` "CI integration" for
the secret-setup procedure.

**Manual fallback** (dev signing, CI bypass, or pre-release smoke
test):

```sh
./sign-agent.sh path/to/CrossDeskAgent.exe
```

Requires `osslsigncode` on PATH (`brew install osslsigncode` /
`apt install osslsigncode`). Backs up the unsigned binary alongside
as `*.unsigned.bak`.

## Rotate the leaf (every 18-24 months)

```sh
./generate.sh --rotate-leaf
```

Keeps the root, re-issues the leaf only.

## Rotate the root (only on key compromise)

```sh
./generate.sh --force
git add pki/publisher-root-ca.crt
git commit -m "chore(code-signing): root rotation (incident: …)"
```

Cuts a new root + leaf. Guests installed BEFORE this rotation will
still trust the old root — there is no in-band revocation path. See
the rotation discussion in `docs/CODE_SIGNING.md`.
