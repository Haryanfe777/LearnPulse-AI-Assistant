"""Lightweight LLM-powered intent router used before heuristics in /chat."""
from src.vertex_client import generate_text

INTENT_SYSTEM = """You are a router for an instructor AI assistant. Analyze the message and return JSON:

{
  "intent": "<one of: student_query, class_query, compare_query, multi_student_query, ranking_query, visualization_query, pure_general, data_general>",
  "students": [list of student names mentioned],
  "class_id": "class identifier or null",
  "concepts": [programming concepts like "loops", "conditionals"],
  "timeframe": "time reference or null",
  "visualization_type": "chart/graph/plot type or null",
  "has_pronoun": true/false
}

Intent Definitions:
- pure_general: Questions about teaching, programming concepts, strategies (NO data needed)
  Examples: "What is a loop?", "How do I teach conditionals?", "Explain debugging strategies"

- data_general: General questions that NEED student data to answer
  Examples: "Who needs help?", "Show overall performance", "Which concept is hardest?"

- visualization_query: Requests for charts, graphs, plots
  Examples: "Create a chart", "Show me a graph of performance", "Visualize progress", "Plot scores"
  Common keywords: chart, graph, plot, visualize, show me, display

- student_query: Questions about a specific student
- class_query: Questions about a specific class
- compare_query: Comparing 2 students
- multi_student_query: Questions about 3+ students
- ranking_query: Ranking/sorting students by metrics

**Pronoun Handling:**
- If message contains pronouns ("her", "his", "she", "he") WITHOUT explicit names, mark has_pronoun: true
- The backend will resolve pronouns using session history

If unsure between pure_general and data_general, choose pure_general.
Be concise. Return only valid JSON.
"""

def classify_intent(message: str, known_students: list[str], known_classes: list[str]) -> dict:
    """Return an intent JSON dict for a message given known entity vocabularies.

    Falls back to general_query if parsing fails.
    """
    names = ", ".join(known_students[:40])
    classes = ", ".join(known_classes[:40])
    prompt = f"""{INTENT_SYSTEM}
Message: {message}
Known students: [{names}]
Known classes: [{classes}]
Return only JSON."""
    try:
        import json
        raw = generate_text(prompt)
        return json.loads(raw.strip().split("```")[-1]) if "```" in raw else json.loads(raw)
    except Exception:
        return {"intent": "general_query", "students": [], "class_id": None, "concepts": [], "timeframe": None, "k": None}
