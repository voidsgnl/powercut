from pathlib import Path

import pytest


def make_supply(root: Path, name: str, **files: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    for fname, content in files.items():
        (d / fname).write_text(content + "\n")


@pytest.fixture
def sysfs(tmp_path):
    root = tmp_path / "power_supply"
    root.mkdir()
    return root


@pytest.fixture
def supply():
    return make_supply
