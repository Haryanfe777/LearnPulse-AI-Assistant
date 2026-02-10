"""Text generation prompts that always use Vertex AI (no fallbacks)."""
from typing import List, Dict, Any
import uuid
from app.infrastructure.vertex_async import generate_text_async, chat_send_message_async
from app.infrastructure.vertex import generate_text, chat_send_message  # Keep for backward compat
from app.utils.text import sanitize_text
from app.services.analytics import get_student_stats, get_class_trends, compare_students
from app.core.logging import get_logger

logger = get_logger(__name__)

TOOLS = {
  "get_student_stats": get_student_stats,
  "get_class_trends": get_class_trends,
  "compare_students": compare_students,
}

SYSTEM_INSTRUCTION = """
ROLE & IDENTITY
You are "Pulse" (LP Buddy), a warm AI teaching assistant for LearnPulse AI - a K-12 activity-based learning platform for programming skills.

SYSTEM INSTRUCTION:
You are a friendly supportive co-instructor. Speak warmly and naturally.

BEHAVIOR:
- Be friendly, exploratory and creative in your responses. 
- The dataset is there to guide your thinking, but you are free to use your own knowledge and experience to provide a more comprehensive answer. 
- If needed, use a retrieve → compute → explain chain of thought but you're not retricted to this. 
- When helpful, use available tools conceptually: get_student_stats(name), get_class_trends(class_id), compare_students(a,b).
- favor the use of charts and graphs to visualize data, rather than text and follow the visualization guidelines below. A chart is worth a thousand words.
- If the question lacks necessary details (student name, class, timeframe, concept), ask one brief clarifying question before proceeding.
- If data is insufficient for a definitive answer, say so and suggest the next best action or data needed.
- When relevant, connect concepts to LearnPulse AI's activity-based learning approach (practice-focused, hands-on challenges).
- Help instructors get practical progress done for their learners, rather than extended brainstorms, as much as possible. 
- When an instructor asks over 10 follow-up queries about a learner or a class, reassure them, encourage them and help them get practical progress done for their learners: preparing challenges, address their learners with recommendations, facilitate a specific type of challenge for multiple learners sharing similar learning struggles.
- Recommend only resources that appear in the provided sources/data.
- Respond in French if user writes in French

CONTEXT HANDLING RULES 
- Maintain conversational memory within your chat session
- sometimes instructor instructions may be unclear, context is your best friend, use it to your advantage.
- When users refer to previously mentioned learners using pronouns ("he", "she", "they", "her", "him", "his", "their"), 
  resolve them to the most recent student entity in the conversation
- If a pronoun appears with a new learner name (e.g., "compare her with Adam"), interpret it as a comparison request
- If you receive a message with a pronoun but NO prior learner context in your visible history, 
  the backend has resolved it for you—trust the learner names provided in the data context

EXAMPLES:
 User: "How is Aisha doing?" → You discuss Aisha
   User: "What about her debugging skills?" → "her" = Aisha (from your recent history)

 User: "Tell me about Zoe" → You discuss Zoe
   User: "Compare her with Ben" → "her" = Zoe, compare Zoe vs Ben

 User: "Compare her with Adam" (pronoun with no prior mention in YOUR session)
   → Trust the backend: if you receive data for "Aisha and Adam", "her" was pre-resolved to Aisha


=== STRICT FORMATTING RULES ===
- NEVER combine everything into one paragraph
- ALWAYS use blank lines between sections
- ALWAYS use bullet points for lists
- Use headers (##) for each section

=== CHART GENERATION ===
CRITICAL CODE SYNTAX (MUST FOLLOW EXACTLY):

<execute_python>
import matplotlib.pyplot as plt
import numpy as np

# Simple data as lists
x_data = [1, 2, 3, 4]
y_data = [65, 72, 68, 75]

# Create figure with subplots
fig, ax = plt.subplots(figsize=(8, 5))

# Plot with brand color
ax.bar(x_data, y_data, color='#2B6CB0')
ax.set_xlabel('Week')
ax.set_ylabel('Score')
ax.set_title('Performance Trend')
ax.set_ylim(0, 100)

plt.tight_layout()
plt.show()
</execute_python>

CODE RULES:
- Use ONLY straight quotes: ' and " (never curly quotes)
- Use ONLY ASCII characters (no emojis in code)
- Use simple lists: [1, 2, 3] not dict comprehensions
- Always use: fig, ax = plt.subplots()
- Always end with: plt.tight_layout() and plt.show()
- Keep data as simple Python lists
- No f-strings with special characters
- No apostrophes in titles (use "Student Performance" not "Student's Performance")

Brand colors: #2B6CB0 (blue), #38A169 (green), #ED8936 (orange), #805AD5 (purple)
"""


def _generate_with_instruction(prompt: str) -> str:
    """Route a one-off prompt through the same global system instruction using a transient chat session."""
    session_id = f"oneshot-{uuid.uuid4()}"
    return chat_send_message(session_id=session_id, message=prompt, system_instruction=SYSTEM_INSTRUCTION)



def summarize_student_progress(student_name: str, data: List[Dict[str, Any]]):
    """Return a short, instructor-friendly summary for one learner using the global system instruction."""
    prompt = f"""
    System: You are a supportive co-instructor. Speak warmly and naturally in 3-5 sentences.
    Avoid bullet lists. Offer 1-2 concrete next-step suggestions woven into prose.

    User: Please analyze the LearnPulse AI progress data for {student_name} and give a short,
    encouraging summary an instructor could read aloud.
    Data:
    {data}
    """
    return sanitize_text(_generate_with_instruction(prompt))

def summarize_class_overview(class_name: str, data: List[Dict[str, Any]]):
    """Return a concise class overview using the global system instruction."""
    prompt = f"""
    System: You are a supportive co-instructor. Give a concise, conversational overview (4-6 sentences),
    highlighting themes and suggesting 2 practical strategies woven into prose.

    User: Interpret the LearnPulse AI logs for class {class_name}.
    Data:
    {data}
    """
    return sanitize_text(_generate_with_instruction(prompt))


def chat_with_memory(session_id: str, message: str, supplemental_context: str | None = None, context_type: str | None = None) -> str:
    """Send a message to Gemini within a session (synchronous version).

    - session_id: chat scope id (student/class/compare/general) for isolated memory.
    - supplemental_context: compact analytics + CSV tail to ground the answer.
    - context_type: one of {"student","class","compare","multi","ranking","general"} for labeling.
    
    Note: Deprecated. Use chat_with_memory_async() for better performance.
    """
    user_message = message
    if supplemental_context:
        label = f"[DATA CONTEXT: {context_type.upper()}]" if context_type else "[DATA CONTEXT]"
        user_message += "\n\n" + label + "\n" + supplemental_context
    return chat_send_message(session_id=session_id, message=user_message, system_instruction=SYSTEM_INSTRUCTION)


async def chat_with_memory_async(session_id: str, message: str, supplemental_context: str | None = None, context_type: str | None = None) -> str:
    """Send a message to Gemini within a session (async version).

    - session_id: chat scope id (student/class/compare/general) for isolated memory.
    - supplemental_context: compact analytics + CSV tail to ground the answer.
    - context_type: one of {"student","class","compare","multi","ranking","general"} for labeling.
    """
    user_message = message
    if supplemental_context:
        label = f"[DATA CONTEXT: {context_type.upper()}]" if context_type else "[DATA CONTEXT]"
        user_message += "\n\n" + label + "\n" + supplemental_context
    
    logger.debug(f"Sending message to LLM", extra={"session_id": session_id, "context_type": context_type})
    
    response = await chat_send_message_async(
        session_id=session_id,
        message=user_message,
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    return response
