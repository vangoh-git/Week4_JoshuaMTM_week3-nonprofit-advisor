"""
Base agent class — shared infrastructure for all specialist agents.
Week 3, Lonely Octopus AI Agent Bootcamp
Week 4: Added cost tracking, caching, and latency measurement.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import List

import anthropic
from dotenv import load_dotenv

from cost_tracker import tracker as cost_tracker
from cache import cache

# Load API key
load_dotenv()
if not os.environ.get("ANTHROPIC_API_KEY"):
    load_dotenv(Path.home() / ".claude" / ".env")

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()


class BaseAgent:
    """Base class for all specialist agents in the advisory team."""

    name: str = "Base Agent"
    domain: str = "general"
    emoji: str = "🤖"
    description: str = "A specialist agent."
    kb_file: str | None = None

    def __init__(self):
        self.knowledge_base = self._load_kb() if self.kb_file else []
        self.tool_definitions = self._build_tools()

    def _load_kb(self) -> list[dict]:
        """Load domain-specific knowledge base."""
        kb_path = Path(__file__).parent.parent / "knowledge" / self.kb_file
        if kb_path.exists():
            with open(kb_path) as f:
                return json.load(f)
        return []

    def _build_tools(self) -> list[dict]:
        """Build tool definitions — each specialist gets KB search + Wikipedia."""
        tools = []
        if self.knowledge_base:
            tools.append({
                "name": f"search_{self.domain}_knowledge",
                "description": (
                    f"Search the {self.domain} knowledge base for guidance on "
                    f"{self.description}. Use this to ground advice in curated best practices."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query — topic, tool name, or question keywords",
                        },
                        "budget_tier": {
                            "type": "string",
                            "enum": ["small", "large", "all"],
                            "description": "Filter by budget: 'small' (<$5M), 'large' ($5M+), 'all'",
                        },
                    },
                    "required": ["query"],
                },
            })

        tools.append({
            "name": "fetch_wikipedia_summary",
            "description": (
                "Fetch a plain-language summary of a concept from Wikipedia. "
                "Use for general technology terms, standards, or frameworks."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to look up",
                    },
                },
                "required": ["topic"],
            },
        })

        return tools

    def search_knowledge(self, query: str, budget_tier: str = "all") -> list[dict]:
        """Search this agent's domain knowledge base (with caching)."""
        # Check cache first
        cache_key = cache.kb_key(self.domain, query, budget_tier)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        query_lower = query.lower()
        stop_words = {"", "a", "the", "for", "and", "or", "is", "in", "to", "of", "my", "our", "we"}
        query_words = set(re.split(r"\W+", query_lower)) - stop_words

        scored = []
        for entry in self.knowledge_base:
            if budget_tier != "all" and entry["budget_tier"] not in (budget_tier, "all"):
                continue

            score = 0
            searchable = f"{entry['title']} {' '.join(entry['keywords'])} {entry['category']}".lower()

            for word in query_words:
                if word in searchable:
                    score += 2
                if word in entry["content"].lower():
                    score += 1

            for kw in entry["keywords"]:
                if kw in query_lower:
                    score += 3

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [
            {"title": e["title"], "content": e["content"], "category": e["category"]}
            for _, e in scored[:3]
        ]

        if not results:
            results = [{"title": "No results", "content": f"No {self.domain} knowledge base entries matched '{query}'.", "category": "none"}]

        # Cache the results (10 min TTL for KB searches)
        cache.set(cache_key, results, ttl=600)
        return results

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call from the agent."""
        if tool_name.startswith("search_") and tool_name.endswith("_knowledge"):
            results = self.search_knowledge(
                query=tool_input["query"],
                budget_tier=tool_input.get("budget_tier", "all"),
            )
            return json.dumps(results, indent=2)
        elif tool_name == "fetch_wikipedia_summary":
            return self._fetch_wikipedia(tool_input["topic"])
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def _fetch_wikipedia(self, topic: str) -> str:
        """Fetch Wikipedia summary."""
        import requests
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "MTM-Advisor/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                return f"**{data.get('title', topic)}**: {data.get('extract', 'No summary available.')}"
            elif resp.status_code == 404:
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(topic)}&format=json&srlimit=1"
                search_resp = requests.get(search_url, timeout=10, headers={"User-Agent": "MTM-Advisor/2.0"})
                if search_resp.status_code == 200:
                    results = search_resp.json().get("query", {}).get("search", [])
                    if results:
                        title = results[0]["title"]
                        retry_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
                        retry_resp = requests.get(retry_url, timeout=10, headers={"User-Agent": "MTM-Advisor/2.0"})
                        if retry_resp.status_code == 200:
                            data = retry_resp.json()
                            return f"**{data.get('title', topic)}**: {data.get('extract', 'No summary available.')}"
                return f"Could not find a Wikipedia article for '{topic}'."
            else:
                return f"Wikipedia API returned status {resp.status_code} for '{topic}'."
        except Exception as e:
            return f"Error fetching Wikipedia summary: {e}"

    def build_system_prompt(self, org_profile: dict, shared_context: str = "") -> str:
        """Build the specialist system prompt — subclasses override for domain specifics."""
        raise NotImplementedError

    def run(self, question: str, org_profile: dict, shared_context: str = "") -> dict:
        """
        Run this specialist agent on a question.

        Returns:
            {
                "agent": agent name,
                "domain": domain,
                "response": text response,
                "tool_calls": [{tool, input, result}, ...],
                "error": None or error message,
            }
        """
        system = self.build_system_prompt(org_profile, shared_context)
        messages = [{"role": "user", "content": question}]
        tool_calls_log = []

        try:
            # Check spending limit before proceeding
            if cost_tracker.limit_reached:
                return {
                    "agent": self.name,
                    "domain": self.domain,
                    "emoji": self.emoji,
                    "response": "Session spending limit reached. Please start a new session to continue.",
                    "tool_calls": [],
                    "error": "spending_limit",
                }

            # Agentic loop
            for _ in range(5):  # Max 5 tool iterations as safety limit
                t0 = time.time()
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=system,
                    tools=self.tool_definitions,
                    messages=messages,
                )
                latency_ms = int((time.time() - t0) * 1000)

                # Track cost
                usage = response.usage
                cost_tracker.record_call(
                    model=MODEL,
                    caller=self.name,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    latency_ms=latency_ms,
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = self.execute_tool(block.name, block.input)
                            tool_calls_log.append({
                                "tool": block.name,
                                "input": block.input,
                                "result": result,
                            })
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})
                else:
                    text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            text += block.text

                    return {
                        "agent": self.name,
                        "domain": self.domain,
                        "emoji": self.emoji,
                        "response": text,
                        "tool_calls": tool_calls_log,
                        "error": None,
                    }

            # If we hit the loop limit
            return {
                "agent": self.name,
                "domain": self.domain,
                "emoji": self.emoji,
                "response": "I reached my tool-use limit. Here's what I found so far based on available information.",
                "tool_calls": tool_calls_log,
                "error": "max_iterations",
            }

        except anthropic.APIError as e:
            return {
                "agent": self.name,
                "domain": self.domain,
                "emoji": self.emoji,
                "response": "",
                "tool_calls": tool_calls_log,
                "error": f"API error: {e}",
            }
