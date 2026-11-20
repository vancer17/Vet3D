"""Validate a dedicated test config inside the authorized runtime; never echo it."""
from urllib.parse import urlsplit

import yaml


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("MDF3 config must be a mapping")
    if config.get("feishu", {}).get("enabled") is not False:
        raise ValueError("Local test profile requires feishu.enabled=false")
    if config.get("tos") or config.get("kafka"):
        raise ValueError("Use a dedicated test config without TOS/Kafka credentials")
    address = config.get("nacos", {}).get("nacos_server_addresses")
    if not isinstance(address, str) or not address or "<" in address or ">" in address:
        raise ValueError("Missing or unfilled Nacos server address")
    endpoints = config.get("task_queue", {}).get("endpoints")
    if not isinstance(endpoints, list) or not endpoints or any(
            not isinstance(item, str) or not item.startswith(("http://", "https://")) for item in endpoints):
        raise ValueError("task_queue.endpoints must be a nonempty HTTP(S) URL list")
    for endpoint in endpoints:
        try:
            parsed = urlsplit(endpoint)
            valid = parsed.hostname and "<" not in endpoint and ">" not in endpoint and not (
                parsed.username or parsed.password or parsed.query or parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Queue URLs must not embed credentials, queries or fragments")
    heartbeat = config.get("agent_heartbeat", {})
    expected = dict(container_dir="/tmp/mdf-health", heartbeat_filename="heartbeat", ready_filename="ready")
    if any(heartbeat.get(key, value if key != "container_dir" else None) != value for key, value in expected.items()):
        raise ValueError("Heartbeat paths must match the bundled healthcheck")
    interval = heartbeat.get("interval_sec", 5)
    if type(interval) not in (int, float) or not 0 < interval < 15:
        raise ValueError("Heartbeat interval must be in (0, 15) seconds")


def check_config(path):
    try:
        with open(path, encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError):
        # Parser errors may quote private YAML lines; suppress their context.
        raise ValueError("Cannot read or parse the dedicated MDF3 config") from None
    try:
        validate_config(config)
    except (TypeError, AttributeError, OverflowError):
        raise ValueError("Invalid MDF3 config field types") from None
