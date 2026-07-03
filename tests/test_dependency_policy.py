from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


def test_dev_dependencies_keep_mutmut_on_v2() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    mutmut_requirement = next(
        dependency for dependency in dev_dependencies if dependency.startswith("mutmut")
    )

    assert "<3.0.0" in mutmut_requirement, (
        "mutmut 3.x removed the junitxml output consumed by TQA and mutation.yml; "
        "do not widen this constraint without migrating that integration"
    )
