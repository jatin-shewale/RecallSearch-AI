import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL, MAX_HISTORY_TURNS
from app.db import get_recent_messages, search_memory, save_message
from app.search import web_search, SearchError

SYSTEM_PROMPT = """You are RecallSearch, a fast, accurate research chat assistant.
You have exactly one external tool available: web search. The application may provide
conversation memory as context; memory is not a tool and must not be described as one.

Rules:
- Answer directly and concisely. Prioritize correctness over confident-sounding guesses.
- Use web search for current, changing, niche, or verification-dependent facts.
- Do not search for stable facts unless useful. If uncertain, search.
- Prefer primary and official sources when available; use secondary sources only when primary sources do not answer the question.
- Ground claims based on search results. Cite sources as Markdown links using the exact URLs supplied.
- For "latest" version questions, identify the newest stable release and distinguish it from preview or prerelease versions when relevant.
- Never invent sources, quotes, dates, or facts. If sources conflict or are weak, say so.
- Use conversation memory only when relevant. Distinguish remembered user statements from verified facts.
- If asked what the user asked before or when, use the timestamped memory context.
- Timestamps are UTC ISO-8601. Convert only if a timezone is explicitly known.
- If a request is ambiguous, ask one focused clarification.
"""

def _client():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")
    return Groq(api_key=GROQ_API_KEY)

def _needs_search(client, question, history, memory):
    prompt = f"""Decide whether this question needs fresh web search.
Return ONLY JSON: {{"search": true|false, "query": "short search query"}}
Search for current facts, recent events, niche claims, or when verification is needed.
Do not search for greetings, creative writing, simple transformations, or stable common knowledge.
Question: {question}
Recent conversation: {json.dumps(history[-4:], ensure_ascii=False)}
Relevant memory: {json.dumps(memory[:4], ensure_ascii=False)}
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL, temperature=0, max_completion_tokens=512,
        include_reasoning=False,
        **({"reasoning_effort": "low"} if GROQ_MODEL.startswith("openai/gpt-oss-") else {}),
        messages=[{"role":"system","content":"Return valid JSON only."},
                  {"role":"user","content":prompt}]
    )
    raw = response.choices[0].message.content.strip()
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        # Conservative fallback: search when routing output is malformed.
        return {"search": True, "query": question}

def answer(session_id: str, question: str):
    client = _client()
    history = get_recent_messages(session_id, MAX_HISTORY_TURNS * 2)
    memory = search_memory(session_id, question, limit=6)

    # Save the user turn immediately so its timestamp is durable even if a provider fails.
    user_timestamp = save_message(session_id, "user", question)

    route = _needs_search(client, question, history, memory)
    sources = []
    search_note = ""
    if route.get("search"):
        try:
            sources = web_search(route.get("query") or question)
        except SearchError as exc:
            search_note = f"Search could not be completed: {exc}"

    memory_text = "\n".join(
        f"- [{m['created_at']}] {m['role']}: {m['content'][:700]}" for m in memory
    ) or "No matching earlier messages found."

    source_text = "\n".join(
        f"[{i+1}] {s['title']}\nURL: {s['url']}\nSnippet: {s['content']}"
        for i, s in enumerate(sources)
    ) or "No web search results."

    messages = [{"role":"system","content":SYSTEM_PROMPT}]
    # Keep only a short recent window for speed and token control.
    for item in history[-MAX_HISTORY_TURNS*2:]:
        if item["role"] in ("user", "assistant"):
            messages.append({"role":item["role"],"content":item["content"][:3000]})

    user_prompt = f"""Current question: {question}

Relevant timestamped conversation memory:
{memory_text}

Web search results (use only if relevant; URLs must be cited exactly):
{source_text}

{search_note}

Answer the current question. Cite web-supported factual claims with Markdown links.
If no search was performed, do not pretend that you searched.
"""
    messages.append({"role":"user","content":user_prompt})
    completion = client.chat.completions.create(
        model=GROQ_MODEL, temperature=0.2, max_completion_tokens=2048,
        include_reasoning=False,
        **({"reasoning_effort": "low"} if GROQ_MODEL.startswith("openai/gpt-oss-") else {}),
        messages=messages
    )
    response = completion.choices[0].message.content
    if not response or not response.strip():
        finish_reason = completion.choices[0].finish_reason
        raise RuntimeError(
            "The model returned no answer text "
            f"(finish reason: {finish_reason or 'unknown'}). Try again or check GROQ_MODEL."
        )
    assistant_timestamp = save_message(session_id, "assistant", response)
    return {
        "answer": response,
        "sources": sources,
        "searched": bool(route.get("search")),
        "user_timestamp": user_timestamp,
        "assistant_timestamp": assistant_timestamp
    }
