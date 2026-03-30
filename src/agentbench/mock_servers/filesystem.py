"""Mock filesystem MCP server backed by an in-memory file tree."""

from __future__ import annotations

import fnmatch
from typing import Any

from agentbench.transport.protocol import MCPToolRegistry


class FilesystemServer:
    """In-memory filesystem with MCP-registered tool handlers."""

    def __init__(self, initial_files: dict[str, str] | None = None) -> None:
        self._files: dict[str, str] = dict(initial_files or {})
        self._operation_log: list[dict[str, Any]] = []

    @property
    def files(self) -> dict[str, str]:
        return dict(self._files)

    @property
    def operation_log(self) -> list[dict[str, Any]]:
        return list(self._operation_log)

    def _log(self, op: str, **kwargs: Any) -> None:
        self._operation_log.append({"operation": op, **kwargs})

    def register(self, registry: MCPToolRegistry) -> None:
        registry.register_simple(
            "fs_read_file", "Read the contents of a file at the given path.",
            self._read_file,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_write_file", "Write content to a file, creating or overwriting it.",
            self._write_file,
            {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        )
        registry.register_simple(
            "fs_list_directory", "List all files and subdirectories under the given path prefix.",
            self._list_directory,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_delete_file", "Delete a file at the given path.",
            self._delete_file,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_search_files", "Search for files whose path matches a glob pattern.",
            self._search_files,
            {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]},
        )
        registry.register_simple(
            "fs_stat_file", "Get metadata about a file: size in bytes and whether it exists.",
            self._stat_file,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_copy_file", "Copy a file from source path to destination path.",
            self._copy_file,
            {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]},
        )
        registry.register_simple(
            "fs_move_file", "Move (rename) a file from source path to destination path.",
            self._move_file,
            {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]},
        )
        registry.register_simple(
            "fs_append_file", "Append content to the end of an existing file.",
            self._append_file,
            {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        )
        registry.register_simple(
            "fs_file_exists", "Check whether a file exists at the given path.",
            self._file_exists,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_read_lines", "Read specific line range from a file (1-indexed, inclusive).",
            self._read_lines,
            {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path", "start", "end"]},
        )
        registry.register_simple(
            "fs_count_lines", "Count the number of lines in a file.",
            self._count_lines,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_grep", "Search for a text pattern inside a file, returning matching lines.",
            self._grep,
            {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["path", "pattern"]},
        )
        registry.register_simple(
            "fs_mkdir", "Create a directory marker at the given path.",
            self._mkdir,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )
        registry.register_simple(
            "fs_tree", "Return a recursive tree listing of all files.",
            self._tree,
            {"type": "object", "properties": {}},
        )

    def _read_file(self, args: dict) -> Any:
        path = args["path"]
        self._log("read_file", path=path)
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return {"path": path, "content": self._files[path]}

    def _write_file(self, args: dict) -> Any:
        path, content = args["path"], args["content"]
        self._log("write_file", path=path, size=len(content))
        self._files[path] = content
        return {"path": path, "written": len(content)}

    def _list_directory(self, args: dict) -> Any:
        prefix = args["path"].rstrip("/") + "/"
        entries = sorted({p for p in self._files if p.startswith(prefix) or p == args["path"].rstrip("/")})
        self._log("list_directory", path=args["path"], count=len(entries))
        return {"path": args["path"], "entries": entries}

    def _delete_file(self, args: dict) -> Any:
        path = args["path"]
        self._log("delete_file", path=path)
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        del self._files[path]
        return {"deleted": path}

    def _search_files(self, args: dict) -> Any:
        pattern = args["pattern"]
        matches = sorted(p for p in self._files if fnmatch.fnmatch(p, pattern))
        self._log("search_files", pattern=pattern, count=len(matches))
        return {"pattern": pattern, "matches": matches}

    def _stat_file(self, args: dict) -> Any:
        path = args["path"]
        self._log("stat_file", path=path)
        if path not in self._files:
            return {"path": path, "exists": False}
        return {"path": path, "exists": True, "size": len(self._files[path])}

    def _copy_file(self, args: dict) -> Any:
        src, dst = args["source"], args["destination"]
        self._log("copy_file", source=src, destination=dst)
        if src not in self._files:
            raise FileNotFoundError(f"No such file: {src}")
        self._files[dst] = self._files[src]
        return {"copied": src, "to": dst}

    def _move_file(self, args: dict) -> Any:
        src, dst = args["source"], args["destination"]
        self._log("move_file", source=src, destination=dst)
        if src not in self._files:
            raise FileNotFoundError(f"No such file: {src}")
        self._files[dst] = self._files[src]
        del self._files[src]
        return {"moved": src, "to": dst}

    def _append_file(self, args: dict) -> Any:
        path, content = args["path"], args["content"]
        self._log("append_file", path=path, size=len(content))
        self._files[path] = self._files.get(path, "") + content
        return {"path": path, "total_size": len(self._files[path])}

    def _file_exists(self, args: dict) -> Any:
        path = args["path"]
        self._log("file_exists", path=path)
        return {"path": path, "exists": path in self._files}

    def _read_lines(self, args: dict) -> Any:
        path = args["path"]
        self._log("read_lines", path=path, start=args["start"], end=args["end"])
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        lines = self._files[path].splitlines()
        start = max(1, args["start"]) - 1
        end = min(len(lines), args["end"])
        return {"path": path, "lines": lines[start:end], "total": len(lines)}

    def _count_lines(self, args: dict) -> Any:
        path = args["path"]
        self._log("count_lines", path=path)
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return {"path": path, "lines": len(self._files[path].splitlines())}

    def _grep(self, args: dict) -> Any:
        path, pattern = args["path"], args["pattern"]
        self._log("grep", path=path, pattern=pattern)
        if path not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        matches = [
            {"line_number": i + 1, "text": line}
            for i, line in enumerate(self._files[path].splitlines())
            if pattern in line
        ]
        return {"path": path, "pattern": pattern, "matches": matches}

    def _mkdir(self, args: dict) -> Any:
        path = args["path"].rstrip("/") + "/"
        self._log("mkdir", path=path)
        self._files.setdefault(path + ".keep", "")
        return {"created": path}

    def _tree(self, args: dict) -> Any:
        self._log("tree")
        return {"files": sorted(self._files.keys())}
