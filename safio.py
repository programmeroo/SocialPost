# safeio.py — shared safe printing and cross-platform env getter
import os
import sys
import platform


def safe_print(*args, sep=" ", end="\n", file=sys.stdout, flush=False):
    """
    Print text safely even if emojis or non-UTF-8 characters appear.
    On non-Windows systems, falls back to ASCII with replacement when needed.
    """
    system_name = platform.system().lower()

    # Windows handles UTF-8 console output fine (esp. Win10+)
    if "windows" in system_name:
        print(*args, sep=sep, end=end, file=file, flush=flush)
        return

    try:
        print(*args, sep=sep, end=end, file=file, flush=flush)
    except UnicodeEncodeError:
        msg = sep.join(str(a) for a in args)
        safe_msg = msg.encode("ascii", "replace").decode()
        file.write(safe_msg + end)
        if flush:
            file.flush()


def get_env(name: str, default=None):
    """
    Cross-platform environment variable getter.
    On Windows: looks for WIN_<name>
    On Linux/macOS: looks for <name>
    Example:
        # Works on both systems with one .env file
        #   Windows .env → WIN_DROPBOX_APP_KEY=xxxx
        #   Linux  .env → DROPBOX_APP_KEY=xxxx
        val = get_env("DROPBOX_APP_KEY")
    """
    system_name = platform.system().lower()
    env_name = f"WIN_{name}" if "windows" in system_name else name
    return os.getenv(env_name, default)
