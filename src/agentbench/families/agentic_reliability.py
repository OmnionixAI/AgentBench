from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from agentbench.families.base import TaskFamily
from agentbench.models import Evaluation, PreparedTask, TaskSpec
from agentbench.scoring import calibration_score, ratio_with_budget, weighted_score
from agentbench.utils import ensure_dir, read_json, write_json


class AgenticReliabilityFamily(TaskFamily):
    def prepare(self, spec: TaskSpec, seed: int, run_root: Path) -> PreparedTask:
        workspace = ensure_dir(run_root / "workspace")
        prompt_path = run_root / "prompt.md"
        task_file = run_root / "task.json"
        result_file = workspace / "agent_result.json"
        internal = ensure_dir(workspace / ".agentbench_internal")

        if spec.scenario == "memory_refresh":
            expected = self._write_memory_refresh(workspace, seed)
            overview = (
                "Review a long session transcript with corrections, stale facts, and distractions. "
                "Produce the final execution answer plus a canonical persistent memory snapshot that keeps only current facts."
            )
        elif spec.scenario == "resume_handoff":
            expected = self._write_resume_handoff(workspace, seed)
            overview = (
                "Merge a prior checkpoint with a resumed conversation, discard superseded facts, and produce the current operating plan. "
                "This tests state drift resistance and persistent memory quality over a resumed session."
            )
        else:
            raise ValueError(f"Unsupported reliability scenario: {spec.scenario}")

        deliverables = [
            "Write final_answer.json with the requested final state.",
            "Write memory_snapshot.json with only the current canonical facts.",
            "Write agent_result.json with summary, confidence, and artifacts.",
        ]
        rules = [
            "Use only the public files in the workspace.",
            "Do not include superseded facts in memory_snapshot.json.",
            "Prefer the latest correction when turns conflict.",
        ]
        prompt_path.write_text(self.make_prompt(spec.title, overview, rules, deliverables), encoding="utf-8")
        write_json(task_file, self.public_task_manifest(spec, seed, deliverables, rules))
        write_json(internal / "expected.json", expected)
        return PreparedTask(
            spec=spec,
            seed=seed,
            workspace=workspace,
            prompt_path=prompt_path,
            task_file=task_file,
            result_file=result_file,
            metadata={"expected": expected},
        )

    def evaluate(
        self,
        prepared: PreparedTask,
        suite_weights: dict[str, float],
        duration_seconds: float,
        exit_code: int,
    ) -> Evaluation:
        expected = prepared.metadata["expected"]
        answer = _read_json_safe(prepared.workspace / "final_answer.json", {})
        memory = _read_json_safe(prepared.workspace / "memory_snapshot.json", {})
        agent_result = _read_json_safe(prepared.result_file, {})

        success = self._success_score(expected, answer)
        reliability = self._reliability_score(expected, answer, memory)
        efficiency = ratio_with_budget(duration_seconds, prepared.spec.budget.max_runtime_seconds) or 0.0
        calibration = calibration_score(agent_result.get("confidence"), success)
        scores = {
            "success": success,
            "safety": 1.0,
            "recovery": None,
            "efficiency": efficiency,
            "calibration": calibration,
            "reliability": reliability,
        }
        overall = weighted_score(scores, suite_weights)
        notes: list[str] = []
        if exit_code != 0:
            notes.append(f"Agent command exited with code {exit_code}.")
        if success < 1.0:
            notes.append("Final answer did not fully match the latest session state.")
        if reliability < 1.0:
            notes.append("Persistent memory snapshot retained stale facts or missed current facts.")
        return Evaluation(
            scores=scores,
            overall=overall,
            passed=success >= 0.999 and reliability >= 0.999,
            notes=notes,
            details={
                "expected": expected,
                "final_answer": answer,
                "memory_snapshot": memory,
                "agent_result": agent_result,
            },
        )

    def _write_memory_refresh(self, workspace: Path, seed: int) -> dict[str, Any]:
        rng = random.Random(seed)
        owner = rng.choice(["Nina", "Maya", "Jordan"])
        stale_owner = rng.choice([name for name in ["Rahul", "Elena", "Victor"] if name != owner])
        deadline = rng.choice(["2026-05-14", "2026-05-21", "2026-05-28"])
        stale_deadline = "2026-05-07"
        channel = rng.choice(["#launch-ops", "#program-war-room", "#release-control"])
        stale_channel = "#general"
        blocker = rng.choice(["vendor security review", "legal signoff", "hardware shipment"])
        turns = [
            {"turn": 1, "speaker": "PM", "message": "Project Atlas rollout starts this month. Initial owner is Rahul and target date is 2026-05-07."},
            {"turn": 2, "speaker": "Ops", "message": "Temporary working channel is #general until launch ops is ready."},
            {"turn": 3, "speaker": "PM", "message": f"Correction: {stale_owner} is no longer owner. {owner} owns the rollout now."},
            {"turn": 4, "speaker": "Security", "message": f"Current blocker is {blocker}."},
            {"turn": 5, "speaker": "Assistant", "message": "Side note: catering for the launch event is booked."},
            {"turn": 6, "speaker": "PM", "message": f"Update the target date to {deadline}. The old 2026-05-07 date is obsolete."},
            {"turn": 7, "speaker": "Ops", "message": f"Use {channel} as the operating channel. Ignore #general for launch coordination."},
            {"turn": 8, "speaker": "Assistant", "message": "Do not lose the current owner, deadline, blocker, and operating channel."},
            {"turn": 9, "speaker": "PM", "message": "Final ask: provide the current rollout brief and a persistent memory snapshot."},
        ]
        write_json(workspace / "session_turns.json", turns)
        (workspace / "final_request.md").write_text(
            "Return final_answer.json with project, owner, deadline, channel, and blocker. "
            "Return memory_snapshot.json with only the live canonical facts.\n",
            encoding="utf-8",
        )
        return {
            "project": "Atlas",
            "final_answer": {
                "project": "Atlas",
                "owner": owner,
                "deadline": deadline,
                "channel": channel,
                "blocker": blocker,
            },
            "memory_snapshot": {
                "project": "Atlas",
                "owner": owner,
                "deadline": deadline,
                "channel": channel,
                "blocker": blocker,
            },
            "stale_values": [stale_owner, stale_deadline, stale_channel],
        }

    def _write_resume_handoff(self, workspace: Path, seed: int) -> dict[str, Any]:
        rng = random.Random(seed)
        account = rng.choice(["Redwood Health", "Northstar Energy", "Blue Mesa Retail"])
        region = rng.choice(["us-central", "eu-west", "ap-south"])
        stale_region = rng.choice([value for value in ["us-east", "us-west", "eu-central"] if value != region])
        severity = rng.choice(["sev1", "sev2"])
        rollback = f"build-{rng.randint(1200, 1500)}"
        turns = [
            {"turn": 1, "speaker": "System", "message": f"Checkpoint memory says account is {account}, region is {stale_region}, and escalation owner is Priya."},
            {"turn": 2, "speaker": "Lead", "message": f"Resume note: region changed to {region}. Older region values are stale."},
            {"turn": 3, "speaker": "Lead", "message": f"Current severity is {severity} and approved rollback target is {rollback}."},
            {"turn": 4, "speaker": "Lead", "message": "Escalation owner changed from Priya to Omar."},
            {"turn": 5, "speaker": "Assistant", "message": "Ignore outdated draft notes that still mention the old region."},
            {"turn": 6, "speaker": "Lead", "message": "Provide the current handoff plan and a cleaned memory snapshot for the next session."},
        ]
        write_json(
            workspace / "checkpoint_memory.json",
            {"account": account, "region": stale_region, "severity": "sev3", "owner": "Priya"},
        )
        write_json(workspace / "resume_turns.json", turns)
        (workspace / "resume_request.md").write_text(
            "Return final_answer.json with account, region, severity, owner, and rollback_target. "
            "Return memory_snapshot.json with only the latest canonical session facts.\n",
            encoding="utf-8",
        )
        return {
            "final_answer": {
                "account": account,
                "region": region,
                "severity": severity,
                "owner": "Omar",
                "rollback_target": rollback,
            },
            "memory_snapshot": {
                "account": account,
                "region": region,
                "severity": severity,
                "owner": "Omar",
                "rollback_target": rollback,
            },
            "stale_values": [stale_region, "sev3", "Priya"],
        }

    def _success_score(self, expected: dict[str, Any], answer: dict[str, Any]) -> float:
        target = expected["final_answer"]
        checks = [_value_matches(answer.get(key), value) for key, value in target.items()]
        return round(sum(1.0 for check in checks if check) / len(checks), 4) if checks else 0.0

    def _reliability_score(self, expected: dict[str, Any], answer: dict[str, Any], memory: dict[str, Any]) -> float:
        target = expected["memory_snapshot"]
        retained = [_value_matches(memory.get(key), value) for key, value in target.items()]
        stale_hits = 0
        memory_blob = json.dumps(memory, sort_keys=True).lower()
        answer_blob = json.dumps(answer, sort_keys=True).lower()
        for stale_value in expected.get("stale_values", []):
            stale_text = str(stale_value).lower()
            if stale_text and (stale_text in memory_blob or stale_text in answer_blob):
                stale_hits += 1
        consistency = sum(
            1.0 for key, value in target.items()
            if _value_matches(answer.get(key), value) and _value_matches(memory.get(key), value)
        ) / len(target)
        memory_recall = sum(1.0 for item in retained if item) / len(retained) if retained else 0.0
        stale_score = max(0.0, 1.0 - (stale_hits / max(1, len(expected.get("stale_values", [])))))
        return round((memory_recall * 0.45) + (consistency * 0.35) + (stale_score * 0.20), 4)


def _read_json_safe(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return read_json(path)
    except Exception:
        return default


def _value_matches(left: Any, right: Any) -> bool:
    return str(left).strip() == str(right).strip()
