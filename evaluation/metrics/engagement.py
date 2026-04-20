"""
Student engagement metrics, computed from the production SQLite DB
(data/nurse_llm.db) that the FastAPI app writes to.

Measures (P2 targets):
  - avg turns per session     (target ≥15)
  - session completion rate    (target ≥80%, = sessions with status="ended" / total)
  - avg session duration (min)
  - turns/session distribution

This reads but never writes to the DB. Safe to run against live data.

Usage:
    python -m evaluation.metrics.engagement
    python -m evaluation.metrics.engagement --db data/nurse_llm.db --out-dir evaluation/results
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

# Reuse the existing ORM — we don't modify it, just query it.
from app.db.models import SessionRecord, MessageRecord


def compute_engagement(db_url: str) -> dict:
    engine = create_engine(db_url)
    with Session(engine) as s:
        all_sessions = s.scalars(select(SessionRecord)).all()
        if not all_sessions:
            return {"total_sessions": 0}

        total = len(all_sessions)
        ended = sum(1 for r in all_sessions if r.status == "ended")
        completion_rate = ended / total

        turn_counts = [r.turn_count or 0 for r in all_sessions]
        avg_turns = sum(turn_counts) / total

        durations_min = []
        for r in all_sessions:
            if r.end_time and r.start_time:
                durations_min.append((r.end_time - r.start_time).total_seconds() / 60)
        avg_duration = sum(durations_min) / len(durations_min) if durations_min else None

        # messages per role
        role_counts = dict(s.execute(
            select(MessageRecord.role, func.count(MessageRecord.id)).group_by(MessageRecord.role)
        ).all())

    return {
        "total_sessions": total,
        "ended_sessions": ended,
        "completion_rate": round(completion_rate, 3),
        "avg_turns": round(avg_turns, 2),
        "turns_distribution": sorted(turn_counts),
        "avg_duration_min": round(avg_duration, 2) if avg_duration is not None else None,
        "message_counts_by_role": role_counts,
        "target_turns_met_15": avg_turns >= 15,
        "target_completion_met_80pct": completion_rate >= 0.80,
    }


def plot_turns_distribution(turns: list[int], out_path: str) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(turns, bins=range(0, max(turns) + 2))
    ax.axvline(15, color="red", linestyle="--", label="P2 target (15 turns)")
    ax.set_xlabel("Turns per session")
    ax.set_ylabel("# sessions")
    ax.set_title("Session Length Distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/nurse_llm.db",
                        help="Path to the SQLite file (relative to project root)")
    parser.add_argument("--out-dir", default="evaluation/results")
    args = parser.parse_args()

    db_url = f"sqlite:///{args.db}"
    stats = compute_engagement(db_url)

    print(f"\n=== Student Engagement ===")
    if stats["total_sessions"] == 0:
        print("  No sessions found in DB yet — run some user sessions first.")
        return

    t_status = "PASS" if stats["target_turns_met_15"] else "FAIL"
    c_status = "PASS" if stats["target_completion_met_80pct"] else "FAIL"
    print(f"  Total sessions:     {stats['total_sessions']}")
    print(f"  Completion rate:    {stats['completion_rate']:.1%}  [{c_status}]  (target ≥80%)")
    print(f"  Avg turns/session:  {stats['avg_turns']}       [{t_status}]  (target ≥15)")
    if stats["avg_duration_min"] is not None:
        print(f"  Avg duration:       {stats['avg_duration_min']} min")
    print(f"  Messages by role:   {stats['message_counts_by_role']}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    import csv
    with open(out_dir / "engagement.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "target", "met"])
        w.writerow(["total_sessions", stats["total_sessions"], "-", "-"])
        w.writerow(["completion_rate", stats["completion_rate"], 0.80,
                    stats["target_completion_met_80pct"]])
        w.writerow(["avg_turns", stats["avg_turns"], 15,
                    stats["target_turns_met_15"]])
        w.writerow(["avg_duration_min", stats["avg_duration_min"], "-", "-"])

    if stats["turns_distribution"]:
        plot_turns_distribution(stats["turns_distribution"],
                                str(out_dir / "turns_distribution.png"))
    print(f"\nResults saved to {out_dir}/")


if __name__ == "__main__":
    main()
