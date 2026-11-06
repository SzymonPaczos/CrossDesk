#!/usr/bin/env python3
"""Two heavy-run slots, identified by PID and start time; unknown liveness refuses reuse.

Class locks must precede slots. Release the slot before waiting for another class.
State uses GATE_STATE_DIR or ${XDG_STATE_HOME:-~/.local/state}/local-gates.
Only an owned, non-symlink directory with mode 700 is accepted. A slot token is
valid only for the same live process or its descendants. SIGKILL can orphan a
wrapper's children: the supervising verifier must stop its group before exiting.
"""
import argparse
import fcntl
import os
import signal
import stat
import subprocess
import sys
import time

MAX_BYTES = 512
DEFAULT_SLOTS = 2
LOCK_WAIT_SECONDS = 10


class Refused(Exception):
    """The state cannot be used; the message says what and how to recover (one line)."""


class PsFailed(Refused):
    """`ps` could not say whether a process exists. Not the same as "it does not": a slot is never
    reclaimed on the strength of a failed `ps`, so a broken `ps` cannot free the slot of a live run."""


def config():
    """Environment selects private state, while the machine-wide capacity remains two."""
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    directory = os.environ.get("GATE_STATE_DIR") or os.path.join(base, "local-gates")
    parent = os.path.dirname(os.path.abspath(directory))
    os.makedirs(parent, mode=0o700, exist_ok=True)
    return directory, DEFAULT_SLOTS


def ps_field(field, pid):
    """What `LC_ALL=C ps -o FIELD= -p PID` prints, or '' when there is no such process (status 1, nothing
    on stdout, and nothing on stderr or the "too large" complaint for a PID beyond the range). Any other
    outcome (ps cannot be run, times out, another status, an error text) raises PsFailed."""
    try:
        done = subprocess.run(["ps", "-o", f"{field}=", "-p", str(pid)], capture_output=True, text=True,
                              env={"LC_ALL": "C", "PATH": "/bin:/usr/bin"}, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise PsFailed(f"ps could not be run to look at process {pid} ({type(err).__name__}); "
                       "nothing is taken or reclaimed until it works")
    text = done.stdout.strip()
    if done.returncode == 0:
        return text
    complaint = done.stderr.strip()
    if done.returncode == 1 and not text and (not complaint or "too large" in complaint):
        return ""
    raise PsFailed(f"ps ended with status {done.returncode} looking at process {pid} "
                   f"({clean_text(complaint, 80) or 'no message'}); nothing is taken or reclaimed until it works")


def lstart_of(pid):
    """The start time of PID as ps prints it, '' when there is no such process; PsFailed when ps cannot say."""
    return ps_field("lstart", pid)


def parent_of(pid):
    text = ps_field("ppid", pid)
    return int(text) if text.isdigit() else 0


def recovery(directory):
    return (f"when no wrapper, hook or push is running: rm -rf {directory}; the next run makes it again "
            f"(heavy-slot.py status shows who holds what)")


def open_state(directory, create):
    """fd of the state directory: ours, not a link, mode 700. Raises Refused for anything else."""
    if create:
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            pass
        except OSError as err:
            raise Refused(f"cannot create {directory}: {err.strerror}; {recovery(directory)}")
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as err:
        raise Refused(f"{directory} is not a usable directory (a link counts): {err.strerror}; {recovery(directory)}")
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid():
            raise Refused(f"{directory} belongs to another user; {recovery(directory)}")
        if stat.S_IMODE(info.st_mode) != 0o700:
            raise Refused(f"{directory} is mode {stat.S_IMODE(info.st_mode):o}, not 700; "
                          f"chmod 700 {directory} or {recovery(directory)}")
        return fd
    except BaseException:
        os.close(fd)
        raise


def lock_state(dir_fd, directory):
    """Takes flock on `lock` in the directory (waits at most LOCK_WAIT_SECONDS) and returns its fd."""
    fd = None
    for attempt in range(100):
        try:
            fd = os.open("lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dir_fd)
            break
        except FileNotFoundError:
            # Two processes creating the file for the first time at once: on APFS one of them can be
            # told ENOENT for a name the other has just made (measured with two parallel first calls).
            time.sleep(0.01)
        except OSError as err:
            raise Refused(f"{directory}/lock cannot be opened: {err.strerror}; {recovery(directory)}")
    if fd is None:
        raise Refused(f"{directory}/lock cannot be opened: no such file after 100 tries; {recovery(directory)}")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise Refused(f"{directory}/lock is not a regular file of ours; {recovery(directory)}")
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except OSError:
                if time.monotonic() >= deadline:
                    raise Refused(f"{directory}/lock is held for over {LOCK_WAIT_SECONDS} s by another heavy-slot.py")
                time.sleep(0.02)
    except BaseException:
        os.close(fd)
        raise


def slot_name(index):
    return f"slot-{index}"


def read_slot(dir_fd, index, directory):
    """('free', None), ('held', {pid, lstart, cls, desc, mtime}) or ('garbage', None) for a regular file
    of ours that does not parse. Raises Refused for a link, a FIFO, a directory or a file of another
    user: whatever stands there is not ours to read or remove."""
    name = slot_name(index)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return "free", None
    except OSError as err:
        raise Refused(f"{directory}/{name} cannot be opened ({err.strerror}); it is not a slot of ours; "
                      f"{recovery(directory)}")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise Refused(f"{directory}/{name} is not a regular file of ours; {recovery(directory)}")
        data = os.read(fd, MAX_BYTES + 1)
    except OSError as err:
        raise Refused(f"{directory}/{name} cannot be read: {err.strerror}; {recovery(directory)}")
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES:
        return "garbage", None
    lines = data.decode("utf-8", "replace").split("\n")
    if len(lines) < 5 or lines[-1] != "" or not lines[0].isdigit() or not lines[1]:
        return "garbage", None
    return "held", {"pid": int(lines[0]), "lstart": lines[1], "cls": lines[2], "desc": lines[3],
                    "mtime": info.st_mtime}


def is_live(holder):
    """True/False by ps; PsFailed (not False) when ps cannot say."""
    return bool(holder["lstart"]) and lstart_of(holder["pid"]) == holder["lstart"]


def remove_slot(dir_fd, index):
    try:
        os.unlink(slot_name(index), dir_fd=dir_fd)
    except FileNotFoundError:
        pass


def clean_text(text, limit):
    return " ".join(text.split())[:limit]


def cmd_try(holder_pid, cls, desc):
    directory, slots = config()
    holder_start = lstart_of(holder_pid)
    if not holder_start:
        raise Refused(f"holder process {holder_pid} does not exist")
    dir_fd = open_state(directory, create=True)
    try:
        lock_fd = lock_state(dir_fd, directory)
        try:
            return _claim(dir_fd, directory, slots, holder_pid, holder_start, cls, desc)
        finally:
            os.close(lock_fd)
    finally:
        os.close(dir_fd)


def _claim(dir_fd, directory, slots, holder_pid, holder_start, cls, desc):
    chosen = None
    for index in range(slots):
        state, holder = read_slot(dir_fd, index, directory)
        if state == "held" and is_live(holder):
            continue
        if state != "free":
            remove_slot(dir_fd, index)  # a dead holder, or what a killed writer left
        chosen = index
        break
    if chosen is None:
        return 1
    content = f"{holder_pid}\n{holder_start}\n{clean_text(cls, 40)}\n{clean_text(desc, 120)}\n".encode("utf-8")
    name = slot_name(chosen)
    committed = created = False
    signals = {signal.SIGTERM, signal.SIGHUP, signal.SIGINT}
    try:
        # The file and the flag that says it exists change together: a signal between the two
        # would leave a slot nobody removes.
        signal.pthread_sigmask(signal.SIG_BLOCK, signals)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
            created = True
        except OSError as err:
            raise Refused(f"cannot create {directory}/{name}: {err.strerror}; {recovery(directory)}")
        finally:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, signals)
        try:
            view = memoryview(content)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
        sys.stdout.write(f"{chosen}:{holder_pid}:{holder_start}\n")
        sys.stdout.flush()
        committed = True
        # From here the token is out: a signal must not take the slot back.
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, signal.SIG_IGN)
        return 0
    except OSError as err:
        raise Refused(f"cannot write {directory}/{name}: {err.strerror}; {recovery(directory)}")
    finally:
        if created and not committed:
            remove_slot(dir_fd, chosen)


def cmd_release(holder_pid):
    directory, slots = config()
    holder_start = lstart_of(holder_pid)
    if not holder_start:
        return 0  # a process that is gone holds nothing it could give back; its slot is freed on read
    try:
        dir_fd = open_state(directory, create=False)
    except Refused as err:
        if not os.path.lexists(directory):
            return 0
        raise err
    try:
        lock_fd = lock_state(dir_fd, directory)
        try:
            for index in range(slots):
                state, holder = read_slot(dir_fd, index, directory)
                if state == "held" and holder["pid"] == holder_pid and holder["lstart"] == holder_start:
                    remove_slot(dir_fd, index)
        finally:
            os.close(lock_fd)
    finally:
        os.close(dir_fd)
    return 0


def parse_token(token):
    parts = token.split(":", 2)
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit() or not parts[2]:
        return None
    return int(parts[0]), int(parts[1]), parts[2]


def is_self_or_ancestor(pid):
    current, steps = os.getpid(), 0
    while steps < 64 and current > 1:
        if current == pid:
            return True
        current = parent_of(current)
        steps += 1
    return False


def cmd_check(token):
    parsed = parse_token(token)
    if parsed is None:
        return 1
    index, pid, lstart = parsed
    directory, slots = config()
    if index >= slots:
        return 1
    try:
        dir_fd = open_state(directory, create=False)
    except Refused:
        return 1
    try:
        state, holder = read_slot(dir_fd, index, directory)
    except Refused:
        return 1
    finally:
        os.close(dir_fd)
    if state != "held" or holder["pid"] != pid or holder["lstart"] != lstart:
        return 1
    if lstart_of(pid) != lstart or not is_self_or_ancestor(pid):
        return 1
    return 0


def holders(directory, slots):
    """[(index, 'free'|'live'|'dead'|'unknown'|'garbage', holder)] for a person; read-only. 'unknown' is a
    held slot whose holder ps could not be asked about."""
    out = []
    try:
        dir_fd = open_state(directory, create=False)
    except Refused as err:
        if not os.path.lexists(directory):
            return [(i, "free", None) for i in range(slots)]
        raise err
    try:
        for index in range(slots):
            state, holder = read_slot(dir_fd, index, directory)
            if state == "held":
                try:
                    state = "live" if is_live(holder) else "dead"
                except PsFailed:
                    state = "unknown"
            out.append((index, state, holder))
    finally:
        os.close(dir_fd)
    return out


def age_of(holder):
    return max(0, int(time.time() - holder["mtime"]))


def cmd_status():
    directory, slots = config()
    print(f"heavy slots in {directory}: {slots}")
    for index, state, holder in holders(directory, slots):
        if state == "free":
            print(f"slot {index}: free")
        elif state == "garbage":
            print(f"slot {index}: a file that does not parse (a writer was killed); the next run removes it")
        elif state == "unknown":
            print(f"slot {index}: held by pid {holder['pid']}, class {holder['cls']}, {holder['desc']}; ps cannot say "
                  f"whether it is alive, so the slot is kept")
        elif state == "live":
            print(f"slot {index}: held by live pid {holder['pid']} (started {holder['lstart']}), class "
                  f"{holder['cls']}, {holder['desc']}, {age_of(holder)} s")
        else:
            print(f"slot {index}: holder pid {holder['pid']} is gone or reused, class {holder['cls']}; "
                  f"free for the next run, {age_of(holder)} s old")
    return 0


def cmd_describe():
    directory, slots = config()
    parts = []
    for index, state, holder in holders(directory, slots):
        if state == "live":
            parts.append(f"held by live pid {holder['pid']} (class {holder['cls']}, {holder['desc']}, "
                         f"{age_of(holder)} s)")
        elif state == "unknown":
            parts.append(f"slot {index} is held by pid {holder['pid']} (ps cannot say whether it is alive)")
        elif state in ("dead", "garbage", "free"):
            parts.append(f"slot {index} is free" if state == "free" else f"slot {index} looks orphaned")
    print("; ".join(parts))
    return 0


def on_signal(signum, _frame):
    raise SystemExit(128 + signum)


def front_file():
    """The class uses flock, not a removable mkdir lock; all adopters must agree."""
    directory = os.environ.get("GATE_LOCK_DIR") or f"/tmp/local-gates-{os.geteuid()}"
    fd = open_state(directory, create=True)
    try:
        lock = os.open("frontend.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=fd)
    finally:
        os.close(fd)
    info = os.fstat(lock)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        os.close(lock)
        raise Refused("zamek frontu nie jest zwykłym plikiem bieżącego użytkownika")
    return lock


def front_check(token):
    try:
        pid, started = token.split(":", 1)
        if not pid.isdigit() or not is_self_or_ancestor(int(pid)) or lstart_of(int(pid)) != started:
            return 1
        fd = front_file()
        try:
            if os.read(fd, MAX_BYTES).decode() != token:
                return 1
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            return 1
        finally:
            os.close(fd)
    except (ValueError, OSError, Refused):
        return 1


def stop_group(child):
    """Wait for git and terminate remaining group members before returning resources."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        # A finished leader can leave children in the group; KILL still follows TERM.
    child.wait()


def push(args):
    if not os.path.isdir(".git") or os.path.islink(".git"):
        sys.stderr.write("push-locked: wymagany katalog głównego drzewa; worktree jest zabronione\n")
        return 1
    if os.environ.get("GATE_HEAVY_SLOT"):
        raise Refused("push musi rozpocząć się bez slotu; najpierw bierze zamek klasy")
    fd = front_file()
    child = None
    attempted = False
    try:
        maximum = int(os.environ.get("GATE_MAX_WAIT_SECONDS", "3600"))
        if maximum < 0:
            raise Refused("GATE_MAX_WAIT_SECONDS musi być nieujemne")
        deadline = time.monotonic() + maximum if maximum else float("inf")
        noted = False
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not noted:
                    sys.stderr.write("push-locked: oczekiwanie na zamek frontu\n")
                    noted = True
                if time.monotonic() >= deadline:
                    return 124
                time.sleep(0.1)
        token = f"{os.getpid()}:{lstart_of(os.getpid())}"
        os.ftruncate(fd, 0)
        os.write(fd, token.encode())
        while True:
            attempted = True
            # Claim in a helper: its post-commit signal policy must not affect the supervisor.
            result = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "try",
                                     "--holder", str(os.getpid()), "--class", "frontend",
                                     "--desc", "push"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                break
            if result.returncode != 1:
                raise Refused(result.stderr.strip() or "pomocnik odmówił przydziału slotu")
            if time.monotonic() >= deadline:
                return 124
            time.sleep(0.1)
        env = {**os.environ, "GATE_FRONT_LOCK": token, "GATE_HEAVY_SLOT": result.stdout.strip()}
        child = subprocess.Popen(["git", "push", *args], env=env, start_new_session=True)
        rc = child.wait()
        return rc if rc >= 0 else 128 - rc
    finally:
        # Ignore repeated signals during cleanup so no group outlives its slot.
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        try:
            if child is not None:
                stop_group(child)
            if attempted:
                cmd_release(os.getpid())
        finally:
            os.close(fd)


def main(argv):
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, on_signal)
    if len(argv) > 1 and argv[1] in ("push", "front-check"):
        try:
            if argv[1] == "push":
                return push(argv[2:])
            return front_check(argv[3]) if len(argv) == 4 and argv[2] == "--token" else 1
        except (Refused, OSError, ValueError) as err:
            sys.stderr.write(f"local-gates: {err}\n")
            return 3
    parser = argparse.ArgumentParser(prog="heavy-slot.py", add_help=False)
    sub = parser.add_subparsers(dest="cmd")
    p_try = sub.add_parser("try")
    p_try.add_argument("--holder", type=int, required=True)
    p_try.add_argument("--class", dest="cls", required=True)
    p_try.add_argument("--desc", default="")
    p_release = sub.add_parser("release")
    p_release.add_argument("--holder", type=int, required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("--token", required=True)
    sub.add_parser("status")
    sub.add_parser("describe")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        sys.stderr.write("usage: heavy-slot.py try --holder PID --class C --desc T | release --holder PID | "
                         "check --token T | status | describe\n")
        return 2
    if args.cmd is None:
        sys.stderr.write("usage: heavy-slot.py try|release|check|status|describe ...\n")
        return 2
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, on_signal)
    try:
        if args.cmd == "try":
            return cmd_try(args.holder, args.cls, args.desc)
        if args.cmd == "release":
            return cmd_release(args.holder)
        if args.cmd == "check":
            return cmd_check(args.token)
        if args.cmd == "status":
            return cmd_status()
        return cmd_describe()
    except Refused as err:
        sys.stderr.write(f"heavy-slot: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
