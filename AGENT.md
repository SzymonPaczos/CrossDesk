# Coding rules

Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing anything beyond a
typo.

## Hard constraints

- **No Docker.** The host runs against `qemu:///session` libvirt directly.
- **No polling.** Both sides communicate through async gRPC streams. No
  `while True: time.sleep(...)` loops, no busy waits.
- **Rust:** idiomatic; `unwrap()` and `expect()` only with a one-line comment
  explaining why the call is infallible at that point.
- **Python:** `asyncio` end-to-end, type hints, `mypy --strict`, `black`
  formatting.
- **Commits:** Conventional Commits.

## Style

- Don't leave `# TODO` placeholders in merged code. If something is genuinely
  deferred, file an issue and link it.
- Comments explain *why*, not *what*. The code already says what it does.
- Keep diffs scoped: a fix doesn't bundle a refactor.
