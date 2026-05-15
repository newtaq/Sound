import subprocess
import sys


TEST_MODULES = [
    "scripts.test_groq_provider_capabilities",
    "scripts.test_groq_native_stream",
    "scripts.test_groq_vision",
    "scripts.test_groq_vision_stream",
    "scripts.test_groq_search_tool",
]


def main() -> None:
    failed: list[str] = []

    for module_name in TEST_MODULES:
        print()
        print("=" * 80)
        print(module_name)
        print("=" * 80)

        result = subprocess.run(
            [sys.executable, "-m", module_name],
            check=False,
        )

        if result.returncode != 0:
            failed.append(module_name)

    print()
    print("=" * 80)
    print("GROQ PACKAGE RESULT")
    print("=" * 80)

    if failed:
        print("failed:")
        for module_name in failed:
            print(f"- {module_name}")

        raise SystemExit(1)

    print("ok")


if __name__ == "__main__":
    main()
