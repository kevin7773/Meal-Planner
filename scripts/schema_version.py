from __future__ import annotations

from collections.abc import Mapping


CURRENT_SCHEMA_VERSION = 1


def schema_version_errors(
    document: object,
    label: str,
    *,
    supported_versions: frozenset[int] = frozenset({CURRENT_SCHEMA_VERSION}),
) -> list[str]:
    if not isinstance(document, Mapping):
        return [f"{label}: document must be a JSON object"]

    if "schema_version" not in document:
        return [f"{label}: schema_version is required"]

    version = document["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        return [f"{label}: schema_version must be an integer"]

    if version not in supported_versions:
        supported = ", ".join(str(item) for item in sorted(supported_versions))
        return [
            f"{label}: unsupported schema_version {version}; "
            f"supported version(s): {supported}"
        ]

    return []
