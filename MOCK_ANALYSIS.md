# Mock & Stub Implementation Analysis

## Executive Summary

The codebase contains **significant mock and fallback patterns** designed to allow operation without real LLM providers. The key findings are:

1. **Config default is "mock"** but **no mock provider implementation exists** — will crash if used
2. **All agents have heuristic fallbacks** — keyword/pattern-based analysis runs when LLM models aren't configured
3. **Frontend has extensive hardcoded mock data** — allows UI testing without backend
4. **Smart fallback mechanism** — frontend switches to mock mode if backend network is unreachable
5. **.env currently configured with OpenAI** — using custom base URL pointing to local inference server

---

## File-by-File Analysis

### 🔴 CRITICAL: Backend Configuration

**File:** `backend/app/core/config.py` (Line 56)

```python
llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
```

**Issue:** Defaults to `"mock"` but `llm.py` doesn't handle it.

**What it does:** 
- Sets default LLM provider to "mock" if `LLM_PROVIDER` env var is not set
- Supports: "openai", "anthropic" (but not "mock")

**Current .env value:** `LLM_PROVIDER=openai` with custom base URL

**Impact:** CRITICAL - Will crash if someone uses default config

---

### 🔴 CRITICAL: LLM Service No Mock Handler

**File:** `backend/app/services/llm.py` (Lines 1-100)

**What it does:**
```python
def complete(model: str, system: str, user: str, ...) -> str:
    # Only handles: "anthropic:model-id" or "openai:model-id"
    # Raises ValueError for unknown provider
```

**Missing:** No implementation for `"mock"` provider

**Impact:** 
- Will raise `ValueError("Unknown LLM provider: 'mock'")` if default config used
- Only supports: `anthropic` and `openai` providers
- No fallback to stub/mock responses

---

### 🟡 AGENTS: Heuristic Fallback Pattern (All 5 Agents)

All agent files follow this pattern:

**File:** `backend/app/agents/document_fact_agent.py`

```python
def run(self, state: AgentState) -> AgentState:
    model = settings.document_fact_agent_model  # e.g., "openai:gpt-4o"
    if model:
        try:
            return self._run_llm(state, model)  # Real LLM call
        except Exception:
            logger.warning("LLM call failed; falling back to heuristic.")
    return self._run_heuristic(state)  # Keyword-based analysis
```

#### 1. **DocumentFactAgent** (`backend/app/agents/document_fact_agent.py`)

**LLM Path:**
- Extracts 12 required facts from uploaded documents using LLM
- Requires: `DOCUMENT_FACT_AGENT_MODEL` env var
- Example: `openai:gpt-4o-mini`

**Heuristic Fallback:**
- Uses keyword search: "Purpose", "Users", "Sector", "Input data", etc.
- Retrieves citations from corpus based on keyword matches
- All facts marked as "uncertain" or "missing" if not found

**Current Status (from .env):**
```
DOCUMENT_FACT_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
```
✅ Configured with real LLM

---

#### 2. **AISystemDefinitionAgent** (`backend/app/agents/ai_system_definition_agent.py`)

**LLM Path:**
- Assesses whether use case involves an AI system under EU AI Act Article 3(1)
- Requires: `AI_SYSTEM_AGENT_MODEL` env var
- Uses: system prompt explaining AI system definition + retrieved context

**Heuristic Fallback:**
- Searches for AI signals: "AI", "machine learning", "model", "algorithm", "automated", "prediction", "recommendation"
- If any signal found → "medium" confidence, uses keyword retrieval
- If no signals → "low" confidence, marks as uncertain

**Current Status (from .env):**
```
AI_SYSTEM_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
```
✅ Configured with real LLM

---

#### 3. **RiskClassificationAgent** (`backend/app/agents/risk_classification_agent.py`)

**LLM Path:**
- Classifies risk level: PROHIBITED / HIGH-RISK / LIMITED RISK / MINIMAL RISK
- Requires: `RISK_CLASSIFICATION_AGENT_MODEL` env var
- System prompt includes full Annex III categories and Article 5 definitions

**Heuristic Fallback:**
- Checks for prohibited signals: biometric, emotion recognition, manipulation, social scoring, etc.
- Checks for sector signals: employment, education, law enforcement, migration, infrastructure, etc.
- Returns "medium" confidence with cautious reasoning

**Current Status (from .env):**
```
RISK_CLASSIFICATION_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
```
✅ Configured with real LLM

---

#### 4. **ObligationsGovernanceAgent** (`backend/app/agents/obligations_governance_agent.py`)

**LLM Path:**
- Maps applicable EU AI Act obligations and governance gaps
- Requires: `OBLIGATIONS_AGENT_MODEL` env var
- Returns: Multiple obligation sections + governance observations

**Heuristic Fallback:**
- Analyzes provider vs deployer roles
- Checks for transparency obligations
- Checks for GPAI/LLM component signals
- Returns 3-4 static obligation sections with low-medium confidence

**Current Status (from .env):**
```
OBLIGATIONS_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
```
✅ Configured with real LLM (but not in .env - uses heuristic!)

---

#### 5. **CriticUncertaintyAgent** (`backend/app/agents/critic_uncertainty_agent.py`)

**Structure (Different from others):**
- **Always runs heuristic first** (deterministic structural checks)
- **Then runs LLM critique on top** if model configured
- Requires: `CRITIC_AGENT_MODEL` env var (optional)

**Heuristic Pass:**
- Identifies missing critical facts (Purpose, Sector, Affected persons, etc.)
- Identifies weak evidence (marked "found" but no citations)
- Finds visible contradictions
- Adds missing_information, uncertainties, follow_up_questions

**LLM Critique:**
- Runs on top of heuristic results
- Adds more nuanced uncertainty analysis
- Requires: `CRITIC_AGENT_MODEL`

**Current Status (from .env):**
```
# NOT CONFIGURED - only heuristic runs
```
⚠️ Only heuristic analysis runs

---

### 🟡 CHAT SERVICE: Fallback Pattern

**File:** `backend/app/services/chat.py`

```python
def answer_follow_up(case_id: str, message: str, ...) -> ChatResult:
    model = settings.chat_agent_model
    if model:
        try:
            content = _build_llm_answer(model, text, analysis, citations)
        except Exception:
            logger.warning("Chat LLM call failed; falling back to template answer.")
            content = _build_template_answer(...)
    else:
        content = _build_template_answer(...)
```

**LLM Path:**
- Uses full LLM call with system prompt
- Requires: `CHAT_AGENT_MODEL` env var
- Grounds answers in assessment and retrieved chunks

**Template Fallback:**
- Structured response using: question + assessment summary + risk + chunks + new_facts
- No actual LLM call, uses string interpolation

**Current Status (from .env):**
```
# NOT CONFIGURED - uses template fallback
```
⚠️ Only template-based answers returned

---

### 🟡 FRONTEND: Hardcoded Mock Data

**File:** `frontend/src/api/mockData.ts`

**Contents:**

1. **mockCases** (Lines 11-25)
   - 2 hardcoded demo cases:
     - "GenAI loan application triage assistant"
     - "AI-assisted radiology pre-read"

2. **mockDocuments** (Lines 30-47)
   - 3 hardcoded documents per case
   - Static filenames and metadata

3. **mockAnalysis(caseId)** (Lines 82-440+)
   - Complete hardcoded analysis result for demo case
   - Includes:
     - 6 extracted facts with citations
     - AI system assessment (conclusion, reasoning, citations)
     - Risk classification (high-risk loan evaluation)
     - 5 obligation sections (risk management, data governance, human oversight, transparency, FRIA)
     - Governance observations
     - Citations to EU AI Act articles

4. **mockMessages** (Line 440)
   - Empty object (no hardcoded chat messages)

**Impact:**
- Allows full UI functionality without backend
- Demonstrates complete analysis workflow
- Data is realistic but fictional (fabricated citations and content)

---

### 🟡 FRONTEND: Smart Fallback Mechanism

**File:** `frontend/src/api/client.ts`

**Pattern:**

```typescript
async function withFallback<T>(
    live: () => Promise<T>,
    fallback: () => T | Promise<T>
): Promise<T> {
    try {
        const result = await live();
        setMode("live");
        return result;
    } catch (e) {
        if (e instanceof ApiError && e.status === undefined) {
            // Network error (backend unreachable)
            setMode("mock");
            return fallback();
        }
        throw e;  // Real HTTP errors still propagate
    }
}
```

**Behavior:**
- ✅ Try real API call
- ❌ If NETWORK ERROR (backend unreachable) → switch to mock mode
- ❌ If HTTP ERROR (backend reachable but returned error) → propagate error

**All API endpoints use this pattern:**
- `createCase()` - real API or mock state
- `listCases()` - real API or mockData
- `getCase()` - real API or mockData lookup
- `uploadDocuments()` - real API or mock state
- `runAnalysis()` - real API or hardcoded mockAnalysis (delays 600ms)
- `getAnalysis()` - real API or mock state
- `getMessages()` - real API or mock state

---

## Summary Table

| Component | Type | LLM Config | Current State | Impact |
|-----------|------|-----------|---------------|--------|
| **Config default** | Default | "mock" | Will crash if used | 🔴 CRITICAL |
| **llm.py** | Service | anthropic, openai | No mock handler | 🔴 CRITICAL |
| **DocumentFactAgent** | Agent | optional | Configured ✅ | Working |
| **AISystemDefinitionAgent** | Agent | optional | Configured ✅ | Working |
| **RiskClassificationAgent** | Agent | optional | Configured ✅ | Working |
| **ObligationsGovernanceAgent** | Agent | optional | NOT configured | Using heuristic ⚠️ |
| **CriticUncertaintyAgent** | Agent | optional | NOT configured | Using heuristic ⚠️ |
| **ChatService** | Service | optional | NOT configured | Template fallback ⚠️ |
| **Frontend mockData** | UI Data | N/A | Hardcoded | Demo only 🟡 |
| **Frontend fallback** | Mechanism | N/A | Smart network fallback | Good 💚 |

---

## What Gets Generated

### When LLM Models ARE Configured:
1. ✅ Facts extracted by DocumentFactAgent via LLM
2. ✅ AI system assessment by AISystemDefinitionAgent via LLM
3. ✅ Risk classification by RiskClassificationAgent via LLM
4. ✅ Obligations analyzed by ObligationsGovernanceAgent via LLM
5. ✅ Uncertainty review by CriticUncertaintyAgent (heuristic + optional LLM)
6. ⚠️ Chat answers use template fallback (no LLM for chat)

### When LLM Models ARE NOT Configured:
1. ⚠️ Facts extracted by keyword/pattern matching
2. ⚠️ AI system assessment by keyword signals
3. ⚠️ Risk classification by sector/prohibited-practice signals
4. ⚠️ Obligations inferred from heuristic rules
5. ⚠️ Uncertainty review by structural analysis only
6. ⚠️ Chat answers use template interpolation

---

## Priority Order for Changes

### 🔴 MUST FIX (System will crash without these)

1. **Add mock provider or change default**
   - File: `backend/app/core/config.py`
   - Change: `default_factory=lambda: os.getenv("LLM_PROVIDER", "mock")` 
   - To: `default_factory=lambda: os.getenv("LLM_PROVIDER", "heuristic")` OR add mock handler
   - Impact: System won't crash on default config

2. **Implement mock LLM provider** (optional, if "mock" is desired)
   - File: `backend/app/services/llm.py`
   - Add: handler for `provider == "mock"` that returns stub responses
   - Impact: Allow explicit "mock" mode for testing

### 🟡 SHOULD FIX (Incomplete analysis without these)

3. **Configure remaining agent models**
   - File: `.env`
   - Add: `OBLIGATIONS_AGENT_MODEL`, `CRITIC_AGENT_MODEL`, `CHAT_AGENT_MODEL`
   - Impact: All analysis sections generated by real LLM instead of heuristics

4. **Implement LLM chat service**
   - File: `backend/app/services/chat.py`
   - Current: Uses template fallback with string interpolation
   - Issue: Chat answers are not LLM-generated
   - Impact: More intelligent, contextual follow-up answers

### 💚 NICE TO HAVE

5. **Remove or document frontend mock data**
   - Reason: Hardcoded analysis results are realistic but fictional
   - Consider: Keep for demo/testing purposes or replace with real test cases

---

## Testing Impact

**Current Test Usage (backend/tests/):**

- `test_agents.py`: Tests run agents with heuristic fallback (no LLM env vars set)
  - Verifies agent output structure
  - Verifies citations resolve to actual chunks
  - No LLM calls made during tests ✅

- `test_end_to_end_demo.py`: Full workflow test
  - Creates case, uploads document, runs analysis, chat
  - Uses heuristic fallback (no LLM env vars)
  - Verifies citations are verified correctly
  - No LLM calls made during tests ✅

**Frontend Tests:**
- No automated tests found
- UI can use mock data or live API based on network availability

---

## Real vs Mock Analysis Comparison

### Documentary Fact Extraction

**LLM (Real):**
- Extracts facts with LLM understanding of context
- Can identify subtle mentions
- Produces "found" vs "uncertain" distinction based on semantic confidence
- Example: Recognizes "algorithmic decision" as evidence of automation level

**Heuristic (Mock):**
- Searches for exact keywords or keyword phrases
- Must find explicit text matches
- Marks as "missing" if no keyword match
- Example: Requires explicit word "automated" or "automation"

### Risk Classification

**LLM (Real):**
- Understands nuanced risk factors
- Can read between the lines
- Produces confidence scores based on evidence strength
- Example: "system for evaluating X" → recognizes Annex III §5(b)

**Heuristic (Mock):**
- Searches for sector keywords: "employment", "education", "biometric"
- Searches for prohibited practice signals
- Returns medium-confidence preliminary classification
- Example: Only flags if documents explicitly mention "employment" or "loan evaluation"

---

## Configuration Examples

### Development: With Real LLM (Current .env)
```ini
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://95.133.252.22:8000/v1
OPENAI_API_KEY=super-secret-api-key
DOCUMENT_FACT_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
AI_SYSTEM_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
RISK_CLASSIFICATION_AGENT_MODEL=openai:meta-llama/Llama-3.3-70B-Instruct
```
**Result:** Full LLM analysis ✅

### Testing: Heuristic-Only Mode
```ini
# Don't set agent-specific models
# Agents fall back to heuristic analysis
```
**Result:** Pattern-based analysis, fast, no LLM calls needed ✅

### Production: Full Configuration
```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
DOCUMENT_FACT_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
AI_SYSTEM_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
RISK_CLASSIFICATION_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
OBLIGATIONS_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
CRITIC_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
CHAT_AGENT_MODEL=anthropic:claude-opus-4-1-20250805
```
**Result:** Full LLM analysis including chat ✅

---

## Next Steps

1. **Immediate:** Fix config default (change "mock" to something that won't crash)
2. **Short-term:** Configure remaining agent models
3. **Medium-term:** Implement LLM chat service
4. **Long-term:** Consider production LLM provider (AWS Bedrock, Azure OpenAI, etc.)
