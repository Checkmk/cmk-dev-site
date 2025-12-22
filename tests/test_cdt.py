import tomllib
from pathlib import Path

from cmk_dev_site.cmk_dev_tool import get_all_tools


def _load_pyproject_scripts() -> dict[str, str]:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["scripts"]


def _extract_tool_name(script_name: str) -> str | None:
    """Extract tool name from cmk-dev-* script names.

    Examples:
        cmk-dev-install -> install
        cmk-dev-site -> site
        cmk-dev-install-site -> install-site
        cmk-dev-site-mock-auth -> site-mock-auth
    """
    if not script_name.startswith("cmk-dev-"):
        return None
    # Remove the cmk-dev- prefix
    return script_name[8:]


def test_wrapper_includes_all_entrypoints() -> None:
    """Test that cmk-dev wrapper includes all cmk-dev-* entrypoints."""
    pyproject_scripts = _load_pyproject_scripts()
    wrapper_tools = get_all_tools()

    # Filter to only cmk-dev-* scripts (excluding the wrapper itself)
    cmk_dev_scripts = {
        name: entry
        for name, entry in pyproject_scripts.items()
        if name.startswith("cmk-dev-") and name != "cdt"
    }

    # Extract expected tool names from entrypoints
    expected_tools: set[str] = set()
    for script_name in cmk_dev_scripts:
        tool_name = _extract_tool_name(script_name)
        if tool_name:
            expected_tools.add(tool_name)

    # Get actual tools from wrapper
    actual_tools = set(wrapper_tools.keys())

    # Assert all entrypoints are wrapped
    missing_tools: set[str] = expected_tools - actual_tools
    extra_tools = actual_tools - expected_tools

    assert not missing_tools, f"Wrapper missing tools: {missing_tools}"
    assert not extra_tools, f"Wrapper has unexpected tools: {extra_tools}"
