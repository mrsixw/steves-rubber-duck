#!/usr/bin/env python3
"""Print the current version from the VERSION file."""


def main() -> None:
    """Print the trimmed contents of VERSION."""

    with open("VERSION", "r") as handle:
        print(handle.read().strip())


if __name__ == "__main__":
    main()
