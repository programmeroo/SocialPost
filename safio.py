# safeio.py — shared safe printing and cross-platform env getter
import os
import sys
import platform
from dotenv import load_dotenv

load_dotenv()


def safe_print(*args, sep=" ", end="\n", file=sys.stdout, flush=False):
    """
    Print safely even if args contain None or emojis.
    On non-Windows systems, falls back to ASCII-safe mode.
    """
    system_name = platform.system().lower()

    # Normalize args: convert None -> "None", bytes -> decoded string
    safe_args = []
    for a in args:
        if a is None:
            safe_args.append("None")
        elif isinstance(a, bytes):
            try:
                safe_args.append(a.decode("utf-8", errors="replace"))
            except Exception:
                safe_args.append(str(a))
        else:
            safe_args.append(str(a))

    msg = sep.join(safe_args)

    # Windows prints normally
    if "windows" in system_name:
        print(msg, end=end, file=file, flush=flush)
        return

    try:
        print(msg, end=end, file=file, flush=flush)
    except UnicodeEncodeError:
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
    # safe_print(f"env_name: {env_name}")
    return os.getenv(env_name, default)
