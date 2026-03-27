"""
Shared Memory — cross-agent persistent memory for the multi-agent team.
Week 3, Lonely Octopus AI Agent Bootcamp

Extends Week 2 memory with:
- Agent interaction tracking (which agents consulted, what they found)
- Cross-agent context (shared findings visible to all agents)
- Conversation thread memory across turns
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path(__file__).parent / "data"
MEMORY_FILE = MEMORY_DIR / "memory.json"


class SharedMemory:
    """Manages persistent shared memory across agents and sessions."""

    def __init__(self):
        MEMORY_DIR.mkdir(exist_ok=True)
        self.data = self._load()
        # In-session scratch pad for cross-agent context (not persisted per-turn)
        self.session_context: list[dict] = []

    def _load(self) -> dict:
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    # --- Org-level memory (persistent across sessions) ---

    def get_org(self, org_name: str) -> Optional[dict]:
        return self.data.get(org_name)

    def has_org(self, org_name: str) -> bool:
        return org_name in self.data

    def init_org(self, org_name: str, profile: dict):
        if org_name not in self.data:
            self.data[org_name] = {
                "profile": profile,
                "first_session": datetime.now().isoformat(),
                "session_count": 0,
                "topics_discussed": [],
                "key_decisions": [],
                "preferences": [],
                "agents_consulted": [],
            }
        else:
            self.data[org_name]["profile"] = profile

        self.data[org_name]["session_count"] = self.data[org_name].get("session_count", 0) + 1
        self.data[org_name]["last_session"] = datetime.now().isoformat()
        self._save()

    def add_topic(self, org_name: str, topic: str):
        if org_name in self.data:
            topics = self.data[org_name].setdefault("topics_discussed", [])
            if topic not in topics:
                topics.append(topic)
                self._save()

    def add_decision(self, org_name: str, decision: str):
        if org_name in self.data:
            decisions = self.data[org_name].setdefault("key_decisions", [])
            decisions.append({"decision": decision, "date": datetime.now().isoformat()})
            self._save()

    def add_preference(self, org_name: str, preference: str):
        if org_name in self.data:
            prefs = self.data[org_name].setdefault("preferences", [])
            if preference not in prefs:
                prefs.append(preference)
                self._save()

    def record_agent_consultation(self, org_name: str, agent_name: str, domain: str):
        """Track which agents have been consulted for this org."""
        if org_name in self.data:
            consulted = self.data[org_name].setdefault("agents_consulted", [])
            entry = f"{agent_name} ({domain})"
            if entry not in consulted:
                consulted.append(entry)
                self._save()

    def format_memory_context(self, org_name: str) -> str:
        org = self.get_org(org_name)
        if not org:
            return ""

        parts = [f"## Memory from Previous Sessions (Session #{org['session_count']})"]
        parts.append(f"First session: {org.get('first_session', 'unknown')}")

        if org.get("topics_discussed"):
            parts.append("\n### Topics Previously Discussed")
            for t in org["topics_discussed"][-10:]:
                parts.append(f"- {t}")

        if org.get("key_decisions"):
            parts.append("\n### Key Decisions Made")
            for d in org["key_decisions"][-10:]:
                parts.append(f"- {d['decision']} ({d['date'][:10]})")

        if org.get("preferences"):
            parts.append("\n### Known Preferences")
            for p in org["preferences"]:
                parts.append(f"- {p}")

        return "\n".join(parts)

    # --- Session-level shared context (cross-agent within a turn) ---

    def add_agent_finding(self, agent_name: str, domain: str, summary: str):
        """Add a finding from one agent that other agents can reference."""
        self.session_context.append({
            "agent": agent_name,
            "domain": domain,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        })

    def get_shared_context(self, exclude_domain: str = "") -> str:
        """Format session context for injection into specialist prompts."""
        relevant = [c for c in self.session_context if c["domain"] != exclude_domain]
        if not relevant:
            return ""

        parts = ["Here is context from other specialists on the team:"]
        for ctx in relevant[-5:]:  # Last 5 findings
            parts.append(f"- **{ctx['agent']}**: {ctx['summary']}")
        return "\n".join(parts)

    def clear_session_context(self):
        """Clear session scratch pad (call at start of new session)."""
        self.session_context = []

    def update_from_extraction(self, org_name: str, extraction: dict):
        """Update memory from an AI extraction result."""
        if org_name not in self.data:
            return

        for topic in extraction.get("topics", []):
            self.add_topic(org_name, topic)
        for decision in extraction.get("decisions", []):
            self.add_decision(org_name, decision)
        for pref in extraction.get("preferences", []):
            self.add_preference(org_name, pref)
