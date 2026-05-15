import os
from pathlib import Path


_LOADED_ENV_PATHS: set[Path] = set()


def load_env_file(
    path: str | Path | None = None,
    override: bool = False,
) -> None:
    paths = [Path(path)] if path is not None else _find_default_env_files()

    for env_path in paths:
        _load_single_env_file(
            path=env_path,
            override=override,
        )


def _find_default_env_files() -> list[Path]:
    result: list[Path] = []

    for directory in [Path.cwd(), *Path.cwd().parents]:
        env_path = directory / ".env"
        env_local_path = directory / ".env.local"

        if env_path.exists():
            result.append(env_path)

        if env_local_path.exists():
            result.append(env_local_path)

        if (directory / "app").exists():
            break

    return result


def _load_single_env_file(
    path: Path,
    override: bool,
) -> None:
    env_path = path.resolve()

    if env_path in _LOADED_ENV_PATHS:
        return

    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)

        if parsed is None:
            continue

        key, value = parsed

        if override or key not in os.environ:
            os.environ[key] = value

    _LOADED_ENV_PATHS.add(env_path)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()

    if not stripped:
        return None

    if stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        value = value[1:-1]

    return key, value

