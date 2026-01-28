"""Simple Streamlit UI for chatting with the LearnPulse AI Instructor Assistant."""
import streamlit as st
import requests
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
import io
import sys

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="LearnPulse AI Instructor Assistant", page_icon="🎓", layout="wide")

API_BASE = "http://127.0.0.1:8000"  # FastAPI backend
st.title("🎓 LearnPulse AI Instructor Assistant (Prototype)")
st.caption("Ask questions about students or classes and get instant feedback.")

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def render_message_with_charts(response_text):
    """Render message with charts appearing inline where they're referenced."""
    # Split by <execute_python> tags to get text segments and code blocks
    pattern = r'<execute_python>(.*?)</execute_python>'
    
    # Find all code blocks and their positions
    parts = re.split(pattern, response_text, flags=re.DOTALL)
    
    # parts will be: [text_before, code1, text_between, code2, text_after, ...]
    # Even indices are text, odd indices are code
    
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # This is text content
            if part.strip():
                st.markdown(part)
        else:
            # This is code to execute
            try:
                code_clean = part.strip().replace('plt.show()', '')
                
                # Clear any existing figures
                plt.clf()
                plt.close('all')
                
                # Create execution namespace
                exec_namespace = {
                    'plt': plt,
                    'pd': pd,
                    'np': np,
                    'pandas': pd,
                    'numpy': np,
                    'matplotlib': plt.matplotlib
                }
                
                # Execute the code
                exec(code_clean, exec_namespace)
                
                # Get and display the figure immediately
                fig = plt.gcf()
                
                if fig.get_axes():
                    st.pyplot(fig)
                    plt.close(fig)
                else:
                    st.warning("⚠️ Code executed but no chart was created")
                
            except SyntaxError as e:
                st.error(f"❌ **Syntax Error in generated code:** {str(e)}")
                st.info("💡 **Tip:** Try rephrasing your request. The AI may have generated invalid Python syntax.")
                with st.expander("📄 Show code that failed"):
                    # Clean up quotes to display properly
                    display_code = part.strip()
                    st.code(display_code, language='python')
                    st.caption(f"Error details: Line {e.lineno if hasattr(e, 'lineno') else '?'}, {e.msg if hasattr(e, 'msg') else str(e)}")
            except Exception as e:
                st.error(f"❌ Error executing chart: {str(e)}")
                st.info("💡 Try asking the question differently or request a simpler chart.")
                with st.expander("📄 Show code that failed"):
                    st.code(part, language='python')

# ---------------------------
# SIDEBAR (for dataset preview)
# ---------------------------
with st.sidebar:
    st.header("📂 Mock Data Viewer")
    try:
        df = pd.read_csv("mock_data/mock_game_logs.csv")
        st.dataframe(df.head(10))
    except FileNotFoundError:
        st.warning("Mock dataset not found. Please generate mock_game_logs.csv first.")

    st.markdown("---")
    
    # Report & Feedback Tools
    st.markdown("### 📄 Reports & Feedback")
    
    # Student Feedback
    st.markdown("**📝 Student Feedback**")
    student_name_feedback = st.text_input("Student name for feedback:", key="feedback_student")
    if st.button("Generate Feedback", key="btn_feedback"):
        if student_name_feedback:
            try:
                feedback_res = requests.get(f"{API_BASE}/feedback/student/{student_name_feedback}", timeout=30)
                if feedback_res.ok:
                    feedback_data = feedback_res.json()
                    st.success(f"**Feedback for {student_name_feedback}:**")
                    st.markdown(feedback_data.get("feedback", "No feedback available"))
                else:
                    st.error(f"Error: {feedback_res.json().get('error', 'Unknown error')}")
            except Exception as e:
                st.error(f"Failed to fetch feedback: {e}")
    
    st.markdown("---")
    
    # Student Reports
    st.markdown("**📊 Student Reports**")
    student_name_report = st.text_input("Student name for report:", key="report_student")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View HTML Report", key="btn_html_student"):
            if student_name_report:
                st.markdown(f"[🔗 Open Student Report (HTML)]({API_BASE}/report/student/{student_name_report}/html)")
    with col2:
        if st.button("Download PDF Report", key="btn_pdf_student"):
            if student_name_report:
                st.markdown(f"[📥 Download Student Report (PDF)]({API_BASE}/report/student/{student_name_report}/pdf)")
    
    st.markdown("---")
    
    # Class Reports
    st.markdown("**📚 Class Reports**")
    class_id_report = st.text_input("Class ID for report:", key="report_class")
    col3, col4 = st.columns(2)
    with col3:
        if st.button("View HTML Report", key="btn_html_class"):
            if class_id_report:
                st.markdown(f"[🔗 Open Class Report (HTML)]({API_BASE}/report/class/{class_id_report}/html)")
    with col4:
        if st.button("Download PDF Report", key="btn_pdf_class"):
            if class_id_report:
                st.markdown(f"[📥 Download Class Report (PDF)]({API_BASE}/report/class/{class_id_report}/pdf)")
    
    st.markdown("---")
    st.markdown("🧠 **Available Endpoints:**")
    st.markdown("- `/student/{name}` → individual summary")
    st.markdown("- `/class/{class_id}` → class overview")
    st.markdown("- `/feedback/student/{name}` → personalized feedback")
    st.markdown("- `/report/student/{name}/html` → HTML report")
    st.markdown("- `/report/student/{name}/pdf` → PDF download")
    st.markdown("- `/report/class/{id}/html` → class HTML report")
    st.markdown("- `/report/class/{id}/pdf` → class PDF download")

# ---------------------------
# MAIN CHAT INTERFACE
# ---------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "chat_session_id" not in st.session_state:
    st.session_state["chat_session_id"] = None
if "meta" not in st.session_state:
    try:
        meta_res = requests.get(f"{API_BASE}/meta", timeout=10)
        if meta_res.ok:
            st.session_state["meta"] = meta_res.json()
        else:
            st.session_state["meta"] = {"students": [], "class_ids": []}
    except Exception:
        st.session_state["meta"] = {"students": [], "class_ids": []}

st.subheader("💬 Chat with your AI Assistant")

# Chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            # Render message with inline charts
            if '<execute_python>' in msg["content"]:
                render_message_with_charts(msg["content"])
            else:
                st.markdown(msg["content"])

# User input
prompt = st.chat_input("Ask something about your students...")

import time

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing... ✨"):
            time.sleep(0.5)  # small pause for UX

            # Detect intent hints to send lightweight context to backend
            lower = prompt.lower()
            name = None
            student_list = [s.lower() for s in st.session_state.get("meta", {}).get("students", [])]
            for possible in student_list:
                if possible and possible in lower:
                    name = possible
                    break
            class_hint = None
            class_list = [str(c).lower() for c in st.session_state.get("meta", {}).get("class_ids", [])]
            for cid in class_list:
                if cid and cid in lower:
                    class_hint = cid
                    break

            # Call conversational endpoint with session memory (optionally include student/class)
            try:
                payload = {"message": prompt, "session_id": st.session_state["chat_session_id"]}
                if class_hint:
                    payload["class_id"] = class_hint
                elif name:
                    payload["student"] = name
                res = requests.post(f"{API_BASE}/chat", json=payload, timeout=90)
                data = res.json()
                if res.status_code == 200 and "reply" in data:
                    response = data["reply"]
                    if not st.session_state["chat_session_id"]:
                        st.session_state["chat_session_id"] = data.get("session_id")
                else:
                    response = data.get("error", f"Unexpected response: {data}")
            except Exception as e:
                response = f"⚠️ Error contacting backend: {e}"

            # Render response with inline charts
            if '<execute_python>' in response:
                render_message_with_charts(response)
            else:
                st.markdown(response)
            
            # Store response (with tags) so we can re-render charts on reload
            st.session_state.messages.append({"role": "assistant", "content": response})
