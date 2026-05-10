# Per-component span coverage

Status of W3C trace-context span coverage per host component, after
the trace-propagation completion sweep (DEC-0006, FOLLOWUPS:355-388).

## What "covered" means

A component is **covered** when:
1. Every external entry point (gRPC handler, CLI command, daemon
   startup task) opens a child span via
   `crossdesk_host.observability.child_span_scope()` (or equivalent
   manual `child_span` + `bind_to_log_context` + `clear_log_context`
   pair).
2. Log lines emitted from inside that scope carry both the inherited
   `trace_id` (from the upstream parent) and a fresh `span_id`
   distinguishing this invocation.
3. A test asserts the binding holds for at least one log line.

Without coverage the handler still gets the upstream `trace_id` (the
server-wide `TraceContextInterceptor` binds it) but every invocation
shares whatever `span_id` was bound at interceptor time — making it
impossible to tell two concurrent invocations apart in trace
backends.

## Component coverage matrix

| Component | Entry point | Span coverage | Notes |
|---|---|---|---|
| `ipc/control.ControlServiceServicer.OpenSession` | bidi stream | ⚠️ inherits parent | per-handler child span follow-up — single long-lived stream so the trade-off is "one span per session vs one per ClientFrame" |
| `ipc/heartbeat.HeartbeatServiceServicer.Channel` | bidi stream | ⚠️ inherits parent | same trade-off as control |
| `ipc/filesystem.FilesystemServiceServicer.ShareChannel` | bidi stream | ⚠️ inherits parent | same trade-off |
| `ipc/management.ManagementServiceServicer.*` | unary RPCs | ⚠️ inherits parent | per-call child span makes sense here (each RPC is one short request); add via `with child_span_scope():` at handler entry |
| `ipc/verify_coordinator.VerifyCoordinator.verify` | server-initiated | ✅ covered | mints a fresh root context per call (Stage 2 already wired this; see `verify_credentials_dispatch` log line) |
| `cli/main.main` | CLI entry | ⚠️ no spans yet | low priority — CLI is short-lived; add only if multi-invocation correlation becomes useful |
| `daemon.main` | startup | ⚠️ no spans yet | startup is one-shot; not a per-invocation surface |

Legend: ✅ covered, ⚠️ inherits parent (correct trace_id, no per-call
span_id distinction), ❌ no trace context at all.

## How to add coverage

Use the context manager exposed from `crossdesk_host.observability`:

```python
from crossdesk_host.observability import child_span_scope

async def SomeRpc(self, request, context):
    with child_span_scope() as ctx:
        logger.info("rpc_start", method="SomeRpc")
        ... do work ...
        logger.info("rpc_end", result="ok")
```

The scope:
- mints a child span from whatever is currently bound (the
  `TraceContextInterceptor` will have bound the upstream parent), or
  a fresh root if nothing is bound;
- binds `trace_id` + `span_id` for the duration of the `with` block;
- restores the previous context on exit (so the interceptor's
  binding survives across multiple per-RPC scopes within one
  connection).

Test the addition by asserting on the captured log records — see
`tests/test_trace_ctx.py::test_child_span_scope_inherits_trace_id_from_parent`
for the canonical pattern.

## Per-frame vs per-handler trade-off (control / heartbeat /
filesystem bidi streams)

The three big bidi streamers don't have a single "RPC handler entry"
— they have one long handler that loops over inbound frames. Two
honest options:

1. **One span per session** (current, by interceptor): inherits the
   parent's span_id for the lifetime of the stream. Easy; bad for
   backends that want to slice by individual frame.
2. **One span per frame**: open `child_span_scope()` inside the
   per-frame loop. Good for fine-grained traces; pays the cost of a
   fresh span_id per frame (cheap) plus the bind/unbind churn (also
   cheap, but worth measuring before promoting).

We adopt option 1 today and keep option 2 as a follow-up to
re-evaluate after the first hardware bring-up makes performance
characteristics measurable.

## Refs

- DEC-0006 — W3C TraceContext mandate.
- FOLLOWUPS.md:355-388 — original observability follow-ups.
- `host/src/crossdesk_host/observability/trace_ctx.py` — primitives
  (`generate_root`, `child_span`, `bind_to_log_context`,
  `child_span_scope`).
- `host/src/crossdesk_host/observability/grpc_interceptor.py` —
  server-wide interceptor that extracts upstream `traceparent`.
- `host/tests/test_smoke_inprocess.py::test_traceparent_propagates_to_all_three_planes`
  — end-to-end assertion that the upstream agent's trace_id appears
  on every plane's host log.
