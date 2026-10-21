"""Partial ownership of Hermes Desktop's v2 connection registry.

Only public connection metadata is managed. Authentication remains machine-local.
Unknown registry fields, other connections, and same-host credentials survive.
"""
from copy import deepcopy


def merge_connections(live, managed):
    if not isinstance(live, dict):
        raise ValueError("Hermes registry must be an object")
    if live and live.get("version") != 2:
        raise ValueError("Unsupported Hermes registry version; refusing to replace it")
    if set(managed) != {"version", "primary", "launchMode", "connections"} or managed["version"] != 2:
        raise ValueError("Invalid managed Hermes registry")
    allowed = {"id", "kind", "label", "url", "authMode"}
    for entry in managed["connections"]:
        if set(entry) != allowed or entry["kind"] != "remote" or entry["authMode"] != "oauth":
            raise ValueError("Managed Hermes connections must contain only OAuth metadata")

    result = deepcopy(live) if live else {
        "version": 2,
        "lastUsed": "local",
        "connections": [{"id": "local", "kind": "local", "label": "This device"}],
    }
    entries = result.get("connections")
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not e.get("id") for e in entries):
        raise ValueError("Invalid Hermes connections; refusing to replace them")
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Hermes connection ids")

    for desired in managed["connections"]:
        existing = next((e for e in entries if e["id"] == desired["id"]), None)
        if existing is not None:
            # Never transfer authentication material to another endpoint or source.
            if existing.get("kind") != desired["kind"] or existing.get("url", "").rstrip("/") != desired["url"].rstrip("/"):
                raise ValueError("Managed Hermes id belongs to another endpoint; resolve it in the app first")
        if any(e["id"] != desired["id"] and e.get("label", "").casefold() == desired["label"].casefold() for e in entries):
            raise ValueError("Managed Hermes label conflicts with another connection")
        if existing is None:
            entries.append(deepcopy(desired))
        else:
            existing.update(desired)

    result["primary"] = managed["primary"]
    result["launchMode"] = managed["launchMode"]
    return result
