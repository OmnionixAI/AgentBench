from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any


def canonical_submission_payload(submission: dict[str, Any]) -> bytes:
    verification = dict(submission.get("verification", {}))
    verification.pop("signature", None)
    payload = {
        "submission_id": submission.get("submission_id"),
        "submitted_at": submission.get("submitted_at"),
        "agent": submission.get("agent"),
        "links": submission.get("links"),
        "run": submission.get("run"),
        "verification": verification,
        "benchmark_card": submission.get("benchmark_card"),
    }
    import json
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_submission(submission: dict[str, Any], secret: str, key_id: str = "maintainer") -> dict[str, Any]:
    payload = canonical_submission_payload(submission)
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii")
    verification = dict(submission.get("verification", {}))
    verification["signature"] = {
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "signature": signature,
    }
    signed = dict(submission)
    signed["verification"] = verification
    return signed


def verify_submission(submission: dict[str, Any], secret: str | None) -> tuple[bool, str]:
    signature_block = submission.get("verification", {}).get("signature")
    if not signature_block:
        return False, "unsigned"
    if not secret:
        return False, "missing_verification_key"
    if signature_block.get("algorithm") != "hmac-sha256":
        return False, "unsupported_signature_algorithm"
    payload = canonical_submission_payload(submission)
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    encoded = base64.b64encode(expected).decode("ascii")
    if not hmac.compare_digest(encoded, signature_block.get("signature", "")):
        return False, "signature_mismatch"
    return True, "verified"
