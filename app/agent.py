import os
import re
import json
import logging
from typing import Any
from google.adk import Workflow
from google.adk.agents import Agent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events import Event, RequestInput
from google.adk.models import Gemini
from google.adk.tools import AgentTool, MCPToolset
from google.adk.workflow import START, node
from google.genai import types
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

from app.config import config

# =====================================================================
# MCP Server Toolset Connection
# =====================================================================

mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "-m", "app.mcp_server"],
        )
    )
)

# =====================================================================
# Specialized Sub-Agents with MCP Tools
# =====================================================================

market_analyst_agent = Agent(
    name="market_analyst_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are a Market Analyst. Analyze technical metrics (price actions, "
        "trends, support/resistance levels, volumes) for the stock ticker requested. "
        "Use the get_stock_price tool to fetch technical data, and get_market_sentiment "
        "to get current market context. Provide a technical assessment of whether the trend "
        "is bullish, bearish, or neutral."
    ),
    tools=[mcp_toolset],
)

fundamental_analyst_agent = Agent(
    name="fundamental_analyst_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are a Fundamental Analyst. Analyze fundamental metrics (P/E ratio, "
        "revenue growth, debt levels, earnings) of the company requested. "
        "Use the get_company_fundamentals tool to fetch fundamentals, and get_market_sentiment "
        "to assess general risks. Provide a fundamental health check and risk assessment."
    ),
    tools=[mcp_toolset],
)

# Wrap sub-agents in AgentTools for orchestrator delegation
market_analyst_tool = AgentTool(agent=market_analyst_agent)
fundamental_analyst_tool = AgentTool(agent=fundamental_analyst_agent)

# =====================================================================
# Orchestrator Agent
# =====================================================================

orchestrator_agent = Agent(
    name="orchestrator_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the Stock Research Orchestrator. Coordinate comprehensive "
        "financial research on the user's requested stock. "
        "You have two specialized tools: market_analyst_agent and fundamental_analyst_agent. "
        "First, run both tools to gather technical and fundamental reports. "
        "Then, synthesize them into a single report. "
        "If you propose a BUY or SELL trade, state the action clearly. "
        "If you do not propose a trade (e.g., recommend HOLD or just provide info), state that clearly."
    ),
    tools=[market_analyst_tool, fundamental_analyst_tool],
)

# =====================================================================
# Workflow Nodes (with Security Controls)
# =====================================================================

@node
async def security_checkpoint(ctx: Context, node_input: Any):
    # Extract query text
    query = ""
    if isinstance(node_input, types.Content):
        query = "".join(p.text for p in node_input.parts if p.text)
    elif isinstance(node_input, str):
        query = node_input
    
    # 1. PII Scrubbing (CCN and SSN/TIN detection)
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    ccn_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    
    scrubbed = query
    pii_found = False
    
    if ssn_pattern.search(query):
        scrubbed = ssn_pattern.sub("[REDACTED_SSN]", scrubbed)
        pii_found = True
    if ccn_pattern.search(query):
        scrubbed = ccn_pattern.sub("[REDACTED_CCN]", scrubbed)
        pii_found = True
        
    if pii_found:
        audit_log = {
            "event": "pii_scrubbed",
            "severity": "WARNING",
            "action": "redacted_sensitive_data",
            "message": "Sensitive PII (SSN or CCN) detected and redacted."
        }
        print(json.dumps(audit_log), flush=True)

    # Store clean/scrubbed query in state
    ctx.state["query"] = scrubbed

    # 2. Prompt Injection Detection
    query_lower = scrubbed.lower()
    injection_triggers = [
        "ignore instruction", "override prompt", "system prompt",
        "ignore previous instruction", "you are now", "jailbreak", "dan mode"
    ]
    
    found_injection = [t for t in injection_triggers if t in query_lower]
    if found_injection:
        audit_log = {
            "event": "prompt_injection_blocked",
            "severity": "CRITICAL",
            "action": "block_request",
            "details": f"Injection keywords matched: {found_injection}"
        }
        print(json.dumps(audit_log), flush=True)
        return Event(
            output="Security check failed: Unauthorized system instructions detected.",
            route="invalid"
        )

    # 3. Domain-Specific Rule: Compliance & Insider Trading Prevention
    compliance_keywords = [
        "insider trading", "non-public info", "non-public information",
        "confidential tip", "insider information"
    ]
    found_compliance = [c for c in compliance_keywords if c in query_lower]
    if found_compliance:
        audit_log = {
            "event": "compliance_violation_blocked",
            "severity": "CRITICAL",
            "action": "block_request",
            "details": f"Compliance keywords matched: {found_compliance}"
        }
        print(json.dumps(audit_log), flush=True)
        return Event(
            output="Security check failed: Request violates compliance guidelines regarding non-public information.",
            route="invalid"
        )

    # Clean query audit log
    audit_log = {
        "event": "security_check_passed",
        "severity": "INFO",
        "action": "forward_request",
        "message": "Query passed all security checks."
    }
    print(json.dumps(audit_log), flush=True)
    return Event(output=scrubbed, route="valid")

@node
async def security_event(ctx: Context, node_input: Any):
    return Event(output=f"Access Denied: Security Checkpoint Blocked Input. Details: {node_input}")

@node(rerun_on_resume=True)
async def orchestrator_node(ctx: Context, node_input: Any):
    # Run the orchestrator agent standalone
    agent_output = await ctx.run_node(orchestrator_agent, node_input=node_input)
    
    # Extract response text
    report_text = ""
    if hasattr(agent_output, "text") and agent_output.text:
        report_text = agent_output.text
    elif hasattr(agent_output, "parts") and agent_output.parts:
        report_text = "".join(p.text for p in agent_output.parts if p.text)
    else:
        report_text = str(agent_output)
        
    ctx.state["report"] = report_text
    
    # Route based on whether trade execution is proposed
    report_upper = report_text.upper()
    if "BUY" in report_upper or "SELL" in report_upper:
        return Event(output="Trade proposal requires user approval.", route="needs_approval")
    else:
        return Event(output=report_text, route="finalize")

@node
async def hitl_approval(ctx: Context, node_input: Any):
    interrupt_id = "trade_approval"
    
    # Check if user response was received via resume
    if interrupt_id in ctx.resume_inputs:
        user_response = ctx.resume_inputs[interrupt_id]
        ctx.state["approved"] = user_response
        
        is_approved = False
        if isinstance(user_response, bool):
            is_approved = user_response
        elif isinstance(user_response, dict):
            is_approved = user_response.get("approved", False)
        elif isinstance(user_response, str):
            is_approved = "yes" in user_response.lower() or "true" in user_response.lower()
            
        if is_approved:
            yield Event(output="Trade execution APPROVED by user.", route="finalize")
        else:
            yield Event(output="Trade execution DENIED by user.", route="finalize")
        return
            
    # Yield RequestInput to pause and request input
    yield RequestInput(
        interrupt_id=interrupt_id,
        message=f"Review the trade proposal:\n\n{ctx.state.get('report')}\n\nDo you approve this trade? (Yes/No)",
        response_schema={"type": "boolean"}
    )

@node
async def finalize_report(ctx: Context, node_input: Any):
    query = ctx.state.get("query", "Unknown stock")
    report = ctx.state.get("report", "No report generated.")
    approved = ctx.state.get("approved", "No trade proposal generated or required approval.")
    
    summary = (
        f"### Stock Analysis Summary\n\n"
        f"**Stock Query:** {query}\n"
        f"**Approval Status:** {approved}\n\n"
        f"**Analysis details:**\n{report}"
    )
    return Event(output=summary)

# =====================================================================
# Workflow Compilation
# =====================================================================

workflow_edges = [
    (START, security_checkpoint),
    (security_checkpoint, {
        "valid": orchestrator_node,
        "invalid": security_event
    }),
    (orchestrator_node, {
        "needs_approval": hitl_approval,
        "finalize": finalize_report
    }),
    (hitl_approval, finalize_report)
]

root_agent = Workflow(
    name="stock_analyst_workflow",
    edges=workflow_edges,
)

app = App(
    root_agent=root_agent,
    name="app",
)
