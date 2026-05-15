import os
from pathlib import Path


_ENV_LOADED = False


def load_project_env(
    filename: str = ".env",
    override: bool = False,
) -> None:
    global _ENV_LOADED

    if _ENV_LOADED:
        return

    env_path = _find_env_file(filename)

    if env_path is None:
        _ENV_LOADED = True
        return

    _load_env_file(env_path, override=override)
    _ENV_LOADED = True


def _find_env_file(filename: str) -> Path | None:
    current = Path.cwd().resolve()

    for path in [current, *current.parents]:
        candidate = path / filename

        if candidate.is_file():
            return candidate

    return None


def _load_env_file(
    path: Path,
    override: bool,
) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_value(value.strip())

        if not key:
            continue

        if override or key not in os.environ:
            os.environ[key] = value


def _clean_value(value: str) -> str:
    if len(value) >= 2:
        if value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]

    return value
