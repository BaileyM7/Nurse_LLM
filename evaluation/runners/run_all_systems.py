"""Run all three systems on every scenario, writing patient-turn JSONL for fidelity.py.

Usage: python -m evaluation.runners.run_all_systems [--limit 5] [--systems rule_based,full_pipeline]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from pathlib import Path

from app.models.scenario import PatientScenario
from evaluation.baselines.few_shot_patient import FewShotPatient
from evaluation.baselines.full_pipeline import FullPipelinePatient
from evaluation.baselines.rule_based_patient import RuleBasedPatient

SYSTEM_BUILDERS = {
    "rule_based": lambda sc: RuleBasedPatient(sc),
    "few_shot": lambda sc: FewShotPatient(sc),
    "full_pipeline": lambda sc: FullPipelinePatient(sc),
}


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


async def _respond(system, message: str) -> str:
    """Unified interface: rule_based returns str directly, others are async."""
    if isinstance(system, RuleBasedPatient):
        return system.respond(message)
    return await system.respond(message)


async def run_scenario(
    scenario_path: Path, system_name: str, questions: list[dict]
) -> list[dict]:
    scenario = load_scenario(scenario_path)
    system = SYSTEM_BUILDERS[system_name](scenario)
    records = []
    try:
        for i, qobj in enumerate(questions):
            reply = await _respond(system, qobj["q"])
            records.append(
                {
                    "system": system_name,
                    "scenario_id": scenario.patient_id,
                    "scenario_path": str(scenario_path),
                    "turn_index": i,
                    "student": qobj["q"],
                    "gold_domain": qobj.get("domain"),
                    "patient": reply,
                }
            )
    finally:
        if hasattr(system, "close"):
            system.close()
    return records


async def main_async(args) -> None:
    scenarios_dir = Path(args.scenarios_dir)
    scenario_paths = sorted(scenarios_dir.glob("case_*.json"))
    if args.limit:
        scenario_paths = scenario_paths[: args.limit]

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    for s in systems:
        if s not in SYSTEM_BUILDERS:
            raise SystemExit(f"Unknown system: {s}. Choices: {list(SYSTEM_BUILDERS)}")

    questions = load_interview_script(Path(args.script))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done = _existing_done(out_path, "system") if args.resume else set()

    print(
        f"Running {len(systems)} systems × {len(scenario_paths)} scenarios "
        f"× {len(questions)} questions"
    )
    print(f"Output: {out_path}")
    if args.resume and done:
        print(
            f"  Resuming: {len(done)} (system, scenario_id) pairs already done — skipping."
        )

    errors_path = Path("evaluation/results/errors.log")
    errors_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if args.resume and out_path.exists() else "w"
    with open(out_path, mode) as f:
        for sp in scenario_paths:
            for system_name in systems:
                scenario_id = sp.stem  # e.g. "case_001"
                if (system_name, scenario_id) in done:
                    print(
                        f"  [{system_name}] {sp.name} — skipped (already done)",
                        flush=True,
                    )
                    continue
                print(f"  [{system_name}] {sp.name}...", flush=True)
                try:
                    records = await run_scenario(sp, system_name, questions)
                except Exception as exc:  # broad on purpose: never abort a long run
                    with errors_path.open("a", encoding="utf-8") as ef:
                        ef.write(
                            f"{system_name}\t{sp.name}\t{type(exc).__name__}\t{exc}\n"
                        )
                    print(
                        f"  [{system_name}] {sp.name} — error logged, skipping",
                        flush=True,
                    )
                    continue
                for r in records:
                    f.write(json.dumps(r) + "\n")

    print(f"\nDone. {out_path} written.")
    print("Next: python -m evaluation.metrics.fidelity", out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios-dir", default="data/scenarios")
    parser.add_argument("--script", default="evaluation/data/interview_script.json")
    parser.add_argument("--systems", default="rule_based,few_shot,full_pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run first N scenarios (for quick sanity checks)",
    )
    parser.add_argument("--out", default="evaluation/results/transcripts.jsonl")
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip scenarios already present in the output JSONL.",
    )
    args = parser.parse_args()
    random.seed(args.seed)
    try:
        import numpy as np

        np.random.seed(args.seed)
    except ImportError:
        pass
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
