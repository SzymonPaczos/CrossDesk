# CrossDesk Linux handoff — 2026-11-06

The sole acceptance plan is task-briefs/ADP-2026-11-06-01.md, indexed by backlog.
This is reproduction guidance, not a second queue or a record of executed gates.
Quality source facts: history/2026-11-06-quality-audit.md. Configuration proof:
toolkit-adoptions/A1-review.md and A1-artifact-manifest.json.

A1 configuration is accepted. A3 is a source/Git audit plus bounded test evidence.
A2/A4 remain open; report and brief carry the evidence and limitations.
QLT/SEC and existing A0905/PLAN work are tracked in the canonical backlog/PLAN.

## Source and clone setup

Toolkit source is the PUBLISHED FEATURE BRANCH chore/project-adoptions-2026-11-06,
version 2026.11.07, exact pin 879edc6f6fcf08762adcd1c34244c582bb690535.
This is not toolkit main. CrossDesk work branch is
chore/toolkit-adoption-audit-2026-11-06, based on origin/main
 d761d6805be6e70a9a23b0276fad16b1b6e6c969. The project branch becomes remotely
available only after P5; obtain the reviewed final project SHA from Coordinator.
The old local audit branch with 11 unique commits must not be merged/deleted
implicitly during setup.

Inside an approved isolated Linux clone/preparation environment:

```sh
git clone --branch chore/project-adoptions-2026-11-06 --single-branch https://github.com/SzymonPaczos/claude-toolkit.git claude-toolkit
git -C claude-toolkit checkout --detach 879edc6f6fcf08762adcd1c34244c582bb690535
git -C claude-toolkit rev-parse HEAD
git clone --branch chore/toolkit-adoption-audit-2026-11-06 --single-branch https://github.com/SzymonPaczos/CrossDesk.git CrossDesk
git -C CrossDesk rev-parse HEAD
git -C CrossDesk status --short
```

Do not substitute main or a floating newer toolkit for the reviewed source.
Before running target code, make the sandbox enforce no external network,
sanitized environment/HOME, no host secrets or sockets, controlled writable
scratch and CPU/memory/process/time limits. A worktree or venv alone is not
this boundary. Provision reviewed toolchains/dependency/advisory caches before
target execution; unavailable cache or control is needs_validation, not a skip
that counts as PASS. No global skill installation or symlink is needed.

## Tool/dependency preparation (not executed here)

Use the existing CI-tested Python 3.12 toolchain; do not silently change the
public >=3.9 contract (A0905-06). Provision Rust/Cargo plus the Windows GNU
target, buf, Qt6 tools, and the chosen scanners at reviewed versions. Existing
Ubuntu CI explicitly installs these OS development dependencies:

```sh
sudo apt-get update
sudo apt-get install -y build-essential libvirt-dev libsystemd-dev pkg-config mingw-w64 qt6-base-dev qt6-declarative-dev qt6-declarative-dev-tools cmake ninja-build
rustup target add x86_64-pc-windows-gnu
```

These are preparation commands requiring an approved package source/network;
Python 3.12 availability is image-specific and is not assumed from apt's default.
Use a reviewed wheelhouse containing dev/linux dependencies and hatchling, and
a complete reviewed Cargo cache. Source constraints are not a reproducible
Python lockfile; retain the selected inventory/fingerprints (A0905-09/lock debt).
In the real OS sandbox with external network disabled:

```sh
cd CrossDesk
python3.12 -m venv host/.venv
host/.venv/bin/python -m pip install --no-index --find-links /wheelhouse hatchling
(cd host && .venv/bin/python -m pip install --no-index --find-links /wheelhouse --no-build-isolation -e '.[mock,dev,linux]')
```

Editable installation/build backends and Python startup files can execute code;
these commands belong inside the sandbox, never on the personal host. Do not
run a target-provided dependency resolver on the host to fill missing caches.
GUI checks need Qt6 headers/tools discoverable in the image. A Linux VM with
KVM/libvirt, D-Bus, QEMU/OVMF and a reviewed FreeRDP binary is a separate runtime
acceptance environment; the source lookup accepts xfreerdp-family names and an
explicit CROSSDESK_FREERDP_BIN. Installing headers is not real VM acceptance.

## Scoped quality checks inside that sandbox

Select the exact gate spec against the reviewed final SHA. Existing commands:

```sh
bash ../claude-toolkit/scripts/toolkit-sync.sh check .
(cd host && .venv/bin/ruff check src/ tests/)
(cd host && .venv/bin/mypy --strict --python-version=3.12 src/)
(cd host && .venv/bin/pytest -x -q --no-header --ignore=benches/ -p no:cacheprovider tests/)
(cd guest && cargo check --locked --offline --workspace --target x86_64-pc-windows-gnu)
(cd guest && cargo test --locked --offline --workspace --features ipc-vsock/mock)
(cd guest && cargo clippy --locked --offline --workspace --target x86_64-pc-windows-gnu -- -D warnings)
(cd guest && cargo build --locked --offline --release --target x86_64-pc-windows-gnu -p agent-svc)
(cd gui && cargo check --locked --offline --workspace)
(cd gui && cargo test --locked --offline --workspace)
(cd proto && buf lint)
(cd proto && buf format --diff --exit-code)
```

The release guest build is distinct from cargo check. Retain PE artifact/hash,
exit codes, skipped-test reasons and exact inventory. Pytest may build the
Rust mock guest; that is target execution and also needs the cached sandbox.
Missing PKI/Cargo or CROSSDESK_SKIP_INPROCESS can skip the real-wire mock-agent
integration. Generate only disposable test PKI with a reviewed script in the
sandbox; never copy host/production leaf keys. Real libvirt/destructive tests
are opt-in; do not pass --live-libvirt or perform install/destroy/suspend during
this metadata audit. Live Stage B, real host sleep, README and package criteria
remain the existing PLAN work with their owner/environment constraints.
Microbench measures in-process overhead, not an end-to-end launch SLO.

## Hooks and publication

Existing CrossDesk hooks are active (`core.hooksPath=.githooks`). Review them
before activation in a new isolated clone. Pre-commit updates architecture and
ignorefile timestamps and stages them. Never disable hooks or use --no-verify.
Docs-only pre-push skips Python/Rust/proto build blocks, but installed cargo-audit,
cargo-deny and gitleaks still run and can block publication. Existing local-review
policy remains; this handoff does not introduce mandatory PRs or main protection.
Scanner details are in the quality/security reports. A failed gate remains failed.

## Coordinator evidence and next Linux action

Read history/2026-11-06-integration-status.md, the quality audit and
history/2026-11-06-security-audit.md before running checks. Whole skill
catalogs are adopted, including Cloudflare; the actual Cloudflare run is
INCOMPLETE at history/2026-11-06-cloudflare/REPORT.md. Its resume.md lists
remaining phases. Zero final findings do not mean a clean security audit.
Further Claude/Fable source review requires the pending owner provider consent.

The Coordinator executed only bounded cached-image checks: CrossDesk 94 selected
synchronous tests passed; full collection blocked on dependencies. BootControl
10 wrapper meta-tests passed with mocked compiler/build output. The receipt
records source hashes, overlay hashes and sandbox controls. No actual Rust
build, real Polkit, live libvirt or firmware verification was performed.
A2 and A4 remain open in the canonical ADP brief. No copied runtime or green
metadata validation closes these stages. toolkit-sync check exits 1 because
adoption is in progress; the earlier fragment-link false positive is fixed.
