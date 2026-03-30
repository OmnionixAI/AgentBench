"""Mock Slack MCP server backed by in-memory state."""

from __future__ import annotations

import random
from typing import Any

from agentbench.transport.protocol import MCPToolRegistry


class SlackServer:
    """In-memory Slack workspace simulator with MCP-registered tool handlers."""

    def __init__(self, seed: int = 42) -> None:
        rng = random.Random(seed)
        self._channels: list[dict[str, Any]] = [
            {"id": f"C{i:04d}", "name": name, "topic": f"Topic for #{name}", "members": rng.randint(3, 50)}
            for i, name in enumerate(["general", "engineering", "incidents", "deployments", "random", "support", "announcements"], start=1)
        ]
        self._users: list[dict[str, Any]] = [
            {"id": f"U{i:04d}", "name": name, "real_name": name.title(), "status": rng.choice(["active", "away"])}
            for i, name in enumerate(["alice", "bob", "carol", "dave", "eve", "frank", "grace"], start=1)
        ]
        self._messages: list[dict[str, Any]] = []
        self._next_ts = 1000
        self._operation_log: list[dict[str, Any]] = []

    @property
    def operation_log(self) -> list[dict[str, Any]]:
        return list(self._operation_log)

    def _log(self, op: str, **kwargs: Any) -> None:
        self._operation_log.append({"operation": op, **kwargs})

    def _ts(self) -> str:
        self._next_ts += 1
        return f"17000{self._next_ts:05d}.000000"

    def register(self, registry: MCPToolRegistry) -> None:
        registry.register_simple("slack_send_message", "Send a message to a Slack channel.", self._send_message, {"type": "object", "properties": {"channel": {"type": "string"}, "text": {"type": "string"}}, "required": ["channel", "text"]})
        registry.register_simple("slack_list_channels", "List all channels in the workspace.", self._list_channels, {"type": "object", "properties": {}})
        registry.register_simple("slack_create_channel", "Create a new Slack channel.", self._create_channel, {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]})
        registry.register_simple("slack_archive_channel", "Archive a Slack channel by ID.", self._archive_channel, {"type": "object", "properties": {"channel_id": {"type": "string"}}, "required": ["channel_id"]})
        registry.register_simple("slack_invite_user", "Invite a user to a channel.", self._invite_user, {"type": "object", "properties": {"channel_id": {"type": "string"}, "user_id": {"type": "string"}}, "required": ["channel_id", "user_id"]})
        registry.register_simple("slack_upload_file", "Upload a file to a channel.", self._upload_file, {"type": "object", "properties": {"channel": {"type": "string"}, "filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["channel", "filename", "content"]})
        registry.register_simple("slack_add_reaction", "Add an emoji reaction to a message.", self._add_reaction, {"type": "object", "properties": {"channel": {"type": "string"}, "timestamp": {"type": "string"}, "emoji": {"type": "string"}}, "required": ["channel", "timestamp", "emoji"]})
        registry.register_simple("slack_search_messages", "Search messages across the workspace.", self._search_messages, {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
        registry.register_simple("slack_set_topic", "Set the topic for a channel.", self._set_topic, {"type": "object", "properties": {"channel_id": {"type": "string"}, "topic": {"type": "string"}}, "required": ["channel_id", "topic"]})
        registry.register_simple("slack_list_users", "List all users in the workspace.", self._list_users, {"type": "object", "properties": {}})
        registry.register_simple("slack_get_user_info", "Get detailed information about a user by ID.", self._get_user_info, {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]})
        registry.register_simple("slack_get_thread_replies", "Get replies to a specific message thread.", self._get_thread_replies, {"type": "object", "properties": {"channel": {"type": "string"}, "thread_ts": {"type": "string"}}, "required": ["channel", "thread_ts"]})
        registry.register_simple("slack_set_status", "Set the status of the authenticated user.", self._set_status, {"type": "object", "properties": {"text": {"type": "string"}, "emoji": {"type": "string"}}, "required": ["text"]})
        registry.register_simple("slack_pin_message", "Pin a message in a channel.", self._pin_message, {"type": "object", "properties": {"channel": {"type": "string"}, "timestamp": {"type": "string"}}, "required": ["channel", "timestamp"]})
        registry.register_simple("slack_get_channel_history", "Get recent messages from a channel.", self._get_channel_history, {"type": "object", "properties": {"channel": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["channel"]})

    def _send_message(self, args: dict) -> Any:
        ts = self._ts()
        msg = {"channel": args["channel"], "text": args["text"], "ts": ts, "user": "bot"}
        self._messages.append(msg)
        self._log("send_message", channel=args["channel"], ts=ts)
        return {"ok": True, "ts": ts}

    def _list_channels(self, args: dict) -> Any:
        self._log("list_channels")
        return {"channels": self._channels}

    def _create_channel(self, args: dict) -> Any:
        ch = {"id": f"C{len(self._channels) + 1:04d}", "name": args["name"], "topic": "", "members": 1}
        self._channels.append(ch)
        self._log("create_channel", name=args["name"])
        return {"ok": True, "channel": ch}

    def _archive_channel(self, args: dict) -> Any:
        self._log("archive_channel", channel_id=args["channel_id"])
        return {"ok": True}

    def _invite_user(self, args: dict) -> Any:
        self._log("invite_user", channel_id=args["channel_id"], user_id=args["user_id"])
        return {"ok": True}

    def _upload_file(self, args: dict) -> Any:
        self._log("upload_file", channel=args["channel"], filename=args["filename"])
        return {"ok": True, "file": {"name": args["filename"], "size": len(args["content"])}}

    def _add_reaction(self, args: dict) -> Any:
        self._log("add_reaction", channel=args["channel"], ts=args["timestamp"], emoji=args["emoji"])
        return {"ok": True}

    def _search_messages(self, args: dict) -> Any:
        query = args["query"]
        self._log("search_messages", query=query)
        matches = [m for m in self._messages if query.lower() in m.get("text", "").lower()]
        return {"ok": True, "messages": matches}

    def _set_topic(self, args: dict) -> Any:
        self._log("set_topic", channel_id=args["channel_id"], topic=args["topic"])
        for ch in self._channels:
            if ch["id"] == args["channel_id"]:
                ch["topic"] = args["topic"]
                return {"ok": True, "channel": ch}
        raise ValueError(f"Channel not found: {args['channel_id']}")

    def _list_users(self, args: dict) -> Any:
        self._log("list_users")
        return {"users": self._users}

    def _get_user_info(self, args: dict) -> Any:
        user_id = args["user_id"]
        self._log("get_user_info", user_id=user_id)
        for u in self._users:
            if u["id"] == user_id:
                return {"user": u}
        raise ValueError(f"User not found: {user_id}")

    def _get_thread_replies(self, args: dict) -> Any:
        self._log("get_thread_replies", channel=args["channel"], thread_ts=args["thread_ts"])
        replies = [m for m in self._messages if m.get("channel") == args["channel"]]
        return {"ok": True, "messages": replies[:5]}

    def _set_status(self, args: dict) -> Any:
        self._log("set_status", text=args["text"])
        return {"ok": True}

    def _pin_message(self, args: dict) -> Any:
        self._log("pin_message", channel=args["channel"], ts=args["timestamp"])
        return {"ok": True}

    def _get_channel_history(self, args: dict) -> Any:
        channel = args["channel"]
        limit = args.get("limit", 20)
        self._log("get_channel_history", channel=channel, limit=limit)
        msgs = [m for m in self._messages if m.get("channel") == channel]
        return {"ok": True, "messages": msgs[:limit]}
