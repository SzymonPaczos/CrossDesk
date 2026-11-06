# CrossDesk audit architecture — preliminary Phase 1

Source is frozen clean d761d6805be6e70a9a23b0276fad16b1b6e6c969. Standard profile;
first-party host Python, guest Rust, GUI/local IPC and maintained CI/release/
packaging are in scope. Vendored WinApps and frozen design reference art are
out of scope. Compatible prior JSON findings/ledgers: none. Historical prose
is a clue, not confirmation or an exclusion. Only baseline recon-a completed;
recon-b/c/d are pending a required model source-payload/endpoint consent gate.
This map and its deterministic planned units are preliminary, not a coverage claim.

CrossDesk is a single-user desktop controller for Windows applications displayed
on Linux via FreeRDP RAIL. Host and operator share the intended OS account. The
Python host uses user-session libvirt rather than a root service/container.
A Windows Rust NT-service guest sends gRPC streams with mTLS and per-frame
AuthContext. The guest is a distinct lower-trust principal; another local OS
user and externally supplied file/protocol inputs are distinct from same-owner
configuration. Same-user host compromise is outside the existing threat model.

Boundaries visible from completed recon-a and Parent source inspection include:
management methods on a Unix socket; agent-to-host control/heartbeat/filesystem
gRPC; certificate identity and replay state; guest RAIL/window/icon data; file
share selectors, mount tokens and host libvirt XML; credential verification and
secret persistence; installer/uninstaller paths; GUI/custom-scheme dispatch;
and CI/build artifacts crossing into release/package trust. This planning map
names candidate surfaces, not demonstrated defects. Real bind kind, socket ACLs,
Windows identity, guest provisioning and deployed signing policy need actual
source tracing or owner-observed runtime facts before any conclusion.

Important source starts are host/src/crossdesk_host/daemon.py, ipc/auth.py,
ipc/control.py, ipc/heartbeat.py, ipc/filesystem.py, ipc/management.py,
filesystem_ctl/real.py, display/rail_manager.py, installer/, freerdp/real.py;
guest/crates/agent-svc/src/planes.rs, credentials.rs, filesystem.rs and session.rs;
gui/crates/crossdesk-gui/src/; infra desktop/installer inputs; release.yml and
packaging/aur/PKGBUILD. The default mock backend cannot certify real libvirt.
The guest filesystem mount function remains explicitly mock; PLAN retains Stage B.

WinApps is a source-documented comparison with different Docker/whole-home
tradeoffs; it is a vendored reference, not the CrossDesk execution path. The
comparison calibrates intended authority only and never excludes a root cause.

Companions selected by boundaries: Desktop for local IPC/files/helper authority;
Protocols for streaming identity/replay and message effects; Web/Auth for mTLS
identity/certificate lifecycle; Resource for guest-controlled cardinality and
stream cleanup; Memory for actual Windows FFI/SMBIOS/handles and binary loading;
Supply Chain for workflows/signing/package promotion; Cloud/Deployment only for
source-visible configuration/fallback and listener selection, not an assumed
cloud, Kubernetes or Docker deployment. Exact per-unit blocks/exclusions live
in coverage-ledger.json. More units may be needed after recon and critics.

No target execution is performed by this Parent. Coordinator separately supplied
OS-sandbox receipts for 94 selected tests; the full suite was blocked by missing
cached modules. That evidence is not a candidate-specific proof. Target tests,
PoCs/builds require the full OS boundary, no external network, empty allowlisted
environment, read-only inputs/tools, scratch-only writes, limits and trusted
no-follow bounded artifact promotion. CLI source review has only Read/Glob/Grep
and formatting-only StructuredOutput; it grants no execution. Two launch approval
rejections executed no model process. No new remote calls until required consent.
