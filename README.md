# Nonprofit Technology Advisory Team

**Weeks 3 & 4 — Lonely Octopus AI Agent Bootcamp**
Built by Joshua Peskay | Meet the Moment (mtm.now)

## What Is This?

A **multi-agent AI advisory system** that provides tailored technology guidance to nonprofits. Six specialized agents collaborate using the **Hierarchical design pattern** to deliver better advice than any single agent could alone.

**Week 4** adds production-readiness: cost monitoring, response caching, a test suite, and spending limits.

## Architecture

```
User Question
     |
+-----------------+
|  CONVERSATION    |  Asks clarifying questions before routing
|  AGENT           |  Decides: clarify / answer / route
+----+------------+
     |
+----+------------+
|  TRIAGE AGENT    |  Classifies question -> routes to 1-2 specialists
|  (Router)        |  Uses: keyword scoring + LLM fallback
+----+----+-------+
     |    |
+--------+ +--------+
|Security| |  Tech  |  Each specialist has:
|Advisor | |Advisor |  - Domain-specific system prompt
+---+----+ +---+----+  - Own knowledge base slice (cached)
    |          |       - Tool-use loop (KB search + Wikipedia)
    |          |
+---+----------+----+
| SYNTHESIS AGENT    |  Combines specialist advice into unified response
| (Combiner)         |  Resolves conflicts, prioritizes by budget/capacity
+----+---------------+
     |
+----+-----------+     +------------------+
| SHARED MEMORY  |     | COST TRACKER     |  (Week 4)
| Persistent JSON|     | Token counting   |
| + session pad  |     | Budget limits    |
+----------------+     | Per-agent costs  |
                       +------------------+
```

## The Six Agents

| Agent | Role | Domain | Model | Tools |
|-------|------|--------|-------|-------|
| **Conversation** | Initial Q&A | Clarification | Sonnet | LLM-only |
| **Triage** | Coordination | Routing | Haiku | Keyword scorer + LLM |
| **Security Advisor** | Analysis | Cybersecurity, compliance, privacy | Sonnet | KB search, Wikipedia |
| **Technology Advisor** | Retrieval | CRM, infrastructure, IT ops | Sonnet | KB search, Wikipedia |
| **AI Readiness Advisor** | Analysis | COMPAS, AI policy, training | Sonnet | KB search, Wikipedia |
| **Synthesis** | Combiner | Unified response | Sonnet | LLM-only |

## Week 4: Production Features

### Cost Monitoring

Real-time token and cost tracking across all agents:

- **Per-call tracking**: model, input/output tokens, estimated cost, latency
- **Session dashboard**: live spending bar, budget alerts, per-agent breakdown
- **Hard spending limit**: configurable per-session cap (default $1.00) with graceful cutoff
- **Soft alerts**: warning at 70% of budget
- **Model-level breakdown**: see Sonnet vs. Haiku spending

### Response Caching

Reduces redundant API calls and KB searches:

- **KB search cache**: 10-minute TTL, deduplicates identical domain queries
- **Cache hit tracking**: visible hit rate in the sidebar dashboard
- **Deterministic keys**: same query + domain + budget tier = cache hit

### Test Suite (14 tests)

```bash
pytest tests/test_eval_suite.py -v
```

| Category | Tests | What's Tested |
|----------|-------|---------------|
| Normal flows | 2 | CRM -> Technology, MFA -> Security routing |
| Edge cases | 3 | Empty input, mixed domains, no KB results |
| Error scenarios | 2 | API failure handling, malformed KB entries |
| Adversarial | 2 | Prompt injection, off-topic questions |
| Cost/Cache | 3 | Token tracking, cache hits, spending limits |
| Memory | 2 | Persistence, cross-agent context sharing |

### Production Checklist

| # | Item | Status |
|---|------|--------|
| 1 | API keys in environment variables | Done |
| 2 | Spending limits configured | Done ($1.00/session) |
| 3 | Environments separated (dev/staging/prod) | Done (.env.example) |
| 4 | Model selection finalized | Done (Sonnet + Haiku) |
| 5 | Test suite created and passing | Done (14/14) |
| 6 | Error handling implemented | Done (fallbacks at every layer) |
| 7 | Security measures in place | Done (input validation, domain routing) |
| 8 | Content filtering active | Done (agent stays in domain lane) |
| 9 | Monitoring dashboard set up | Done (cost sidebar) |
| 10 | Alerts configured | Done (70% soft, 100% hard) |
| 11 | Cost optimization applied | Done (caching, Haiku for triage) |
| 12 | Scaling plan documented | See below |

### Scaling Plan

| Scale | Approach |
|-------|----------|
| 0-100 users | Streamlit Community Cloud (current) |
| 100-1K | Add Redis cache, database for memory |
| 1K+ | Queue system, async agents, load balancing |

## Error Handling & Fallbacks

| Scenario | Handling |
|----------|---------|
| LLM triage fails | Falls back to keyword scoring |
| LLM returns invalid domain | Validated + defaults to Technology |
| No keywords match | Defaults to Technology specialist |
| Specialist API error | Returns error in result, synthesis works with available data |
| Tool-use loop exceeds 5 iterations | Safety break, returns partial results |
| No specialist produces useful output | Synthesis returns helpful error message |
| Wikipedia API timeout | Returns graceful error string, agent continues |
| Session spending limit reached | Agents refuse to run, user sees clear message |

## Running Locally

```bash
# Clone
git clone https://github.com/joshuamtm/week3-nonprofit-advisor.git
cd week3-nonprofit-advisor

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run
streamlit run app.py

# Test
pytest tests/test_eval_suite.py -v
```

## File Structure

```
week3-nonprofit-advisor/
├── agents/
│   ├── __init__.py          # Agent exports
│   ├── base.py              # BaseAgent (KB search, tool loop, Wikipedia, cost tracking)
│   ├── triage.py            # TriageAgent (keyword + LLM classification)
│   ├── security.py          # SecurityAgent (cybersecurity specialist)
│   ├── technology.py        # TechnologyAgent (CRM, infrastructure specialist)
│   ├── ai_readiness.py      # AIReadinessAgent (COMPAS, AI policy specialist)
│   └── conversation.py      # ConversationAgent (clarifying questions)
├── knowledge/
│   ├── security.json        # 6 security-focused KB entries
│   ├── technology.json      # 16 technology/ops KB entries
│   └── ai.json              # 13 AI adoption KB entries
├── tests/
│   ├── conftest.py          # Shared test fixtures
│   └── test_eval_suite.py   # 14-test production evaluation suite
├── data/
│   └── memory.json          # Persistent shared memory (gitignored)
├── orchestrator.py          # Multi-agent coordinator + synthesis
├── memory.py                # SharedMemory class (persistent + session)
├── cost_tracker.py          # Token/cost monitoring + spending limits (Week 4)
├── cache.py                 # Response caching for KB searches (Week 4)
├── export.py                # Word doc export with MTM branding
├── session_io.py            # Session save/resume
├── app.py                   # Streamlit UI with cost dashboard
├── requirements.txt         # Python dependencies
├── .env.example             # API key template
└── README.md                # This file
```

## Stack

- **LLM**: Anthropic Claude (Sonnet 4.6 for agents, Haiku 4.5 for triage + memory)
- **Framework**: Streamlit
- **Tools**: Knowledge base search (per-domain, cached), Wikipedia REST API
- **Monitoring**: Custom cost tracker with per-agent breakdown
- **Testing**: pytest (14 tests across 6 categories)
- **Export**: python-docx with MTM branding

## Credits

Built by Joshua Peskay, Co-Founder of [Meet the Moment](https://mtm.now).
Co-authored with Claude (Anthropic).
