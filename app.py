"""
Nonprofit Technology Advisory Team — Streamlit UI
Week 3 Assignment, Lonely Octopus AI Agent Bootcamp

Demonstrates: Multi-Agent System (Hierarchical Pattern)
  - Triage Agent → routes to specialists
  - 3 Specialist Agents (Security, Technology, AI Readiness)
  - Synthesis Agent → combines advice
  - Shared Memory across agents and sessions

Run: streamlit run app.py
"""

import json

import streamlit as st
from orchestrator import run_advisory_team, evaluate_conversation, generate_greeting, extract_memory, memory
from export import generate_docx
from session_io import serialize_session, parse_session
from cost_tracker import tracker as cost_tracker, reset_tracker
from cache import cache

# --- Page Config ---
st.set_page_config(
    page_title="MTM Nonprofit Tech Advisory Team",
    page_icon="favicon.png",
    layout="wide",
)

# --- Custom CSS ---
st.markdown(
    """
    <style>
    .mtm-header {
        background: linear-gradient(135deg, #0891b2 0%, #0e7490 50%, #155e75 100%);
        padding: 24px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
    }
    .pillar-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
        margin: 4px;
    }
    .pillar-multi { background: #f3e8ff; color: #7c3aed; }
    .pillar-memory { background: #dbeafe; color: #1e40af; }
    .pillar-tools { background: #ffedd5; color: #9a3412; }
    .pillar-context { background: #dcfce7; color: #166534; }

    .agent-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
    }
    .agent-card-header {
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 4px;
    }
    .routing-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .route-security { background: #fee2e2; color: #991b1b; }
    .route-technology { background: #dbeafe; color: #1e40af; }
    .route-ai { background: #f3e8ff; color: #7c3aed; }
    .route-triage { background: #fef3c7; color: #92400e; }

    .mtm-footer {
        text-align: center;
        color: #85abbd;
        font-size: 12px;
        margin-top: 40px;
        padding-top: 16px;
        border-top: 1px solid #e5e7eb;
    }
    .mtm-footer a { color: #1ab1d2; text-decoration: none; }

    .tool-log {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        font-size: 13px;
        margin-top: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Session State Init ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "org_profile" not in st.session_state:
    st.session_state.org_profile = {}
if "advising_started" not in st.session_state:
    st.session_state.advising_started = False
if "agent_logs" not in st.session_state:
    st.session_state.agent_logs = {}

ROUTE_COLORS = {
    "security": "route-security",
    "technology": "route-technology",
    "ai": "route-ai",
}

# --- Sidebar: Org Profile ---
with st.sidebar:
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0891b2, #0e7490, #155e75);
                    padding: 16px; border-radius: 8px; margin-bottom: 16px;">
            <p style="color: white; font-weight: 600; font-size: 16px; margin: 0;">
                Organization Profile
            </p>
            <p style="color: rgba(255,255,255,0.8); font-size: 12px; margin: 4px 0 0 0;">
                Tell us about your nonprofit
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    org_name = st.text_input("Organization Name", placeholder="e.g., Hope Community Center")

    budget_tier = st.selectbox(
        "Annual Budget",
        ["", "Under $1M", "Under $5M", "$5M – $20M", "$20M – $100M", "Over $100M"],
    )

    staff_count = st.text_input("Staff Count", placeholder="e.g., 35")

    cause_area = st.selectbox(
        "Cause Area",
        [
            "", "Arts & Culture", "Community Services", "Education", "Environment",
            "Health & Human Services", "Housing & Homelessness",
            "International Development", "Social Justice & Advocacy",
            "Workforce Development", "Youth Development", "Other",
        ],
    )

    st.markdown(
        "**Current Tech Stack**  \n"
        '<span style="color: #64748b; font-size: 13px;">'
        "Select what's relevant</span>",
        unsafe_allow_html=True,
    )

    tech_options = {
        "Google Workspace": "Google Workspace",
        "Microsoft 365": "Microsoft 365",
        "Salesforce": "Salesforce / NPSP",
        "QuickBooks": "QuickBooks",
        "Spreadsheets": "Spreadsheets",
        "Mailchimp": "Mailchimp",
        "Zoom": "Zoom",
        "Slack": "Slack",
        "WordPress": "WordPress",
        "ChatGPT": "ChatGPT",
        "Microsoft Copilot": "Microsoft Copilot",
        "Google Gemini": "Google Gemini",
        "Claude": "Claude",
        "Paper/manual": "Paper/manual processes",
    }

    selected_tech = []
    cols = st.columns(2)
    for i, (key, label) in enumerate(tech_options.items()):
        with cols[i % 2]:
            if st.checkbox(label, key=f"tech_{key}"):
                selected_tech.append(key)

    other_tech = st.text_input("Other tools", placeholder="e.g., Bloomerang, Asana")
    current_tech = ", ".join(selected_tech)
    if other_tech.strip():
        current_tech = f"{current_tech}, {other_tech.strip()}" if current_tech else other_tech.strip()

    pain_points = st.text_area("Top Technology Pain Points", placeholder="e.g., No CRM, security concerns", height=80)

    st.markdown(
        "**IT Support**  \n"
        '<span style="color: #64748b; font-size: 13px;">Select all that apply</span>',
        unsafe_allow_html=True,
    )

    it_options = {
        "No dedicated IT staff": "No dedicated IT staff",
        "IT generalist": "Internal IT generalist",
        "IT team": "Internal IT team (2+)",
        "MSP": "Outsourced IT / MSP",
        "Fractional CIO/CTO": "Fractional CIO/CTO",
        "Fractional CISO": "Fractional CISO",
        "Fractional CAIO": "Fractional CAIO",
        "IT-savvy staff": "Non-IT staff handle tech",
    }

    selected_it = []
    it_cols = st.columns(2)
    for i, (key, label) in enumerate(it_options.items()):
        with it_cols[i % 2]:
            if st.checkbox(label, key=f"it_{key}"):
                selected_it.append(key)

    it_capacity = ", ".join(selected_it) if selected_it else ""

    st.markdown("---")

    start_button = st.button("Start Advising", type="primary", use_container_width=True)

    if start_button and org_name.strip():
        profile = {
            "org_name": org_name.strip(),
            "budget_tier": budget_tier,
            "staff_count": staff_count,
            "cause_area": cause_area,
            "current_tech": current_tech,
            "pain_points": pain_points,
            "it_capacity": it_capacity,
        }
        st.session_state.org_profile = profile
        st.session_state.advising_started = True
        st.session_state.messages = []
        st.session_state.agent_logs = {}
        st.rerun()
    elif start_button:
        st.warning("Please enter an organization name.")

    # Dashboard
    if st.session_state.advising_started:
        st.markdown("---")
        st.markdown("**Multi-Agent Dashboard**")

        profile = st.session_state.org_profile
        has_memory = memory.has_org(profile.get("org_name", ""))
        session_count = 0
        if has_memory:
            org_data = memory.get_org(profile["org_name"])
            session_count = org_data.get("session_count", 0) if org_data else 0

        # Count total specialist invocations
        specialist_count = sum(
            len(log.get("specialists", []))
            for log in st.session_state.agent_logs.values()
        )
        tool_count = sum(
            sum(len(s.get("tool_calls", [])) for s in log.get("specialists", []))
            for log in st.session_state.agent_logs.values()
        )

        st.markdown(
            f'<span class="pillar-badge pillar-context">Context: {profile.get("org_name", "N/A")}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="pillar-badge pillar-multi">Agents: {specialist_count} consultations</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="pillar-badge pillar-tools">Tools: {tool_count} calls</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="pillar-badge pillar-memory">Memory: {"Session #" + str(session_count) if has_memory else "New org"}</span>',
            unsafe_allow_html=True,
        )

    # Cost Monitoring Dashboard (Week 4)
    if st.session_state.advising_started:
        st.markdown("---")
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #059669, #047857);
                        padding: 12px 16px; border-radius: 8px; margin-bottom: 12px;">
                <p style="color: white; font-weight: 600; font-size: 14px; margin: 0;">
                    Cost Monitor
                </p>
                <p style="color: rgba(255,255,255,0.8); font-size: 11px; margin: 2px 0 0 0;">
                    Session spending & usage tracking
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        budget = cost_tracker.check_budget()
        cache_stats = cache.get_stats()

        # Budget bar
        pct = min(budget["percent"], 100)
        bar_color = "#ef4444" if budget["status"] == "exceeded" else (
            "#f59e0b" if budget["status"] == "warning" else "#10b981"
        )
        st.markdown(
            f'<div style="background: #e5e7eb; border-radius: 8px; height: 12px; margin: 8px 0;">'
            f'<div style="background: {bar_color}; width: {pct}%; height: 12px; '
            f'border-radius: 8px; transition: width 0.3s;"></div></div>',
            unsafe_allow_html=True,
        )

        if budget["status"] == "exceeded":
            st.error("Session spending limit reached!")
        elif budget["status"] == "warning":
            st.warning(f"Approaching limit ({budget['percent']:.0f}%)")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Session Cost", f"${budget['spent']:.4f}")
        with col2:
            st.metric("API Calls", budget["calls"])

        col3, col4 = st.columns(2)
        with col3:
            st.metric("Tokens In", f"{cost_tracker.total_input_tokens:,}")
        with col4:
            st.metric("Tokens Out", f"{cost_tracker.total_output_tokens:,}")

        # Cache stats
        if cache_stats["hits"] + cache_stats["misses"] > 0:
            st.caption(
                f"Cache: {cache_stats['hit_rate']}% hit rate "
                f"({cache_stats['hits']} hits / {cache_stats['active_entries']} entries)"
            )

        # Cost breakdown by agent (expandable)
        if cost_tracker.calls:
            with st.expander("Cost Breakdown"):
                breakdown = cost_tracker.get_breakdown_by_caller()
                for caller, data in sorted(breakdown.items(), key=lambda x: x[1]["cost"], reverse=True):
                    st.markdown(
                        f"**{caller}**: ${data['cost']:.4f} "
                        f"({data['calls']} calls, {data['input_tokens'] + data['output_tokens']:,} tokens)"
                    )

                st.markdown("---")
                model_breakdown = cost_tracker.get_breakdown_by_model()
                for model, data in model_breakdown.items():
                    short_name = "Sonnet" if "sonnet" in model else "Haiku" if "haiku" in model else model
                    st.caption(f"{short_name}: ${data['cost']:.4f} ({data['calls']} calls)")

    # Save session + reset
    if st.session_state.advising_started:
        st.markdown("---")

        if st.session_state.messages:
            st.markdown("**Save Your Advice**")
            profile = st.session_state.org_profile
            docx_bytes = generate_docx(
                st.session_state.messages, profile, st.session_state.agent_logs,
            )
            org_slug = profile.get("org_name", "session").lower().replace(" ", "-")

            st.download_button(
                label="Download as Word Doc",
                data=docx_bytes,
                file_name=f"mtm-advice-{org_slug}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

            # Save session for resuming later
            st.markdown("**Resume Later**")
            session_md = serialize_session(profile, st.session_state.messages)

            st.download_button(
                label="Save Session (.md)",
                data=session_md.encode("utf-8"),
                file_name=f"mtm-session-{org_slug}.md",
                mime="text/markdown",
                use_container_width=True,
                help="Download this file to resume your session later. Upload it on the home page to continue.",
            )

        st.markdown("---")
        if st.button("New Organization", use_container_width=True):
            st.session_state.advising_started = False
            st.session_state.messages = []
            st.session_state.org_profile = {}
            st.session_state.agent_logs = {}
            st.rerun()


def _render_agent_transparency(log: dict):
    """Render the multi-agent transparency panel for a response."""
    routing = log.get("routing")
    specialists = log.get("specialists", [])

    if not routing and not specialists:
        return

    label_parts = []
    if routing:
        label_parts.append(f"Routed to: {routing['primary']}")
        if routing.get("secondary"):
            label_parts.append(f"+ {routing['secondary']}")
    label_parts.append(f"({len(specialists)} specialist{'s' if len(specialists) != 1 else ''})")

    with st.expander(f"Multi-Agent Pipeline: {' '.join(label_parts)}"):
        # Triage
        if routing:
            st.markdown(
                f'<span class="routing-badge route-triage">🔀 Triage</span> '
                f'→ <span class="routing-badge {ROUTE_COLORS.get(routing["primary"], "")}">'
                f'{routing["primary"].title()}</span>',
                unsafe_allow_html=True,
            )
            if routing.get("secondary"):
                st.markdown(
                    f'&nbsp;&nbsp;&nbsp;→ <span class="routing-badge {ROUTE_COLORS.get(routing["secondary"], "")}">'
                    f'{routing["secondary"].title()}</span>',
                    unsafe_allow_html=True,
                )
            st.caption(f"Reasoning: {routing.get('reasoning', 'N/A')}")
            st.markdown("---")

        # Specialist details
        for spec in specialists:
            emoji = spec.get("emoji", "🤖")
            name = spec.get("agent", "Agent")
            domain = spec.get("domain", "")
            tool_calls = spec.get("tool_calls", [])
            error = spec.get("error")

            st.markdown(f"**{emoji} {name}** ({domain})")

            if error:
                st.error(f"Error: {error}")

            if tool_calls:
                for t in tool_calls:
                    st.markdown(f"  Tool: `{t['tool']}`")
                    st.code(json.dumps(t["input"], indent=2), language="json")
                    result_preview = t["result"][:300] + "..." if len(t["result"]) > 300 else t["result"]
                    st.caption(f"Result: {result_preview}")
            else:
                st.caption("No tools used — answered from training knowledge")

            st.markdown("---")


# --- Main Area ---
st.image("mtm-logo.png", width=280)
st.markdown(
    """
    <div style="margin-top: -8px; margin-bottom: 24px;">
        <h1 style="color: #1c487b; font-size: 28px; margin: 0;">Nonprofit Technology Advisory Team</h1>
        <p style="color: #85abbd; font-size: 14px; margin: 4px 0 0 0;">
            Multi-agent guidance powered by Claude &mdash;
            Week 3, Lonely Octopus AI Agent Bootcamp
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

if not st.session_state.advising_started:
    # Resume session option
    st.markdown(
        """
        <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px;
                    padding: 16px; margin-bottom: 24px;">
            <p style="font-weight: 600; color: #0e7490; margin: 0 0 4px 0;">
                Returning? Resume a previous session
            </p>
            <p style="color: #64748b; font-size: 13px; margin: 0;">
                Upload a saved session file (.md) to pick up where you left off.
                Your organization profile and conversation history will be restored.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload a saved session file",
        type=["md"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        try:
            markdown_text = uploaded_file.read().decode("utf-8")
            restored_profile, restored_messages = parse_session(markdown_text)

            if restored_profile.get("org_name"):
                st.session_state.org_profile = restored_profile
                st.session_state.messages = restored_messages
                st.session_state.advising_started = True
                st.session_state.agent_logs = {}
                st.session_state["_just_resumed"] = True
                st.rerun()
            else:
                st.error("Could not find an organization profile in this file. Please check the file format.")
        except Exception:
            st.error("Could not parse this file. Please upload a valid saved session (.md) file.")

    st.markdown("")

    tab_users, tab_bootcamp = st.tabs(["For Nonprofit Staff", "For Bootcamp Reviewers"])

    with tab_users:
        st.markdown(
            """
            ### Your AI Technology Advisory Team

            Get **free, tailored technology guidance** for your nonprofit — powered by
            a team of specialized AI advisors from Meet the Moment.

            **How it works:**
            1. Fill in your organization's profile in the sidebar
            2. Click **Start Advising** to meet your advisory team
            3. Ask any technology question — our team of specialists will collaborate to answer
            4. Get recommendations calibrated to your budget, team size, and capacity

            **What makes this different from a single AI chatbot:**
            - A **triage agent** routes your question to the right specialist(s)
            - **Three specialist agents** cover security, technology, and AI readiness
            - A **synthesis agent** combines their expertise into one clear answer
            - Every answer shows which agents contributed and what sources they used

            **This is an AI advisory team, not humans.** The advice is a helpful starting
            point — always validate with your team before making major changes.

            ---

            ### Privacy & Data

            **Safe to enter:** Organization name, budget range, staff count, general pain points.

            **Do NOT enter:** Passwords, PII, donor lists, financial details, health data.

            **Nothing is saved.** Sessions are erased when you close the page. Download your
            advice as a Word doc before leaving.
            """
        )

    with tab_bootcamp:
        st.markdown(
            """
            ### Week 3 Assignment — Multi-Agent System (Hierarchical Pattern)

            This builds on the Week 2 single-agent advisor by evolving it into a
            **multi-agent team** using the **Hierarchical design pattern**.

            **Architecture:**

            ```
            User Question
                 ↓
            ┌─────────────┐
            │ Triage Agent │  ← Classifies & routes (keyword + LLM)
            └──┬─────┬────┘
               ↓     ↓
            ┌──────┐ ┌──────┐
            │Spec 1│ │Spec 2│  ← Up to 2 specialists per question
            └──┬───┘ └──┬───┘
               ↓        ↓
            ┌─────────────────┐
            │ Synthesis Agent  │  ← Combines into unified response
            └─────────────────┘
            ```

            **Requirements Checklist:**

            | Requirement | Implementation |
            |-------------|---------------|
            | Design pattern | Hierarchical (Triage → Specialists → Synthesis) |
            | 3+ specialized agents | Security, Technology, AI Readiness + Triage + Synthesis = 5 |
            | Shared memory | `SharedMemory` class with cross-agent context + persistent JSON |
            | Error handling | Keyword fallback if LLM triage fails, tool iteration limits, graceful API errors |
            | Architecture docs | This tab + README.md + inline docstrings |
            | Demo | Interactive — fill profile, ask questions, see agent pipeline |

            **Key demo moments:**
            1. Ask about "CRM" → routes to Technology specialist
            2. Ask about "MFA" → routes to Security specialist
            3. Ask about "should we use ChatGPT" → routes to AI Readiness specialist
            4. Ask about "migrating to cloud securely" → routes to Technology + Security
            5. Expand any response to see the full agent pipeline and tool calls

            **Evolution from Week 2:**

            | Week 2 | Week 3 |
            |--------|--------|
            | Single agent (1 Claude call) | Triage + specialists + synthesis (3-4 calls) |
            | One knowledge base (33 entries) | Split by domain (security, technology, AI) |
            | One system prompt | Per-agent specialized prompts |
            | Tool transparency (1 agent) | Multi-agent pipeline transparency |

            **Stack:** Python, Anthropic SDK (Sonnet + Haiku), Streamlit
            """
        )

    st.markdown("")
    st.markdown("**Get started** by filling in your organization profile in the sidebar and clicking **Start Advising**.")

else:
    profile = st.session_state.org_profile
    org_name = profile["org_name"]

    # Display chat history
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Show agent transparency for assistant messages
            if msg["role"] == "assistant" and i in st.session_state.agent_logs:
                _render_agent_transparency(st.session_state.agent_logs[i])

    # Auto-generate greeting on first load
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            with st.spinner("Assembling your advisory team..."):
                result = generate_greeting(profile)
                st.markdown(result["response"])

        st.session_state.messages.append({"role": "assistant", "content": result["response"]})
    elif st.session_state.get("_just_resumed"):
        # Show a resume notice once
        del st.session_state["_just_resumed"]
        st.info(
            f"Session resumed for **{org_name}** with "
            f"{len(st.session_state.messages)} previous messages. "
            f"Continue the conversation below."
        )

    # Chat input
    if user_input := st.chat_input("Ask about technology for your nonprofit..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            # Step 1: Conversation agent decides — clarify, answer directly, or route
            with st.spinner("Thinking..."):
                conv_result = evaluate_conversation(st.session_state.messages, profile)

            action = conv_result["action"]

            if action == "clarify":
                # Ask a clarifying question — fast, no specialist calls
                response_text = conv_result["question"]
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "is_clarifying": True,
                })
                st.rerun()

            elif action == "answer":
                # Direct answer for simple questions — no specialists needed
                response_text = conv_result["response"]
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                })
                # Memory extraction (best-effort)
                extract_memory(org_name, user_input, response_text)
                st.rerun()

            else:
                # Route to specialist pipeline with enriched context
                refined_q = conv_result.get("refined_question", user_input)
                st.info("Consulting the advisory team — this may take 2-3 minutes for a complete analysis.", icon="🔄")
                with st.spinner("Specialists are analyzing your question..."):
                    result = run_advisory_team(refined_q, profile)
                    st.markdown(result["response"])

                    # Build and store agent log
                    agent_log = {
                        "routing": result["routing"],
                        "specialists": result["specialists"],
                        "conversation_summary": conv_result.get("summary", ""),
                    }

                    _render_agent_transparency(agent_log)

                # Store
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["response"],
                })
                msg_idx = len(st.session_state.messages) - 1
                st.session_state.agent_logs[msg_idx] = agent_log

                # Memory extraction (best-effort)
                extract_memory(org_name, user_input, result["response"])

# --- Footer ---
st.markdown(
    """
    <div class="mtm-footer">
        <a href="https://mtm.now" target="_blank">Meet the Moment</a> &mdash;
        Helping nonprofits harness technology to amplify their impact.
        <br>Built by Joshua Peskay | AI Agent Bootcamp, Mar 2026
    </div>
    """,
    unsafe_allow_html=True,
)
