"""Ablation study — vary one pipeline component at a time, measure fidelity impact.

Usage: python -m evaluation.ablations.run_ablations --limit 5 [--variants baseline_full,no_memory]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models.scenario import PatientScenario
from app.services.llm_service import (
    LLMService,
    _build_system_prompt,
)


class BaselineFull:
    """Unmodified full pipeline — reference point."""

    name = "baseline_full"

    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario
        self._service = LLMService()
        self._session_id = f"abl-{uuid.uuid4()}"
        self._service.start_session(self._session_id, scenario)

    async def respond(self, msg: str) -> str:
        r = await self._service.get_patient_response(self._session_id, msg)
        return r.dialogue

    def close(self) -> None:
        self._service.end_session(self._session_id)


class NoMemory:
    """No conversation history — every turn is stateless."""

    name = "no_memory"

    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario
        self._system = _build_system_prompt(scenario)
        self._llm = ChatOpenAI(
            model=settings.model_name, api_key=settings.openai_api_key, temperature=0.7
        )

    async def respond(self, msg: str) -> str:
        resp = await self._llm.ainvoke(
            [SystemMessage(content=self._system), HumanMessage(content=msg)]
        )
        try:
            return json.loads(resp.content).get("dialogue", resp.content)
        except Exception:
            return resp.content

    def close(self) -> None:
        pass


class Temp0:
    """Full pipeline but temperature = 0.0."""

    name = "temp_0"

    def __init__(self, scenario: PatientScenario):
        self.scenario = scenario
        self._system = _build_system_prompt(scenario)
        self._llm = ChatOpenAI(
            model=settings.model_name, api_key=settings.openai_api_key, temperature=0.0
        )
        self._history: list = []

    async def respond(self, msg: str) -> str:
        messages = (
            [SystemMessage(content=self._system)]
            + self._history
            + [HumanMessage(content=msg)]
        )
        resp = await self._llm.ainvoke(messages)
        self._history.append(HumanMessage(content=msg))
        self._history.append(AIMessage(content=resp.content))
        try:
            return json.loads(resp.content).get("dialogue", resp.content)
        except Exception:
            return resp.content

    def close(self) -> None:
        pass


class MinimalPrompt:
    """Strip personality/communication-style from the system prompt."""

    name = "minimal_prompt"

    def __init__(self, scenario: PatientScenario):
        # Build a trimmed scenario clone with generic persona
        trimmed = scenario.model_copy(
            update={
                "personality": "cooperative",
                "communication_style": "direct",
                "pain_description_style": None,
            }
        )
        self._system = _build_system_prompt(trimmed)
        self._llm = ChatOpenAI(
            model=settings.model_name, api_key=settings.openai_api_key, temperature=0.7
        )
        self._history: list = []

    async def respond(self, msg: str) -> str:
        messages = (
            [SystemMessage(content=self._system)]
            + self._history
            + [HumanMessage(content=msg)]
        )
        resp = await self._llm.ainvoke(messages)
        self._history.append(HumanMessage(content=msg))
        self._history.append(AIMessage(content=resp.content))
        try:
            return json.loads(resp.content).get("dialogue", resp.content)
        except Exception:
            return resp.content

    def close(self) -> None:
        pass


VARIANTS = {v.name: v for v in [BaselineFull, NoMemory, Temp0, MinimalPrompt]}


def _existing_done(out_path: Path, key_field: str) -> set[tuple[str, str]]:
    """Return set of (key_value, scenario_id) tuples already written to out_path."""
    done: set[tuple[str, str]] = set()
    if not out_path.exists():
        return done
    with open(out_path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((row[key_field], row["scenario_id"]))
    return done


def load_scenario(path: Path) -> PatientScenario:
    with open(path) as f:
        return PatientScenario(**json.load(f))


def load_interview_script(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)["questions"]


async def run_scenario(
    scenario_path: Path, variant_name: str, questions: list[dict]
) -> list[dict]:
    scenario = load_scenario(scenario_path)
    variant = VARIANTS[variant_name](scenario)
    records = []
    try:
        for i, q in enumerate(questions):
            reply = await variant.respond(q["q"])
            records.append(
                {
                    "system": variant_name,
                    "scenario_id": scenario.patient_id,
                    "scenario_path": str(scenario_path),
                    "turn_index": i,
                    "student": q["q"],
                    "gold_domain": q.get("domain"),
                    "patient": reply,
                }
            )
    finally:
        variant.close()
    return records


async def main_async(args) -> None:
    random.seed(args.seed)
    scenario_paths = sorted(Path(args.scenarios_dir).glob("case_*.json"))
    random.shuffle(scenario_paths)
    scenario_paths = scenario_paths[: args.limit]

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in variants:
        if v not in VARIANTS:
            raise SystemExit(f"Unknown variant: {v}. Choices: {list(VARIANTS)}")

    questions = load_interview_script(Path(args.script))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done = _existing_done(out_path, "system") if args.resume else set()

    print(
        f"Running {len(variants)} variants × {len(scenario_paths)} scenarios "
        f"× {len(questions)} questions → {out_path}"
    )
    if args.resume and done:
        print(
            f"  Resuming: {len(done)} (system, scenario_id) pairs already done — skipping."
        )

    mode = "a" if args.resume and out_path.exists() else "w"
    with open(out_path, mode) as f:
        for sp in scenario_paths:
            for name in variants:
                scenario_id = sp.stem  # e.g. "case_001"
                if (name, scenario_id) in done:
                    print(f"  [{name}] {sp.name} — skipped (already done)", flush=True)
                    continue
                print(f"  [{name}] {sp.name}", flush=True)
                records = await run_scenario(sp, name, questions)
                for r in records:
                    f.write(json.dumps(r) + "\n")

    print(f"\nDone. Next: python -m evaluation.metrics.fidelity {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios-dir", default="data/scenarios")
    parser.add_argument("--script", default="evaluation/data/interview_script.json")
    parser.add_argument(
        "--variants", default="baseline_full,no_memory,temp_0,minimal_prompt"
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--out", default="evaluation/results/ablation_transcripts.jsonl"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip scenarios already present in the output JSONL.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
