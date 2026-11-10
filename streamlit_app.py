import uuid
import streamlit as st
from app.db import init_db, get_recent_messages, list_sessions
from app.agent import answer

st.set_page_config(page_title="RecallSearch AI", page_icon="🔎", layout="wide")
init_db()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RecallSearch")
    st.caption("One tool. Persistent memory. Source-grounded answers.")
    if st.button("＋ New conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.subheader("Memory")
    rows = get_recent_messages(st.session_state.session_id, 20)
    if not rows:
        st.caption("Your questions and timestamps will appear here.")
    for item in rows[-10:]:
        label = "You" if item["role"] == "user" else "RecallSearch"
        st.caption(f"{label} · {item['created_at']}")
        st.write(item["content"][:140] + ("…" if len(item["content"]) > 140 else ""))
    st.divider()
    st.caption("Only external agent tool: Tavily web search")

st.title("🔎 RecallSearch AI")
st.write("Ask anything. I can search the web and remember what you asked — including when you asked it.")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask a question…")
if prompt:
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = answer(st.session_state.session_id, prompt)
                st.markdown(result["answer"])
                if result["searched"]:
                    st.caption("🌐 Web search used")
                else:
                    st.caption("Answered from model knowledge and conversation context")
                if result["sources"]:
                    with st.expander(f"Sources ({len(result['sources'])})"):
                        for source in result["sources"]:
                            st.markdown(f"- [{source['title']}]({source['url']})")
                st.session_state.messages.append({"role":"assistant","content":result["answer"]})
            except Exception as exc:
                st.error(str(exc))
