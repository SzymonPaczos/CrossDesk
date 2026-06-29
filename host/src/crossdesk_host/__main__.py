import asyncio

from crossdesk_host.daemon import main
from crossdesk_host.observability import get_logger


def _maybe_write_crash_report(exc: BaseException) -> None:
    """Best-effort opt-in crash report for a daemon crash (default OFF).

    Never raises — a failure here must not shadow the original crash on
    its way to systemd / the supervisor.
    """
    try:
        from crossdesk_host.config import load_from_toml
        from crossdesk_host.observability import report_exception

        cfg = load_from_toml()
        path = report_exception(
            exc,
            component="host.daemon",
            command=["crossdesk-host"],
            host_version=cfg.daemon.host_version,
            enabled=cfg.observability.crash_report_enabled,
            report_dir=cfg.paths.state_dir / "crash-reports",
        )
        if path is not None:
            get_logger("host.daemon").info("crash_report_written")
    except Exception:  # noqa: BLE001 - reporting must never mask the crash
        pass


def _run() -> None:
    logger = get_logger("host.daemon")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # SIGINT after the signal handler tripped a graceful stop, or a
        # bare Ctrl-C before the loop installed handlers — normal exit.
        logger.info("daemon_interrupted")
    except Exception as exc:
        # Last-resort catchall: without this, an unhandled exception (OOM
        # in a task, a libvirt binding fault, a config surprise) dies with
        # a bare traceback and no structured record, so `crossdesk logs`
        # shows nothing about why the daemon vanished. Log it as a single
        # JSON line, write an opt-in crash report, then re-raise so the
        # exit code still signals failure to systemd / the supervisor.
        logger.exception("daemon_crashed")
        _maybe_write_crash_report(exc)
        raise


if __name__ == "__main__":
    _run()
