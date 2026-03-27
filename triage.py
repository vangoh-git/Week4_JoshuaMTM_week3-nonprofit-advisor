"""
Triage Agent — classifies questions and routes to specialist agents.
Week 3, Lonely Octopus AI Agent Bootcamp
Week 4: Added cost tracking.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from cost_tracker import tracker as cost_tracker

load_dotenv()
if not os.environ.get("ANTHROPIC_API_KEY"):
    load_dotenv(Path.home() / ".claude" / ".env")

MODEL = "claude-haiku-4-5-20251001"  # Haiku for fast classification
client = anthropic.Anthropic()

# Domain definitions for routing
DOMAINS = {
    "security": {
        "keywords": [
            "security", "cybersecurity", "mfa", "phishing", "breach", "ransomware",
            "compliance", "hipaa", "privacy", "incident", "backup", "recovery",
            "firewall", "encryption", "password", "cis controls", "vulnerability",
            "threat", "risk", "insurance", "cyber insurance", "pci", "gdpr",
            "data protection", "audit", "penetration test",
        ],
        "description": "Cybersecurity, data privacy, compliance, incident response",
    },
    "technology": {
        "keywords": [
            "crm", "salesforce", "bloomerang", "microsoft 365", "google workspace",
            "email", "website", "cloud", "migration", "server", "hardware",
            "software", "it staffing", "msp", "vcio", "project management",
            "asana", "monday", "volunteer", "grant management", "budget",
            "techsoup", "remote work", "vpn", "infrastructure", "platform",
            "slack", "teams", "sharepoint", "quickbooks", "mailchimp",
            "squarespace", "wordpress", "accessibility", "wcag",
        ],
        "description": "CRM, infrastructure, productivity, operations, vendor selection",
    },
    "ai": {
        "keywords": [
            "ai", "artificial intelligence", "chatgpt", "claude", "copilot",
            "gemini", "machine learning", "compas", "ai policy", "llm",
            "prompt", "automation", "ai training", "ai adoption", "generative",
            "shadow ai", "ai governance", "board ai", "ai risks", "hallucination",
            "ai writing", "grant writing ai", "ai tools", "ai privacy",
        ],
        "description": "AI adoption, COMPAS framework, AI policy, platform selection",
    },
}


class TriageAgent:
    """Routes questions to the appropriate specialist agent(s)."""

    name = "Triage"
    emoji = "🔀"

    def classify(self, question: str, org_profile: dict) -> dict:
        """
        Classify a question and determine which specialists to consult.

        Returns:
            {
                "primary": "security" | "technology" | "ai",
                "secondary": "..." | None,
                "reasoning": "...",
                "refined_question": "...",
            }
        """
        # First pass: keyword scoring for speed
        question_lower = question.lower()
        scores = {}
        for domain, info in DOMAINS.items():
            score = sum(1 for kw in info["keywords"] if kw in question_lower)
            if score > 0:
                scores[domain] = score

        # If keyword match is clear (one domain dominates), use fast path
        if scores:
            sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top_score = sorted_domains[0][1]
            if top_score >= 3 and (len(sorted_domains) == 1 or sorted_domains[1][1] < top_score * 0.5):
                primary = sorted_domains[0][0]
                return {
                    "primary": primary,
                    "secondary": None,
                    "reasoning": f"Strong keyword match for {primary} ({top_score} matches)",
                    "refined_question": question,
                }

        # Second pass: use LLM for nuanced classification
        try:
            t0 = time.time()
            response = client.messages.create(
                model=MODEL,
                max_tokens=256,
                system=(
                    "You are a triage agent that classifies nonprofit technology questions. "
                    "Classify the question into one or two domains and return JSON only.\n\n"
                    "Domains:\n"
                    "- security: cybersecurity, data privacy, compliance, incident response, backup\n"
                    "- technology: CRM, productivity tools, infrastructure, cloud, IT operations, websites\n"
                    "- ai: AI adoption, ChatGPT/Claude/Copilot, AI policy, AI training, COMPAS framework\n\n"
                    "Return: {\"primary\": \"domain\", \"secondary\": \"domain_or_null\", \"reasoning\": \"brief why\"}"
                ),
                messages=[{
                    "role": "user",
                    "content": f"Question: {question}\n\nOrg budget: {org_profile.get('budget_tier', 'unknown')}, "
                               f"Cause area: {org_profile.get('cause_area', 'unknown')}",
                }],
            )
            latency_ms = int((time.time() - t0) * 1000)

            cost_tracker.record_call(
                model=MODEL,
                caller="Triage",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
            )

            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)
            primary = result.get("primary")
            # Validate that primary is a known domain; default to technology if not
            if primary not in DOMAINS:
                primary = "technology"
            secondary = result.get("secondary")
            if secondary not in DOMAINS or secondary == primary:
                secondary = None
            return {
                "primary": primary,
                "secondary": secondary,
                "reasoning": result.get("reasoning", "LLM classification"),
                "refined_question": question,
            }

        except (json.JSONDecodeError, anthropic.APIError, KeyError, IndexError):
            # Fallback: use keyword scores if available, else default to technology
            if scores:
                sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                return {
                    "primary": sorted_domains[0][0],
                    "secondary": sorted_domains[1][0] if len(sorted_domains) > 1 else None,
                    "reasoning": "Keyword fallback after LLM classification failed",
                    "refined_question": question,
                }
            return {
                "primary": "technology",
                "secondary": None,
                "reasoning": "Default fallback — could not classify",
                "refined_question": question,
            }
