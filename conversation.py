"""
Conversation Agent — asks clarifying questions before routing to specialists.
Inspired by the InterviewPrompt skill: one question at a time, adaptive flow.
Week 4: Added cost tracking.

Uses a faster model (Sonnet) since this is conversational, not tool-heavy.
Decides each turn whether to: clarify, answer directly, or route to specialists.
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

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()

SYSTEM_PROMPT = """# Role
You are {advisor_name}, a personalized AI technology advisor from Meet the Moment (MTM).
You lead a team of specialist advisors covering cybersecurity, technology platforms,
and AI readiness for nonprofits.

IMPORTANT: You are an AI advisor, not a human.

# Behavior
You are the CONVERSATION agent. Your job is to have a natural dialogue with the user
BEFORE routing their question to specialist agents. Good advisors ask questions first.

Each turn, you MUST decide ONE action:

1. **clarify** — Ask ONE focused clarifying question to better understand their need.
   Use this when you don't yet have enough context to give good advice.

2. **answer** — Answer simple, factual questions directly. No need for specialists.
   Use this for definitions, quick explanations, or simple yes/no questions.
   Examples: "What is MFA?", "What does CRM stand for?", "Do we need cyber insurance?"

3. **route** — You have enough context. Send to the specialist team for a full answer.
   Use this after 2-3 clarifying exchanges OR when the question is detailed enough already.

# Question Design (from InterviewPrompt methodology)
- ONE question at a time — never overwhelm
- Be specific — "What CRM are you using now?" not "Tell me about your tech"
- Acknowledge what they said before asking the next question
- Ask about: current state, pain points, constraints, desired outcome, timeline

# Decision Rules
- If the question is simple/factual → **answer** immediately
- If the question is broad but you've already asked 2-3 questions in this thread → **route**
- If you have org profile context AND a specific enough question → **route**
- Otherwise → **clarify** with ONE question

# Response Format
Return JSON only. No other text.

For **clarify**:
{{"action": "clarify", "question": "Your single clarifying question here", "what_i_know": "Brief summary of what you know so far", "what_i_need": "What this question will help clarify"}}

For **answer**:
{{"action": "answer", "response": "Your direct answer here. Keep it concise and helpful."}}

For **route**:
{{"action": "route", "refined_question": "Enhanced version of the original question incorporating all clarifying context", "summary": "Brief context summary for the specialist team"}}

# Organization Profile
{org_context}
"""


class ConversationAgent:
    """Asks 2-3 clarifying questions before routing to specialists."""

    name = "Conversation Agent"
    emoji = "💬"

    def evaluate_turn(
        self,
        chat_history: list[dict],
        org_profile: dict,
        advisor_name: str = "Maya",
    ) -> dict:
        """
        Evaluate the current conversation turn and decide: clarify, answer, or route.

        Args:
            chat_history: Full conversation history [{"role": "user"/"assistant", "content": "..."}]
            org_profile: Organization profile dict
            advisor_name: Deterministic advisor name

        Returns:
            {"action": "clarify", "question": "..."} or
            {"action": "answer", "response": "..."} or
            {"action": "route", "refined_question": "...", "summary": "..."}
        """
        # Build org context string
        org_lines = []
        for key, value in org_profile.items():
            if value:
                org_lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        org_context = "\n".join(org_lines) if org_lines else "No profile provided."

        system = SYSTEM_PROMPT.format(
            advisor_name=advisor_name,
            org_context=org_context,
        )

        # Count how many clarifying exchanges have happened
        clarify_count = sum(
            1 for msg in chat_history
            if msg["role"] == "assistant" and msg.get("is_clarifying")
        )

        # Add a hint about clarification count
        if clarify_count >= 2:
            system += (
                f"\n\nNOTE: You have already asked {clarify_count} clarifying questions. "
                "You should now either **answer** directly or **route** to specialists "
                "unless the question is still completely unclear."
            )

        # Build messages for the API call (strip internal metadata)
        api_messages = []
        for msg in chat_history:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        try:
            t0 = time.time()
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=system,
                messages=api_messages,
            )
            latency_ms = int((time.time() - t0) * 1000)

            cost_tracker.record_call(
                model=MODEL,
                caller="Conversation",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
            )

            text = response.content[0].text.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)

            # Validate action
            if result.get("action") not in ("clarify", "answer", "route"):
                result["action"] = "route"
                result["refined_question"] = chat_history[-1]["content"]
                result["summary"] = "Could not determine action"

            return result

        except (json.JSONDecodeError, anthropic.APIError, KeyError, IndexError):
            # On failure, route to specialists with the raw question
            return {
                "action": "route",
                "refined_question": chat_history[-1]["content"] if chat_history else "",
                "summary": "Conversation agent fallback — routing directly",
            }
