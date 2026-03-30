"""Decoy tool generator — plausible but irrelevant tools to pad the MCP manifest.

Used to measure Tool-Selection Entropy: can the agent ignore noise and pick
the correct tool when 50+ tools are available?
"""

from __future__ import annotations

from typing import Any

from agentbench.transport.protocol import MCPToolRegistry


_DECOY_SPECS: list[dict[str, Any]] = [
    {"name": "convert_currency", "description": "Convert an amount from one currency to another using live exchange rates.", "input_schema": {"type": "object", "properties": {"amount": {"type": "number"}, "from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["amount", "from_currency", "to_currency"]}},
    {"name": "translate_text", "description": "Translate text from one language to another.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "source_lang": {"type": "string"}, "target_lang": {"type": "string"}}, "required": ["text", "target_lang"]}},
    {"name": "generate_qr_code", "description": "Generate a QR code image from a URL or text string.", "input_schema": {"type": "object", "properties": {"data": {"type": "string"}, "size": {"type": "integer"}}, "required": ["data"]}},
    {"name": "compress_image", "description": "Compress an image file, reducing its size while preserving quality.", "input_schema": {"type": "object", "properties": {"image_path": {"type": "string"}, "quality": {"type": "integer"}}, "required": ["image_path"]}},
    {"name": "send_email", "description": "Send an email via SMTP to the specified recipient.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}},
    {"name": "generate_password", "description": "Generate a cryptographically secure random password.", "input_schema": {"type": "object", "properties": {"length": {"type": "integer"}, "include_symbols": {"type": "boolean"}}, "required": ["length"]}},
    {"name": "get_weather", "description": "Get current weather conditions for a location.", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}},
    {"name": "calculate_bmi", "description": "Calculate Body Mass Index from height and weight.", "input_schema": {"type": "object", "properties": {"height_cm": {"type": "number"}, "weight_kg": {"type": "number"}}, "required": ["height_cm", "weight_kg"]}},
    {"name": "shorten_url", "description": "Create a shortened URL from a long URL.", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "validate_json", "description": "Check whether a given string is valid JSON.", "input_schema": {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}},
    {"name": "dns_lookup", "description": "Perform a DNS lookup for a domain name.", "input_schema": {"type": "object", "properties": {"domain": {"type": "string"}, "record_type": {"type": "string"}}, "required": ["domain"]}},
    {"name": "base64_encode", "description": "Encode a string to base64.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "base64_decode", "description": "Decode a base64-encoded string.", "input_schema": {"type": "object", "properties": {"encoded": {"type": "string"}}, "required": ["encoded"]}},
    {"name": "hash_text", "description": "Compute a SHA-256 hash of the given text.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "format_date", "description": "Convert a date string between different formats.", "input_schema": {"type": "object", "properties": {"date": {"type": "string"}, "input_format": {"type": "string"}, "output_format": {"type": "string"}}, "required": ["date", "output_format"]}},
    {"name": "generate_uuid", "description": "Generate a new UUID v4.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "ip_geolocation", "description": "Get geographic location data for an IP address.", "input_schema": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
    {"name": "text_to_speech", "description": "Convert text to a speech audio file.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "voice": {"type": "string"}}, "required": ["text"]}},
    {"name": "ocr_image", "description": "Extract text from an image using optical character recognition.", "input_schema": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}},
    {"name": "sentiment_analysis", "description": "Analyze the sentiment of a text passage.", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "regex_match", "description": "Test a regular expression pattern against input text.", "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "text": {"type": "string"}}, "required": ["pattern", "text"]}},
    {"name": "json_to_csv", "description": "Convert a JSON array to CSV format.", "input_schema": {"type": "object", "properties": {"json_data": {"type": "string"}}, "required": ["json_data"]}},
    {"name": "csv_to_json", "description": "Convert CSV data to a JSON array.", "input_schema": {"type": "object", "properties": {"csv_data": {"type": "string"}}, "required": ["csv_data"]}},
    {"name": "markdown_to_html", "description": "Convert Markdown text to HTML.", "input_schema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]}},
    {"name": "calculate_distance", "description": "Calculate the great-circle distance between two geographic coordinates.", "input_schema": {"type": "object", "properties": {"lat1": {"type": "number"}, "lon1": {"type": "number"}, "lat2": {"type": "number"}, "lon2": {"type": "number"}}, "required": ["lat1", "lon1", "lat2", "lon2"]}},
    {"name": "color_converter", "description": "Convert colors between HEX, RGB, and HSL formats.", "input_schema": {"type": "object", "properties": {"color": {"type": "string"}, "to_format": {"type": "string"}}, "required": ["color", "to_format"]}},
    {"name": "cron_parser", "description": "Parse a cron expression and return the next N execution times.", "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}, "count": {"type": "integer"}}, "required": ["expression"]}},
    {"name": "diff_text", "description": "Compute a unified diff between two text strings.", "input_schema": {"type": "object", "properties": {"text_a": {"type": "string"}, "text_b": {"type": "string"}}, "required": ["text_a", "text_b"]}},
    {"name": "whois_lookup", "description": "Perform a WHOIS lookup for a domain.", "input_schema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "pdf_extract_text", "description": "Extract text content from a PDF file.", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
]


def _decoy_handler(args: dict) -> Any:
    return {"status": "not_applicable", "message": "This tool is not relevant to the current task."}


def generate_decoy_tools(registry: MCPToolRegistry, count: int | None = None) -> list[str]:
    """Register *count* decoy tools into *registry*.  Returns the names added."""
    specs = _DECOY_SPECS[:count] if count is not None else _DECOY_SPECS
    names: list[str] = []
    for spec in specs:
        if not registry.has_tool(spec["name"]):
            registry.register_simple(
                name=spec["name"],
                description=spec["description"],
                handler=_decoy_handler,
                input_schema=spec.get("input_schema"),
            )
            names.append(spec["name"])
    return names
