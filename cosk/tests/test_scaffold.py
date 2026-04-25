from __future__ import annotations

import ast
from pathlib import Path
import tomllib


COSK_DIR = Path(__file__).resolve().parents[1]


def test_scaffold_root_files_exist() -> None:
    assert COSK_DIR.exists()
    assert (COSK_DIR / "__init__.py").exists()
    assert (COSK_DIR / "README.md").exists()
    assert (COSK_DIR / "pyproject.toml").exists()


def test_scaffold_subpackages_exist_with_init() -> None:
    for package_name in ("extraction", "indexing", "graph", "mcp", "safety"):
        package_dir = COSK_DIR / package_name
        assert package_dir.exists()
        assert package_dir.is_dir()
        assert (package_dir / "__init__.py").exists()


def test_pyproject_declares_required_metadata() -> None:
    pyproject = tomllib.loads((COSK_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["name"] == "cosk"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.11"


def test_pyproject_declares_required_dependency_names() -> None:
    pyproject = tomllib.loads((COSK_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    dependency_names = {
        dependency.split(";", maxsplit=1)[0].strip().split("[", maxsplit=1)[0].split("<", maxsplit=1)[0]
        .split(">", maxsplit=1)[0]
        .split("=", maxsplit=1)[0]
        .strip()
        for dependency in dependencies
    }

    assert {"tree-sitter", "lancedb", "networkx", "sentence-transformers", "mcp"}.issubset(dependency_names)


def test_init_files_are_docstring_only_or_empty() -> None:
    init_files = [
        COSK_DIR / "__init__.py",
        COSK_DIR / "extraction" / "__init__.py",
        COSK_DIR / "indexing" / "__init__.py",
        COSK_DIR / "graph" / "__init__.py",
        COSK_DIR / "mcp" / "__init__.py",
        COSK_DIR / "safety" / "__init__.py",
    ]

    for init_file in init_files:
        parsed = ast.parse(init_file.read_text(encoding="utf-8"))
        body = parsed.body

        if not body:
            continue

        assert len(body) == 1
        only_statement = body[0]
        assert isinstance(only_statement, ast.Expr)
        assert isinstance(only_statement.value, ast.Constant)
        assert isinstance(only_statement.value.value, str)
