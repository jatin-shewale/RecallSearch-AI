# Design Document — RecallSearch AI

## 1. Product goal

Build a fast, accurate chat agent with one external tool — web search — and durable
memory of what the user asked and when. The core challenge is balancing latency,
grounding, and continuity without turning the agent into a large tool-using system.

## 2. Non-negotiable constraint: one tool

The agent has exactly one callable external tool: `web_search(query)`.

The following are application capabilities, not agent tools:
- SQLite persistence for messages and timestamps.
- Retrieval of recent or lexically relevant conversation records.
- UI rendering and session management.

No browser automation, code execution, email, file search, or other agent tools are
registered or exposed.

## 3. Architecture

1. **UI:** Streamlit collects a user message and displays the conversation.
2. **Memory retrieval:** The backend loads a bounded recent history and searches
   the current session's stored messages for keyword overlap.
3. **Search routing:** A small, low-temperature LLM call returns a strict JSON
   decision: search or do not search, plus a concise query.
4. **Tool execution:** If needed, Tavily performs one web search request.
5. **Synthesis:** The main LLM receives the question, bounded history, relevant
   memory, and search snippets. It writes a concise answer with exact source URLs.
6. **Persistence:** User and assistant messages are stored with UTC ISO-8601
   timestamps in SQLite.

## 4. Memory model

Each message stores:
- `session_id`
- `role` (`user` or `assistant`)
- `content`
- `created_at` (UTC ISO-8601)

Two retrieval paths are used:
- Recent chronological history for conversational continuity.
- Lightweight keyword matching for targeted recall.

This deliberately avoids a vector database and embedding model. For a small
challenge agent, lexical retrieval is inexpensive, transparent, and fast. A future
iteration could add SQLite FTS5 while keeping memory internal to the application.

## 5. Search strategy

Search is useful for:
- Current releases, prices, events, and changing facts.
- Recent news and current public information.
- Specific claims that need verification.
- Niche topics where model knowledge may be incomplete.

Search is usually unnecessary for:
- Greetings.
- Creative writing.
- Reformatting or summarizing user-provided text.
- Stable, common knowledge.

The router is asked for JSON only. If parsing fails, the system conservatively
searches rather than silently presenting uncertain current facts as verified.

## 6. Speed choices

- Use a fast hosted inference endpoint.
- Keep the routing response short.
- Limit recent history to a configurable number of turns.
- Limit retrieved memory records.
- Limit search results to five by default.
- Use basic search depth for lower latency.
- Bound HTTP timeout and generated answer length.

The two-call LLM flow (routing + synthesis) adds overhead. For production optimization,
routing can be replaced with deterministic heuristics or combined with a single
model call, but the current design makes the search decision explicit and inspectable.

## 7. Accuracy and trust

- Search snippets are treated as evidence, not unquestionable truth.
- The model must cite exact URLs from returned results.
- It must not invent sources or claim a search occurred when it did not.
- Conflicting or weak evidence should be disclosed.
- Memory is treated as prior user-provided context, not verified external truth.
- UTC timestamps are preserved to avoid silently assuming the user's timezone.

## 8. Failure handling

- Missing API keys produce actionable configuration errors.
- Search failures are passed into answer synthesis so the agent can disclose that
  verification was unavailable.
- Search HTTP requests have a timeout.
- User messages are saved before model calls, preserving the question timestamp
  even if a provider call fails.

## 9. Privacy and security

- API keys are loaded from environment variables and `.env` is ignored by Git.
- The database is local by default.
- No message content is sent to Tavily; only the search query is sent.
- Conversation text is sent to the configured LLM provider for generation.
- A production deployment should add authentication, retention controls, encryption
  at rest, rate limiting, and explicit user data deletion.

## 10. Known limitations

- Memory is scoped to a session ID stored in Streamlit session state. A fresh browser
  session starts a new conversation.
- Keyword retrieval can miss semantic matches.
- Search result snippets may omit context or contain outdated information.
- There is no streaming token output in this starter implementation.
- The search router can occasionally make a poor search/no-search decision.

## 11. Evaluation plan

Measure:
- **Answer correctness:** Human-rated factual correctness on a fixed question set.
- **Citation precision:** Fraction of factual claims supported by linked sources.
- **Search decision quality:** Whether search was used when freshness/verification
  required it, and avoided when unnecessary.
- **Memory recall:** Correct retrieval of earlier questions and their timestamps.
- **Latency:** Median and p95 time from submit to completed answer.

Suggested test cases:
1. Current fact requiring search.
2. Stable fact not requiring search.
3. Follow-up pronoun ("What about its alternatives?").
4. Exact recall ("What did I ask at the beginning, and when?").
5. Search provider timeout.
6. Missing API key.
7. Conflicting search snippets.

## 12. Next improvements

- Add automated unit tests for memory, routing and search formatting.
- Add SQLite FTS5 for stronger retrieval without another external service.
- Add streaming synthesis.
- Add export and delete-conversation controls.
- Add provider-independent model configuration.
