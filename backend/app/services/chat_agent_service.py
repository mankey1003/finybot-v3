import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Generator, Optional

from google import genai
from google.genai import types

from app.config import GEMINI_MODEL, GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION
from app.services import firestore_service

logger = logging.getLogger(__name__)

_client = genai.Client(
    vertexai=True,
    project=GOOGLE_CLOUD_PROJECT,
    location=VERTEX_AI_LOCATION,
)

SYSTEM_PROMPT = """You are FinyBot, a helpful financial assistant for credit card expense tracking.
You help users understand their spending by querying their transaction data.

Rules:
- ALWAYS use the provided tools to fetch real data. Never make up numbers.
- Format all monetary amounts in INR (₹).
- When showing multiple transactions, use markdown tables or lists for clarity.
- If the user asks about their cards and you're unsure which providers they have, call list_card_providers first.
- Support multi-step reasoning: e.g., to compare months, fetch data for each month then compare.
- Keep responses concise and actionable.
- When the user asks about "last month" or "this month", infer the billing month in YYYY-MM format based on common sense.
- If a query returns no results, suggest the user check their filters or try a different time period.
"""

# ── Tool Declarations ──────────────────────────────────────────────────────────

AGENT_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="search_transactions",
            description="Search and filter the user's credit card transactions. Returns matching transactions with date, description, amount, category, and card provider.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "billing_month": types.Schema(type="STRING", description="Filter by billing month in YYYY-MM format. If not specified, searches recent months."),
                    "billing_months": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Filter by multiple billing months (YYYY-MM). Use this for cross-month searches."),
                    "category": types.Schema(type="STRING", description="Filter by category: Food, Travel, Shopping, Entertainment, Utilities, Healthcare, Fuel, EMI, Other"),
                    "card_provider": types.Schema(type="STRING", description="Filter by card provider name"),
                    "min_amount": types.Schema(type="NUMBER", description="Minimum transaction amount"),
                    "max_amount": types.Schema(type="NUMBER", description="Maximum transaction amount"),
                    "description_keyword": types.Schema(type="STRING", description="Search keyword in transaction description (case-insensitive)"),
                    "debit_or_credit": types.Schema(type="STRING", description="Filter by 'debit' or 'credit'"),
                    "limit": types.Schema(type="INTEGER", description="Maximum number of results to return (default 20)"),
                    "start_date": types.Schema(type="STRING", description="Start date filter in YYYY-MM-DD format"),
                    "end_date": types.Schema(type="STRING", description="End date filter in YYYY-MM-DD format"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_spending_summary",
            description="Get aggregated spending summary grouped by category or card provider for specified billing months. Shows totals and breakdowns.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "billing_months": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Billing months to aggregate (YYYY-MM format). Required."),
                    "group_by": types.Schema(type="STRING", description="Group results by 'category' or 'card'. Defaults to 'category'."),
                },
                required=["billing_months"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_statements",
            description="Get credit card statement summaries including total amount due, minimum payment, due dates, and billing periods.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "billing_months": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Filter by billing months (YYYY-MM format). If empty, returns all statements."),
                    "card_provider": types.Schema(type="STRING", description="Filter by card provider name"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="list_card_providers",
            description="List all credit card providers configured by the user, including card names.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
    ])
]


# ── Tool Execution ─────────────────────────────────────────────────────────────

def _serialize_value(v):
    """Convert Firestore timestamps and other non-JSON types to strings."""
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _serialize_doc(doc: dict) -> dict:
    return {k: _serialize_value(v) for k, v in doc.items()}


def _execute_search_transactions(uid: str, args: dict) -> str:
    billing_months = args.get("billing_months", [])
    if not billing_months and args.get("billing_month"):
        billing_months = [args["billing_month"]]
    if not billing_months:
        # Default to last 3 months
        now = datetime.now(timezone.utc)
        billing_months = []
        for i in range(3):
            month = now.month - i
            year = now.year
            if month <= 0:
                month += 12
                year -= 1
            billing_months.append(f"{year:04d}-{month:02d}")

    transactions = firestore_service.get_transactions_for_months(uid, billing_months)

    # Apply in-memory filters
    if args.get("category"):
        cat = args["category"].lower()
        transactions = [t for t in transactions if t.get("category", "").lower() == cat]

    if args.get("card_provider"):
        cp = args["card_provider"].lower()
        transactions = [t for t in transactions if cp in t.get("cardProvider", "").lower()]

    if args.get("min_amount") is not None:
        transactions = [t for t in transactions if t.get("amount", 0) >= args["min_amount"]]

    if args.get("max_amount") is not None:
        transactions = [t for t in transactions if t.get("amount", 0) <= args["max_amount"]]

    if args.get("description_keyword"):
        kw = args["description_keyword"].lower()
        transactions = [t for t in transactions if kw in t.get("description", "").lower()]

    if args.get("debit_or_credit"):
        dc = args["debit_or_credit"].lower()
        transactions = [t for t in transactions if t.get("debitOrCredit", "").lower() == dc]

    if args.get("start_date"):
        start = args["start_date"]
        transactions = [t for t in transactions if _date_str(t.get("date", "")) >= start]

    if args.get("end_date"):
        end = args["end_date"]
        transactions = [t for t in transactions if _date_str(t.get("date", "")) <= end]

    # Sort by date descending
    transactions.sort(key=lambda t: t.get("date", ""), reverse=True)

    limit = args.get("limit", 20)
    transactions = transactions[:limit]

    serialized = [_serialize_doc(t) for t in transactions]
    return json.dumps({"count": len(serialized), "transactions": serialized})


def _date_str(val) -> str:
    """Convert a datetime or string to YYYY-MM-DD string for comparison."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10] if val else ""


def _execute_get_spending_summary(uid: str, args: dict) -> str:
    billing_months = args.get("billing_months", [])
    group_by = args.get("group_by", "category")

    transactions = firestore_service.get_transactions_for_months(uid, billing_months)

    spend_data = {}
    for month in billing_months:
        month_txs = [t for t in transactions if t.get("billingMonth") == month]
        by_category: dict[str, float] = defaultdict(float)
        by_card: dict[str, float] = defaultdict(float)
        total = 0.0

        for tx in month_txs:
            if tx.get("debitOrCredit") == "debit":
                amount = tx.get("amount", 0.0)
                total += amount
                by_category[tx.get("category", "Other")] += amount
                by_card[tx.get("cardProvider", "unknown")] += amount

        spend_data[month] = {
            "total": round(total, 2),
            "by_card": {k: round(v, 2) for k, v in by_card.items()},
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
            "transaction_count": len(month_txs),
        }

    return json.dumps(spend_data)


def _execute_get_statements(uid: str, args: dict) -> str:
    statements = firestore_service.get_statements(uid)

    billing_months = args.get("billing_months", [])
    if billing_months:
        statements = [s for s in statements if s.get("billingMonth") in billing_months]

    card_provider = args.get("card_provider")
    if card_provider:
        cp = card_provider.lower()
        statements = [s for s in statements if cp in s.get("cardProvider", "").lower()]

    serialized = [_serialize_doc(s) for s in statements]
    return json.dumps({"count": len(serialized), "statements": serialized})


def _execute_list_card_providers(uid: str, args: dict) -> str:
    providers = firestore_service.get_card_providers(uid)
    # Strip sensitive fields
    safe = []
    for p in providers:
        safe.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "emailSenderPattern": p.get("emailSenderPattern"),
            "subjectKeyword": p.get("subjectKeyword"),
        })
    return json.dumps({"count": len(safe), "providers": safe})


_TOOL_EXECUTORS = {
    "search_transactions": _execute_search_transactions,
    "get_spending_summary": _execute_get_spending_summary,
    "get_statements": _execute_get_statements,
    "list_card_providers": _execute_list_card_providers,
}


# ── Result Summarization ──────────────────────────────────────────────────────

def _summarize_result(tool_name: str, result_json: str) -> str:
    """Create a compact summary for frontend display."""
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return result_json[:200]

    if tool_name == "search_transactions":
        count = data.get("count", 0)
        txs = data.get("transactions", [])
        if count == 0:
            return "No transactions found"
        preview = []
        for t in txs[:3]:
            preview.append(f"₹{t.get('amount', 0):,.2f} - {t.get('description', 'N/A')}")
        summary = f"{count} transaction(s) found"
        if preview:
            summary += ": " + "; ".join(preview)
        if count > 3:
            summary += f" ... and {count - 3} more"
        return summary

    if tool_name == "get_spending_summary":
        months = list(data.keys())
        parts = []
        for m in months[:3]:
            total = data[m].get("total", 0)
            parts.append(f"{m}: ₹{total:,.2f}")
        return "Spending summary — " + ", ".join(parts)

    if tool_name == "get_statements":
        count = data.get("count", 0)
        return f"{count} statement(s) found"

    if tool_name == "list_card_providers":
        providers = data.get("providers", [])
        names = [p.get("name", "Unknown") for p in providers]
        return f"{len(names)} card(s): {', '.join(names)}" if names else "No cards configured"

    return f"Result: {len(result_json)} chars"


# ── History Reconstruction ─────────────────────────────────────────────────────

def _build_contents_from_history(history: list[dict]) -> list[types.Content]:
    """Convert stored message history into Gemini Content objects."""
    contents = []
    for msg in history:
        role = msg.get("role", "user")
        gemini_role = "user" if role == "user" else "model"

        if role == "user":
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=msg.get("content", ""))],
            ))
        elif role == "assistant":
            # Reconstruct function calls + responses if present
            tool_calls = msg.get("toolCalls") or []
            if tool_calls:
                for tc in tool_calls:
                    # Function call from model
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_function_call(
                            name=tc["name"],
                            args=tc.get("arguments", {}),
                        )],
                    ))
                    # Function response
                    if tc.get("result") is not None:
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(
                                name=tc["name"],
                                response={"result": tc["result"]},
                            )],
                        ))
            if msg.get("content"):
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg["content"])],
                ))
    return contents


# ── SSE Helpers ────────────────────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ── Agentic Loop ──────────────────────────────────────────────────────────────

def run_agent_stream(uid: str, user_message: str, history: list[dict]) -> Generator[str, None, None]:
    """
    Run the agentic loop and yield SSE events.
    Yields: chat_id, tool_call, tool_result, message, done, error events.
    """
    try:
        contents = _build_contents_from_history(history)
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)],
        ))

        collected_tool_calls = []

        for iteration in range(10):
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=AGENT_TOOLS,
                    temperature=0.3,
                ),
            )

            candidate = response.candidates[0]
            has_function_call = False

            for part in candidate.content.parts:
                if part.function_call:
                    has_function_call = True
                    fc = part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    yield _sse_event("tool_call", {
                        "name": tool_name,
                        "arguments": tool_args,
                    })

                    # Execute tool
                    executor = _TOOL_EXECUTORS.get(tool_name)
                    if executor:
                        try:
                            result = executor(uid, tool_args)
                        except Exception as e:
                            logger.error("tool_execution_failed", extra={"tool": tool_name, "error": str(e)})
                            result = json.dumps({"error": str(e)})
                    else:
                        result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    summary = _summarize_result(tool_name, result)
                    yield _sse_event("tool_result", {
                        "name": tool_name,
                        "result": summary,
                    })

                    collected_tool_calls.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": summary,
                    })

                    # Add function call + response to contents for next iteration
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_function_call(name=tool_name, args=tool_args)],
                    ))
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=tool_name,
                            response={"result": result},
                        )],
                    ))

            if not has_function_call:
                # Text response — final answer
                text = candidate.content.parts[0].text if candidate.content.parts else ""
                yield _sse_event("message", {"content": text, "tool_calls": collected_tool_calls})
                yield _sse_event("done", {})
                return

        # Max iterations reached
        yield _sse_event("message", {"content": "I've reached the maximum number of tool calls. Here's what I found so far.", "tool_calls": collected_tool_calls})
        yield _sse_event("done", {})

    except Exception as e:
        logger.error("agent_stream_error", extra={"error": str(e)}, exc_info=True)
        yield _sse_event("error", {"message": str(e)})


# ── Title Generation ───────────────────────────────────────────────────────────

def generate_chat_title(user_message: str) -> str:
    """Generate a short 4-6 word title for a chat based on the first message."""
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f'Generate a concise 4-6 word title for a chat that starts with this message. Return ONLY the title, no quotes or punctuation at the end.\n\nMessage: "{user_message}"',
        )
        title = response.text.strip().strip('"').strip("'")
        return title[:60]
    except Exception as e:
        logger.error("title_generation_failed", extra={"error": str(e)})
        return user_message[:50]
