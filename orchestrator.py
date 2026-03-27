"""
Orchestrator — coordinates the multi-agent advisory team.
Week 3, Lonely Octopus AI Agent Bootcamp
Week 4: Added cost tracking, response caching, and spending limits.

Flow: User Question → Triage → Specialist(s) → Synthesis → Response
Uses the Hierarchical pattern with a triage router and synthesis combiner.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents.triage import TriageAgent
from agents.security import SecurityAgent
from agents.technology import TechnologyAgent
from agents.ai_readiness import AIReadinessAgent
from agents.conversation import ConversationAgent
from memory import SharedMemory
from cost_tracker import tracker as cost_tracker
from cache import cache

load_dotenv()
if not os.environ.get("ANTHROPIC_API_KEY"):
    load_dotenv(Path.home() / ".claude" / ".env")

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()

# Advisor names (same as week 2 for continuity)
ADVISOR_NAMES = [
    "Amara", "Priya", "Sofia", "Keiko", "Maya",
    "Luz", "Fatima", "Nia", "Elena", "Aisha",
    "Carmen", "Mei", "Tanya", "Aaliyah", "Rosa",
    "Gabriela", "Nkechi", "Suki", "Yara", "Ingrid",
    "Marcus", "David", "Ravi", "Carlos", "James",
    "Omar", "Andre", "Tomás", "Kwame", "Raj",
]

# Specialist registry
SPECIALISTS = {
    "security": SecurityAgent(),
    "technology": TechnologyAgent(),
    "ai": AIReadinessAgent(),
}

triage = TriageAgent()
conversation = ConversationAgent()
memory = SharedMemory()


def _pick_advisor_name(org_name: str) -> str:
    idx = int(hashlib.md5(org_name.encode()).hexdigest(), 16) % len(ADVISOR_NAMES)
    return ADVISOR_NAMES[idx]


def synthesize(
    question: str,
    org_profile: dict,
    specialist_results: list[dict],
    advisor_name: str,
) -> str:
    """
    Synthesis agent — combines specialist advice into a unified, coherent response.
    This is the final agent in the hierarchical chain.
    """
    # Build context from specialist findings
    specialist_context = ""
    for result in specialist_results:
        if result["response"] and not result["error"]:
            specialist_context += (
                f"\n## {result['emoji']} {result['agent']} ({result['domain'].title()})\n"
                f"{result['response']}\n"
            )

    if not specialist_context.strip():
        return (
            "I apologize, but I wasn't able to get input from our specialist team on this question. "
            "Could you try rephrasing it, or ask about a specific technology topic like CRM selection, "
            "cybersecurity, or AI adoption?"
        )

    system = f"""# Role
You are {advisor_name}, a personalized AI technology advisor from Meet the Moment (MTM).
You are the synthesis agent for a multi-agent advisory team. Your job is to combine
input from specialist agents into a single, coherent, actionable response for the user.

IMPORTANT: You are an AI advisor, not a human. Be transparent about this. Do NOT claim
to be a real person or invent credentials.

# Task
The user asked: "{question}"

Below is analysis from our specialist team. Synthesize their input into ONE clear,
well-structured response that:
1. Provides a unified answer (don't just list what each specialist said)
2. Resolves any conflicting recommendations
3. Prioritizes by impact and feasibility for this specific organization
4. Maintains a warm, professional tone
5. Uses headers, bullet points, and clear structure

# Constraints
- Don't reference the specialists by name or say "the security agent recommended..."
  Instead, integrate their advice naturally as if it came from one advisor
- Keep the response concise — use short paragraphs and bullet points
- Don't repeat information that appears in multiple specialist responses
- If only one specialist was consulted, polish and present their advice directly
- Always consider the org's budget and capacity when prioritizing

# Organization Profile
"""
    for key, value in org_profile.items():
        if value:
            system += f"- {key.replace('_', ' ').title()}: {value}\n"

    system += (
        "\n# App Features\n"
        "There is a 'Download as Word Doc' button in the sidebar for saving advice.\n"
        "Sessions are not saved after the page is closed.\n"
        "\nIMPORTANT — Response length: Keep responses concise and scannable. "
        "Use short paragraphs, bullet points, and headers. Avoid walls of text."
    )

    t0 = time.time()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Specialist team analysis:\n{specialist_context}",
        }],
    )
    latency_ms = int((time.time() - t0) * 1000)

    cost_tracker.record_call(
        model=MODEL,
        caller="Synthesis",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )

    return response.content[0].text


def evaluate_conversation(
    chat_history: list[dict],
    org_profile: dict,
) -> dict:
    """
    Conversation agent evaluates the current turn.
    Returns: {"action": "clarify"/"answer"/"route", ...}
    """
    org_name = org_profile.get("org_name", "Unknown")
    advisor_name = _pick_advisor_name(org_name)
    result = conversation.evaluate_turn(chat_history, org_profile, advisor_name)
    result["advisor_name"] = advisor_name
    return result


def run_advisory_team(
    question: str,
    org_profile: dict,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Run the full multi-agent pipeline on a user question.

    Returns:
        {
            "response": final synthesized text,
            "routing": triage classification result,
            "specialists": [specialist result dicts],
            "advisor_name": deterministic advisor name,
        }
    """
    org_name = org_profile.get("org_name", "Unknown")
    advisor_name = _pick_advisor_name(org_name)

    # Step 1: Triage — classify and route
    routing = triage.classify(question, org_profile)

    # Step 2: Run specialist agent(s)
    specialist_results = []

    # Primary specialist
    primary_domain = routing["primary"]
    if primary_domain in SPECIALISTS:
        primary_agent = SPECIALISTS[primary_domain]
        result = primary_agent.run(question, org_profile)
        specialist_results.append(result)

        # Track in memory
        memory.record_agent_consultation(org_name, result["agent"], result["domain"])

        # Add to shared context for secondary agent
        if result["response"]:
            memory.add_agent_finding(
                result["agent"], result["domain"],
                result["response"][:500],
            )

    # Secondary specialist (if routed)
    secondary_domain = routing.get("secondary")
    if secondary_domain and secondary_domain in SPECIALISTS and secondary_domain != primary_domain:
        secondary_agent = SPECIALISTS[secondary_domain]
        shared_ctx = memory.get_shared_context(exclude_domain=secondary_domain)
        result = secondary_agent.run(question, org_profile, shared_context=shared_ctx)
        specialist_results.append(result)
        memory.record_agent_consultation(org_name, result["agent"], result["domain"])

    # Step 3: Synthesis — combine specialist advice
    final_response = synthesize(question, org_profile, specialist_results, advisor_name)

    return {
        "response": final_response,
        "routing": routing,
        "specialists": specialist_results,
        "advisor_name": advisor_name,
    }


def generate_greeting(org_profile: dict) -> dict:
    """Generate a context-aware greeting using the full team."""
    org_name = org_profile.get("org_name", "your organization")
    advisor_name = _pick_advisor_name(org_name)

    system = f"""# Role
You are {advisor_name}, a personalized AI technology advisor from Meet the Moment (MTM).
You lead a team of specialist AI advisors covering cybersecurity, technology platforms,
and AI readiness for nonprofits.

IMPORTANT: You are an AI advisor, not a human. Introduce yourself as such.

# Task
This is the start of a new advising session. Briefly:
1. Introduce yourself as a personalized AI technology advisor from Meet the Moment
2. Mention you have a team of specialists in security, technology, and AI
3. Acknowledge the organization's profile
4. Suggest 3-5 specific technology topics they might want to explore, based on their
   profile and pain points. Present as a numbered list.
5. Note they can ask about anything — the list is just a starting point

# Constraints
- Keep it to 4-6 sentences plus the topic list
- Be warm but concise
- Don't claim to be human or invent credentials
"""

    system += "\n# Organization Profile\n"
    for key, value in org_profile.items():
        if value:
            system += f"- {key.replace('_', ' ').title()}: {value}\n"

    t0 = time.time()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": "Please introduce yourself and begin the advising session."}],
    )
    latency_ms = int((time.time() - t0) * 1000)

    cost_tracker.record_call(
        model=MODEL,
        caller="Greeting",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )

    return {
        "response": response.content[0].text,
        "advisor_name": advisor_name,
        "routing": None,
        "specialists": [],
    }


def extract_memory(org_name: str, user_message: str, assistant_response: str):
    """Extract and store conversation insights (best-effort, via Haiku)."""
    try:
        t0 = time.time()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                "Extract structured information from this conversation turn. "
                "Return JSON only, no other text."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"User: {user_message}\n\n"
                    f"Assistant: {assistant_response[:2000]}\n\n"
                    "Extract as JSON:\n"
                    '{"topics": ["..."], "decisions": ["..."], "preferences": ["..."]}\n'
                    "Only include clearly stated items. Return empty lists if nothing applies."
                ),
            }],
        )
        latency_ms = int((time.time() - t0) * 1000)

        cost_tracker.record_call(
            model="claude-haiku-4-5-20251001",
            caller="Memory Extraction",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        extraction = json.loads(text)
        memory.update_from_extraction(org_name, extraction)
    except (json.JSONDecodeError, IndexError, KeyError, anthropic.APIError):
        pass  # Memory extraction is best-effort