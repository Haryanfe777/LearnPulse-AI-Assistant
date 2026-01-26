# Instructor AI Assistant for LearnPulse AI

An intelligent AI assistant that helps instructors analyze LearnPulse AI activity logs, track learner progress, generate individualized feedback, and answer questions about the platform and pedagogy—all in French or English.

---

## 🎯 Project Objectives

1. **Learner Progress Analysis:** Summarize each learner's performance across coding concepts (Loops, Conditionals, Debugging, Functions)
2. **Individualized Feedback:** Generate specific, actionable recommendations per learner
3. **Class Insights:** Provide class-wide trends and charts, identify struggling learners, and suggest interventions
4. **Bilingual Support:** Seamlessly handle French and English queries
5. **Context-Aware Conversations:** Remember prior questions and provide intelligent follow-ups
6. **Company Knowledge:** Answer general questions about LearnPulse AI's pedagogy, metrics, and best practices

---

## 📁 Project Structure

```
teacher-assistant/
├── main.py                      # FastAPI app entrypoint
├── app_streamlit.py             # Streamlit UI frontend
├── requirements.txt             # Python dependencies
├── PROJECT_REVIEW.md            # Comprehensive project assessment
├── IMPLEMENTATION_ROADMAP.md    # Phased enhancement plan
├── README.md                    # This file
├── mock_data/
│   └── mock_game_logs.csv       # Sample game log data
├── knowledge/                   # Company knowledge base (NEW)
│   ├── company_info.md          # LearnPulse AI mission, pedagogy, support
│   └── teacher_guide.md         # Metric interpretation, best practices
└── src/
    ├── assistant.py             # AI prompt templates & global system instruction
    ├── analytics.py             # Analytics functions (learner stats, trends, comparisons, rankings)
    ├── routes.py                # FastAPI endpoints (/chat, /student, /class, /meta)
    ├── routes_intent.py         # LLM-based intent classifier
    ├── data_loader.py           # CSV loading & basic queries
    ├── vertex_client.py         # Google Vertex AI (Gemini) client
    ├── config.py                # Environment config (PROJECT_ID, REGION, credentials)
    └── utils.py                 # Utility functions (text sanitization)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Google Cloud account with Vertex AI enabled
- Service account with Vertex AI permissions

### Installation

1. **Clone the repository** (or navigate to the folder)
   ```bash
   cd C:\Users\USER\teacher-assistant
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root (local dev only):
   ```env
   PROJECT_ID=your-gcp-project-id
   REGION=europe-west1
   # Local dev only (do not set in Cloud Run):
   GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json
   JWT_SECRET_KEY=change-me-in-production
   STUDENT_COL=student_name
   CLASS_COL=class_id
   SCORE_COL=score
   DATE_COL=date
   ```

5. **Run the FastAPI backend**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Run the Streamlit frontend** (in a separate terminal)
   ```bash
   streamlit run app_streamlit.py
   ```

7. **Open your browser**
   - Backend API: http://localhost:8000
   - Frontend UI: http://localhost:8501

---

## 🎮 Usage Examples

### Chat Interface (Streamlit)

**Single Learner Query:**
```
User: How is Aisha doing with Debugging?
Assistant: [Provides summary with stats, weekly trend, and specific feedback]
```

**Comparison:**
```
User: Compare Adam and Zoe's performance
Assistant: [Shows side-by-side metrics with deltas in a table]
```

**Class Summary:**
```
User: Summarize class 4B
Assistant: [Provides class-wide stats, trends, and top concepts needing attention]
```

**Ranking:**
```
User: Who are the top 5 learners in Loops last 3 weeks?
Assistant: [Lists ranked learners with scores]
```

**Company Question:**
```
User: What is LearnPulse AI's teaching philosophy?
Assistant: [Pulls from knowledge base and explains activity-based learning approach]
```

**Follow-up (Context-Aware):**
```
User: Compare Adam and Aisha
Assistant: [Shows comparison table with Delta column]
User: What does the Delta column mean?
Assistant: [Explains Delta = Adam - Aisha for each metric]
```

### API Endpoints

- **GET** `/student/{name}` - Get learner summary with individualized feedback
- **GET** `/class/{class_id}` - Get class overview
- **POST** `/chat` - Conversational interface with context memory
- **GET** `/meta` - List all learners and classes
- **GET** `/health` - Health check

---

## 🧠 How It Works

### 1. Intent Classification
When an instructor asks a question, the system:
1. **Detects entities** (learner names, class IDs) using fuzzy matching
2. **Classifies intent** via LLM router (`routes_intent.py`):
   - `student_query` - single learner analysis
   - `compare_query` - compare two learners
   - `multi_student_query` - multiple learners (no comparison)
   - `class_query` - class-wide insights
   - `ranking_query` - top/bottom N learners
   - `general_query` - company/pedagogy questions
3. **Scopes memory** by intent to prevent cross-talk (e.g., `session_id:learner:aisha`)

### 2. Grounding & Analytics
Before calling the LLM, the system:
1. **Computes analytics** (avg score, trends, concept breakdown, etc.)
2. **Builds grounding text** with:
   - Concise stat summary (e.g., "Sessions: 21, Avg score: 64.7, Lowest concept: Debugging")
   - CSV tail (last 40-80 rows) for semantic hooks
3. **Injects into prompt** with a label (e.g., `[DATA CONTEXT: STUDENT]`)

### 3. LLM Response
The Gemini model:
1. **Follows global system instruction** (role, behavior, output format)
2. **Grounds answer in provided data** (no hallucination)
3. **Returns structured response** with sections: Answer, Evidence, Next steps
4. **Adapts language** (French if query is in French)

### 4. Context Persistence
For follow-ups:
- Previous scope (student/class/compare) is **persisted** in session state
- If a new message has no explicit entities, the system **reuses prior scope**
- This allows "What does Delta mean?" to correctly reference the previous comparison table

---

## 📊 Current Capabilities

### ✅ Implemented
- Learner stats (sessions, scores, trends, concept breakdown, streaks, feedback notes)
- Class trends (learner count, avg score, weekly trends, concept distribution)
- Comparisons (side-by-side with deltas)
- Multi-learner summaries
- Rankings (top N by score, filterable by class/concept/timeframe)
- Intent routing with fuzzy name matching
- Scoped chat memory (no leakage across query types)
- Bilingual support (French/English auto-detection)
- Context-aware follow-ups
- Company knowledge base (mission, pedagogy, instructor guide)

### ⚠️ In Progress
- Visualizations (charts for trends, concept breakdown, rankings)
- Individualized feedback generation
- Performance optimizations (model caching, timeout fixes)

### 🔮 Planned (See IMPLEMENTATION_ROADMAP.md)
- PDF/HTML report export
- Authentication & multi-tenancy
- Database migration (SQLite/Postgres)
- Predictive analytics (at-risk learner alerts)
- Voice interface

---

## 📈 Next Steps

**Priority 1: Visualizations** (Week 1)
- Add Plotly charts for weekly trends, concept breakdown, rankings
- Integrate into Streamlit and API responses

**Priority 2: Performance** (Week 1)
- Cache Vertex model with `@lru_cache`
- Increase Streamlit timeout to 90s
- Skip intent router for unambiguous queries

**Priority 3: Knowledge Base Integration** (Week 1)
- Wire `knowledge/` files into general query flow
- Test company question responses

**Priority 4: Testing & Polish** (Week 2)
- Add pytest suite for analytics and routes
- Test bilingual quality with native French speakers
- Pilot with 2-3 real instructors

See **IMPLEMENTATION_ROADMAP.md** for detailed implementation guides.

---

## ✅ Production Checklist

- Set `ENVIRONMENT=production` and `DEBUG=false`
- Provide a secure `JWT_SECRET_KEY` (no defaults)
- Use the Cloud Run service account (no JSON key, no `GOOGLE_APPLICATION_CREDENTIALS`)
- Lock down `CORS_ORIGINS` to your real domains only
- Configure Redis and database URLs for production
- Verify HTTPS/TLS, domain DNS, and health checks
- Enable structured logging and error monitoring
- Configure SMTP settings for support escalation emails
- Replace mock data with real data sources (or remove `mock_data/`)
- Run tests and a smoke test on `/health`

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes and test locally
3. Run linter: `ruff check src/`
4. Commit: `git commit -m "Add new feature"`
5. Push and open PR

---

## 📝 Documentation

- **PROJECT_REVIEW.md** - Comprehensive gap analysis and recommendations
- **IMPLEMENTATION_ROADMAP.md** - Phased enhancement plan with code templates
- **knowledge/company_info.md** - LearnPulse AI company information
- **knowledge/teacher_guide.md** - Metric interpretation and best practices

---

## 🐛 Known Issues

1. **Intermittent 30s timeouts** - Due to two sequential LLM calls (intent + chat). Mitigated by increasing timeout to 90s and caching model.
2. **No visualizations yet** - Text-only output; charts coming in Phase 1.
3. **Static CSV data** - No real-time updates; database migration planned for Phase 2.
4. **No authentication** - Single-instructor use only; multi-tenancy planned for Phase 2.

---

## 📞 Support

- **Email:** support@learnpulse.ai
- **GitHub Issues:** [Create an issue](https://github.com/your-org/teacher-assistant/issues)
- **Community Forum:** https://community.learnpulse.ai

---

## 📜 License

[Your License Here]

---

## 🙏 Acknowledgments

Built with:
- **Google Vertex AI (Gemini 2.5 Flash)** for LLM reasoning
- **FastAPI** for backend API
- **Streamlit** for frontend UI
- **Pandas** for data analytics
- **Plotly** for visualizations (coming soon)

Inspired by LearnPulse AI's mission to make coding accessible through activity-based learning.

