"""YAMLRocks loading with the project's existing safe YAML policy."""
from typing import IO

import yamlrocks
from yamlrocks.compat import YAMLError, safe_dump

__all__ = ["YAMLError", "safe_load", "safe_dump"]

_SAFE_TAG_NAMES = (
    "null", "bool", "int", "float", "binary", "timestamp", "omap",
    "pairs", "set", "str", "seq", "map", "merge", "value",
)
_SAFE_TAGS = {
    prefix + name
    for prefix in ("!!", "tag:yaml.org,2002:")
    for name in _SAFE_TAG_NAMES
}


def _validate_tags(node: yamlrocks.YAMLRocksTreeNode | None) -> None:
    pending = [node] if node is not None else []
    while pending:
        current = pending.pop()
        if current.tag is not None and current.tag not in _SAFE_TAGS:
            raise YAMLError(f"Unsupported YAML tag: {current.tag}")
        if current.kind == "mapping":
            for key, value in current.value:
                pending.extend((key, value))
        elif current.kind == "sequence":
            pending.extend(current.value)


def safe_load(stream: str | bytes | IO[str]) -> object:
    """Read one document, preserving legacy scalars and rejecting custom tags."""
    source = stream if isinstance(stream, (str, bytes)) else stream.read()
    # The compatibility loader silently drops unknown standard-namespace tags.
    # Inspect source tags before converting the document to Python values.
    documents = yamlrocks.loads_all(
        source,
        option=(yamlrocks.OPT_PYYAML_COMPAT | yamlrocks.OPT_ROUND_TRIP
                | yamlrocks.OPT_REJECT_COMPLEX_KEYS),
    )
    if len(documents) > 1:
        raise YAMLError("Expected one YAML document")
    if not documents:
        return None
    document = documents[0]
    _validate_tags(document.to_tree())
    return document.to_dict()
