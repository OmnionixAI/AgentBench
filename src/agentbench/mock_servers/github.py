"""Mock GitHub API MCP server backed by in-memory state."""

from __future__ import annotations

import random
from typing import Any

from agentbench.transport.protocol import MCPToolRegistry


class GitHubServer:
    """In-memory GitHub API simulator with MCP-registered tool handlers."""

    def __init__(self, seed: int = 42) -> None:
        rng = random.Random(seed)
        self._repos: list[dict[str, Any]] = [
            {"name": f"repo-{i}", "owner": "omnionix", "stars": rng.randint(5, 5000), "language": rng.choice(["Python", "TypeScript", "Go", "Rust"])}
            for i in range(1, 6)
        ]
        self._issues: list[dict[str, Any]] = [
            {"id": i, "repo": f"repo-{rng.randint(1, 5)}", "title": f"Issue #{i}", "state": "open", "labels": [], "assignees": []}
            for i in range(1, 8)
        ]
        self._prs: list[dict[str, Any]] = []
        self._branches: list[dict[str, Any]] = [
            {"repo": f"repo-{i}", "name": "main", "sha": f"abc{i}000"} for i in range(1, 6)
        ]
        self._commits: list[dict[str, Any]] = [
            {"repo": f"repo-{rng.randint(1, 5)}", "sha": f"commit{i:04x}", "message": f"Commit {i}", "author": "dev"}
            for i in range(1, 11)
        ]
        self._next_id = 100
        self._operation_log: list[dict[str, Any]] = []

    @property
    def operation_log(self) -> list[dict[str, Any]]:
        return list(self._operation_log)

    def _log(self, op: str, **kwargs: Any) -> None:
        self._operation_log.append({"operation": op, **kwargs})

    def _fresh_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def register(self, registry: MCPToolRegistry) -> None:
        registry.register_simple("gh_list_repos", "List all repositories in the organization.", self._list_repos, {"type": "object", "properties": {}})
        registry.register_simple("gh_get_repo", "Get details of a specific repository by name.", self._get_repo, {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]})
        registry.register_simple("gh_list_issues", "List issues for a repository, optionally filter by state.", self._list_issues, {"type": "object", "properties": {"repo": {"type": "string"}, "state": {"type": "string"}}, "required": ["repo"]})
        registry.register_simple("gh_create_issue", "Create a new issue in a repository.", self._create_issue, {"type": "object", "properties": {"repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}, "required": ["repo", "title"]})
        registry.register_simple("gh_close_issue", "Close an issue by ID.", self._close_issue, {"type": "object", "properties": {"issue_id": {"type": "integer"}}, "required": ["issue_id"]})
        registry.register_simple("gh_add_label", "Add a label to an issue.", self._add_label, {"type": "object", "properties": {"issue_id": {"type": "integer"}, "label": {"type": "string"}}, "required": ["issue_id", "label"]})
        registry.register_simple("gh_assign_reviewer", "Assign a reviewer to an issue or PR.", self._assign_reviewer, {"type": "object", "properties": {"issue_id": {"type": "integer"}, "reviewer": {"type": "string"}}, "required": ["issue_id", "reviewer"]})
        registry.register_simple("gh_create_branch", "Create a new branch in a repository from a base branch.", self._create_branch, {"type": "object", "properties": {"repo": {"type": "string"}, "branch": {"type": "string"}, "base": {"type": "string"}}, "required": ["repo", "branch"]})
        registry.register_simple("gh_list_branches", "List branches for a repository.", self._list_branches, {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]})
        registry.register_simple("gh_create_pr", "Create a pull request.", self._create_pr, {"type": "object", "properties": {"repo": {"type": "string"}, "title": {"type": "string"}, "head": {"type": "string"}, "base": {"type": "string"}}, "required": ["repo", "title", "head", "base"]})
        registry.register_simple("gh_merge_pr", "Merge a pull request by ID.", self._merge_pr, {"type": "object", "properties": {"pr_id": {"type": "integer"}}, "required": ["pr_id"]})
        registry.register_simple("gh_list_prs", "List pull requests for a repository.", self._list_prs, {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]})
        registry.register_simple("gh_get_commit", "Get details of a commit by SHA.", self._get_commit, {"type": "object", "properties": {"repo": {"type": "string"}, "sha": {"type": "string"}}, "required": ["repo", "sha"]})
        registry.register_simple("gh_list_commits", "List recent commits for a repository.", self._list_commits, {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]})
        registry.register_simple("gh_search_code", "Search for code content across repositories.", self._search_code, {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
        registry.register_simple("gh_get_file_content", "Get the content of a file in a repository.", self._get_file_content, {"type": "object", "properties": {"repo": {"type": "string"}, "path": {"type": "string"}}, "required": ["repo", "path"]})
        registry.register_simple("gh_create_release", "Create a tagged release for a repository.", self._create_release, {"type": "object", "properties": {"repo": {"type": "string"}, "tag": {"type": "string"}, "name": {"type": "string"}}, "required": ["repo", "tag", "name"]})
        registry.register_simple("gh_list_releases", "List releases for a repository.", self._list_releases, {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]})
        registry.register_simple("gh_get_rate_limit", "Get current API rate limit status.", self._get_rate_limit, {"type": "object", "properties": {}})
        registry.register_simple("gh_get_user", "Get information about the authenticated user.", self._get_user, {"type": "object", "properties": {}})

    def _list_repos(self, args: dict) -> Any:
        self._log("list_repos")
        return {"repos": self._repos}

    def _get_repo(self, args: dict) -> Any:
        name = args["name"]
        self._log("get_repo", name=name)
        for repo in self._repos:
            if repo["name"] == name:
                return repo
        raise ValueError(f"Repository not found: {name}")

    def _list_issues(self, args: dict) -> Any:
        repo = args["repo"]
        state = args.get("state", "open")
        self._log("list_issues", repo=repo, state=state)
        return {"issues": [i for i in self._issues if i["repo"] == repo and i["state"] == state]}

    def _create_issue(self, args: dict) -> Any:
        issue = {"id": self._fresh_id(), "repo": args["repo"], "title": args["title"], "state": "open", "labels": [], "assignees": []}
        self._issues.append(issue)
        self._log("create_issue", issue_id=issue["id"])
        return issue

    def _close_issue(self, args: dict) -> Any:
        issue_id = args["issue_id"]
        self._log("close_issue", issue_id=issue_id)
        for issue in self._issues:
            if issue["id"] == issue_id:
                issue["state"] = "closed"
                return issue
        raise ValueError(f"Issue not found: {issue_id}")

    def _add_label(self, args: dict) -> Any:
        issue_id, label = args["issue_id"], args["label"]
        self._log("add_label", issue_id=issue_id, label=label)
        for issue in self._issues:
            if issue["id"] == issue_id:
                issue["labels"].append(label)
                return issue
        raise ValueError(f"Issue not found: {issue_id}")

    def _assign_reviewer(self, args: dict) -> Any:
        issue_id, reviewer = args["issue_id"], args["reviewer"]
        self._log("assign_reviewer", issue_id=issue_id, reviewer=reviewer)
        for issue in self._issues:
            if issue["id"] == issue_id:
                issue["assignees"].append(reviewer)
                return issue
        raise ValueError(f"Issue not found: {issue_id}")

    def _create_branch(self, args: dict) -> Any:
        branch = {"repo": args["repo"], "name": args["branch"], "sha": f"new{self._fresh_id():04x}"}
        self._branches.append(branch)
        self._log("create_branch", repo=args["repo"], branch=args["branch"])
        return branch

    def _list_branches(self, args: dict) -> Any:
        repo = args["repo"]
        self._log("list_branches", repo=repo)
        return {"branches": [b for b in self._branches if b["repo"] == repo]}

    def _create_pr(self, args: dict) -> Any:
        pr = {"id": self._fresh_id(), "repo": args["repo"], "title": args["title"], "head": args["head"], "base": args["base"], "state": "open", "merged": False}
        self._prs.append(pr)
        self._log("create_pr", pr_id=pr["id"])
        return pr

    def _merge_pr(self, args: dict) -> Any:
        pr_id = args["pr_id"]
        self._log("merge_pr", pr_id=pr_id)
        for pr in self._prs:
            if pr["id"] == pr_id:
                pr["state"] = "closed"
                pr["merged"] = True
                return pr
        raise ValueError(f"PR not found: {pr_id}")

    def _list_prs(self, args: dict) -> Any:
        repo = args["repo"]
        self._log("list_prs", repo=repo)
        return {"prs": [p for p in self._prs if p["repo"] == repo]}

    def _get_commit(self, args: dict) -> Any:
        repo, sha = args["repo"], args["sha"]
        self._log("get_commit", repo=repo, sha=sha)
        for c in self._commits:
            if c["repo"] == repo and c["sha"] == sha:
                return c
        raise ValueError(f"Commit not found: {sha}")

    def _list_commits(self, args: dict) -> Any:
        repo = args["repo"]
        self._log("list_commits", repo=repo)
        return {"commits": [c for c in self._commits if c["repo"] == repo]}

    def _search_code(self, args: dict) -> Any:
        query = args["query"]
        self._log("search_code", query=query)
        return {"results": [{"repo": "repo-1", "path": "src/main.py", "snippet": f"...{query}..."}]}

    def _get_file_content(self, args: dict) -> Any:
        self._log("get_file_content", repo=args["repo"], path=args["path"])
        return {"repo": args["repo"], "path": args["path"], "content": f"# Stub content for {args['path']}\n"}

    def _create_release(self, args: dict) -> Any:
        release = {"id": self._fresh_id(), "repo": args["repo"], "tag": args["tag"], "name": args["name"]}
        self._log("create_release", release_id=release["id"])
        return release

    def _list_releases(self, args: dict) -> Any:
        self._log("list_releases", repo=args["repo"])
        return {"releases": []}

    def _get_rate_limit(self, args: dict) -> Any:
        self._log("get_rate_limit")
        return {"limit": 5000, "remaining": 4987, "reset": 1700000000}

    def _get_user(self, args: dict) -> Any:
        self._log("get_user")
        return {"login": "bench-agent", "name": "Bench Agent", "plan": "pro"}
