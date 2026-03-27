"""
Cost Tracker — centralized token and cost monitoring for the advisory team.
Week 4 Production Addition, Lonely Octopus AI Agent Bootcamp

Tracks per-call and per-session usage, enforces spending limits,
and provides data for the Streamlit cost dashboard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

# Anthropic pricing (per 1M tokens) as of March 2026
MODEL_PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}

# Default fallback for unknown models
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


@dataclass
class APICall:
    """Record of a single API call."""
    timestamp: str
    model: str
    caller: str  # e.g., "SecurityAgent", "Triage", "Synthesis"
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: int


@dataclass
class CostTracker:
    """Session-level cost tracking with spending limits."""

    # Configurable limits
    session_limit_usd: float = 1.00  # Hard limit per session
    alert_threshold: float = 0.70  # Soft alert at 70% of limit

    # Tracked state
    calls: list[APICall] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    limit_reached: bool = False

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for an API call."""
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)
        return round(cost, 6)

    def record_call(
        self,
        model: str,
        caller: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int = 0,
    ) -> APICall:
        """Record an API call and check against spending limits."""
        cost = self.estimate_cost(model, input_tokens, output_tokens)

        call = APICall(
            timestamp=datetime.now().isoformat(),
            model=model,
            caller=caller,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
        )

        self.calls.append(call)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost

        if self.total_cost >= self.session_limit_usd:
            self.limit_reached = True

        return call

    def check_budget(self) -> dict:
        """Check current budget status."""
        pct = (self.total_cost / self.session_limit_usd * 100) if self.session_limit_usd > 0 else 0
        if self.limit_reached:
            status = "exceeded"
        elif pct >= self.alert_threshold * 100:
            status = "warning"
        else:
            status = "ok"

        return {
            "status": status,
            "spent": round(self.total_cost, 4),
            "limit": self.session_limit_usd,
            "percent": round(pct, 1),
            "calls": len(self.calls),
        }

    def get_breakdown_by_caller(self) -> dict[str, dict]:
        """Get cost breakdown by caller (agent name)."""
        breakdown = {}
        for call in self.calls:
            if call.caller not in breakdown:
                breakdown[call.caller] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                }
            entry = breakdown[call.caller]
            entry["calls"] += 1
            entry["input_tokens"] += call.input_tokens
            entry["output_tokens"] += call.output_tokens
            entry["cost"] += call.estimated_cost
        return breakdown

    def get_breakdown_by_model(self) -> dict[str, dict]:
        """Get cost breakdown by model."""
        breakdown = {}
        for call in self.calls:
            if call.model not in breakdown:
                breakdown[call.model] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                }
            entry = breakdown[call.model]
            entry["calls"] += 1
            entry["input_tokens"] += call.input_tokens
            entry["output_tokens"] += call.output_tokens
            entry["cost"] += call.estimated_cost
        return breakdown

    def format_summary(self) -> str:
        """Human-readable summary for logging."""
        budget = self.check_budget()
        lines = [
            f"Session Cost: ${budget['spent']:.4f} / ${budget['limit']:.2f} ({budget['percent']:.1f}%)",
            f"API Calls: {budget['calls']}",
            f"Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out",
        ]
        return " | ".join(lines)


# Module-level singleton for the current session
tracker = CostTracker()


def reset_tracker(session_limit: float = 1.00):
    """Reset the tracker for a new session."""
    global tracker
    tracker = CostTracker(session_limit_usd=session_limit)
    return tracker
