import asyncio

from crossdesk_host.daemon import main
from crossdesk_host.observability import get_logger


def _run() -> None:
    logger = get_logger("host.daemon")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # SIGINT after the signal handler tripped a graceful stop, or a
        # bare Ctrl-C before the loop installed handlers — normal exit.
        logger.info("daemon_interrupted")
    except Exception:
        # Last-resort catchall: without this, an unhandled exception (OOM
        # in a task, a libvirt binding fault, a config surprise) dies with
        # a bare traceback and no structured record, so `crossdesk logs`
        # shows nothing about why the daemon vanished. Log it as a single
        # JSON line, then re-raise so the exit code still signals failure
        # to systemd / the supervisor.
        logger.exception("daemon_crashed")
        raise


if __name__ == "__main__":
    _run()
