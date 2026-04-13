# Day 5: 7-Minute Presentation Outline

## Overview
Presentation delivered to hackathon judges demonstrating the complete Day 1-4 solution with live demo and architecture explanation.

---

## Timeline

### 1. Problem Statement (1 minute)

**Objective**: Frame why this project matters

**Key Points**:
- **Challenge**: Automating validation of network protocol interfaces
  - Protocols define message structures, field constraints, and operations
  - Manual validation is error-prone and time-consuming
  - Need: automated system that converts natural language → structured validation rules → executable tests

- **Solution Approach**: 
  - LLM-guided interface generation (natural language → YAML)
  - Schema validation (ensures compliance)
  - Lua scripting + sandbox execution (safe, auditable code)

**Talking Points** (30 seconds):
> "Imagine a network engineer describing a protocol operation in plain English. Our system understands that description, validates it against protocol specifications, and generates safe, executable Lua code to test it—all locally, without external dependencies."

---

### 2. Architecture & Protocollab Integration (2 minutes)

**Objective**: Explain the technical pipeline and protocollab's role

**Diagram Reference**: [docs/diagrams/day5_architecture.mmd](docs/diagrams/day5_architecture.mmd)

**Components**:

1. **Input Layer** (30 sec)
   - User provides: **natural language prompt** (e.g., "Extract emails from a list")
   - System: Sent to **local Ollama** (qwen2.5-coder:1.5b model)
   - **Why local?** Offline, no external API dependencies, reproducible

2. **Processing Pipeline** (60 sec)
   - **Day 1 - YAML Generation** (LLM):
     ```
     Prompt → Ollama → generated YAML
     Example: operation: array_last, parameters: {...}
     ```
   
   - **Day 2 - Validation** (protocollab **yaml_serializer** + **jsonschema_validator**):
     ```
     → yaml_serializer parses YAML safely with structure limits
     → jsonschema_validator checks operation is one of 7 allowed
     → Rejects invalid, returns feedback if needed
     ```
   
   - **Day 3 - Lua Code Generation** (protocollab **expression** module):
     ```
     → Selects appropriate Lua template (array_last.lua.jinja2, etc.)
     → For array_filter: parses condition via protocollab.expression
     → Transpiles condition to Lua (prevents injection)
     → Renders complete Lua code
     ```
   
   - **Day 3 - Sandbox Execution**:
     ```
     → Docker container with: --network none, --cap-drop ALL
     → Executes Lua in isolated environment
     → Returns: status, stdout, stderr, exit_code
     ```

3. **Why Protocollab?** (30 sec)
   - **yaml_serializer**: Safe YAML parsing with access controls
   - **jsonschema_validator**: Pluggable validation (can swap backends)
   - **expression**: Domain-specific language for conditions (safe AST → Lua transpilation)
   - **Open-source**: Auditable, no black-box dependencies

---

### 3. Live Demo (2 minutes)

**Objective**: Show the system working end-to-end

**Setup** (before presentation):
- Have `docker compose up` already running
- Open browser with `localhost:8000/health` showing green
- Have VS Code or terminal ready with curl commands

**Demo Scenario**: Array Last Operation

**Step 1: Generate** (30 sec)
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get last email from the list"}'
```
**Expected Output**:
```json
{
  "session_id": "sess-uuid",
  "is_complete": true,
  "yaml": {
    "operation": "array_last",
    "parameters": {"source": "wf.vars.emails"}
  },
  "lua_code": "return wf.vars.emails[#wf.vars.emails]"
}
```
**Talking Points**: "The LLM understood our instruction and generated valid YAML—all validated against our schema."

**Step 2: Execute** (60 sec)
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-uuid",
    "context": {
      "wf": {"vars": {"emails": ["alice@example.com", "bob@example.com", "charlie@example.com"]}}
    }
  }'
```
**Expected Output**:
```json
{
  "operation": "array_last",
  "execution_result": {
    "status": "success",
    "exit_code": 0,
    "stdout": "charlie@example.com"
  }
}
```
**Talking Points**: "The Lua code ran safely in an isolated sandbox and returned the correct result."

**Step 3 (Optional): Array Filter with Condition** (if time permits)
- Show how protocollab.expression parses a condition like `"email contains 'example.com'"`
- Transpiles to Lua and filters the array

---

### 4. Performance & Deployment Metrics (1 minute)

**Objective**: Demonstrate the solution meets hackathon constraints

**Key Metrics**:

1. **Performance**:
   - **Generation**: 2-5 seconds (Ollama inference)
   - **Validation**: < 100ms (local YAML + schema)
   - **Execution**: 1-2 seconds (Lua sandbox)
   - **Total E2E**: ~5-10 seconds ✅

2. **Resource Constraints**:
   - **GPU VRAM**: Peak < 8 GB (model runs locally)
   - **Sandbox Memory**: 128 MB per execution
   - **Sandbox Timeout**: 5 seconds
   - **Sandbox Network**: Disabled (--network none)

3. **Deployment**:
   - **Docker Compose**: One-command startup
     ```bash
     git submodule update --init --recursive
     docker compose up
     ```
   - **Dependencies**: All local (no cloud APIs)
   - **Reproducibility**: Identical results every run

---

### 5. Defense: Why This Architecture (1 minute)

**Objective**: Answer potential judge questions

**Key Talking Points**:

1. **Why Ollama?**
   - Local inference (privacy, offline)
   - Model choice: qwen2.5-coder optimized for code generation
   - Memory efficient (qwen:1.5b fits in 8GB VRAM)

2. **Why Protocollab?**
   - Domain-specific library for protocol specifications
   - yaml_serializer provides safe YAML parsing with access controls
   - jsonschema_validator pluggable architecture (can swap implementations)
   - expression module prevents injection via safe AST transpilation

3. **Why Lua Sandbox?**
   - Lightweight, fast scripting language
   - Docker isolation with hardened security:
     - --network none (no network access)
     - --cap-drop ALL (no capabilities)
     - --read-only (filesystem immutable except /tmp)
     - --user nobody (unprivileged)
   - Deterministic output (no external calls)

4. **Why This Approach?**
   - **Auditable**: All code is open-source (can inspect every step)
   - **Safe**: No code injection, all generated code validated
   - **Reproducible**: Same input → same output, every time
   - **Offline**: Works without internet, no API rate limits

---

### 6. Demo Variations (if time permits)

**Backup Scenarios** (in case main demo has issues):

**Scenario A: Error & Fix Loop**
- Show a vague prompt that generates feedback
- Use `/ask` endpoint to clarify
- Demonstrate the system converges to valid YAML

**Scenario B: Array Filter with Condition**
- Show protocollab.expression parsing a condition
- Display transpiled Lua code
- Execute with test data

**Scenario C: Show Offline Nature**
- Describe how network is isolated
- Explain Docker sandbox constraints
- Highlight no external APIs called

---

## Presentation Assets

### Slides/Diagrams

1. **[docs/diagrams/day5_architecture.mmd](../diagrams/day5_architecture.mmd)**
   - C4 architecture diagram showing all components
   - Color-coded: API (yellow), Services (gray), Protocollab (blue), Runtime (red)
   - Shows integration points and data flow

2. **[docs/protocollab_integration.md](./protocollab_integration.md)**
   - Detailed breakdown of each protocollab component
   - Code locations with line numbers
   - Integration evidence and test coverage

3. **[docs/reference_scenario.md](../verification/reference_scenario.md)**
   - Complete curl commands for demo
   - Expected responses and success criteria
   - End-to-end timeline estimates

### Supporting Docs

4. **[docs/offline_verification.md](../verification/offline_verification.md)**
   - Proof of no external API calls
   - Network isolation verification
   - Configuration hardcoding

5. **[README.md](../../README.md)**
   - Quick start (docker compose up)
   - Model installation
   - Configuration parameters
   - Example curl commands

---

## Timing Breakdown

| Section | Duration | Notes |
|---------|----------|-------|
| Problem Statement | 1 min | Set context and motivation |
| Architecture & Protocollab | 2 min | Explain technical pipeline |
| Live Demo | 2 min | Show system in action |
| Performance & Deployment | 1 min | Metrics and constraints |
| Q&A Buffer | 1 min | (7 min total) |

---

## Common Judge Questions & Answers

**Q: Why not use ChatGPT or Claude?**
> A: We needed an offline, auditable solution. Our local Ollama model is reproducible, works without API keys, and complies with hackathon constraints. Plus it's more cost-effective for repeated runs.

**Q: How do you prevent code injection in Lua generation?**
> A: Three layers:
> 1. YAML schema validation (operation and parameters must match schema)
> 2. Parameter sanitization (no raw string interpolation)
> 3. For array_filter, protocollab.expression parses condition as AST before transpiling to Lua (prevents arbitrary code)

**Q: What if the LLM generates invalid YAML?**
> A: The system asks for clarification. It returns a feedback loop with /ask endpoint, allowing the user to correct the prompt. We demonstrate this with our error handling E2E test.

**Q: Why Lua specifically?**
> A: Lua is lightweight, safe to sandbox, and commonly used in protocol testing frameworks. It's fast, deterministic, and easy to reason about for auditing.

**Q: Can this run without Docker?**
> A: The `/generate` and `/ask` endpoints (LLM inference) can run without Docker. The `/execute` endpoint requires Docker for sandbox isolation. For the full pipeline, Docker is required.

---

## Delivery Checklist

Before presenting:
- [ ] Verify `docker compose up` running with no errors
- [ ] Test `/health` endpoint
- [ ] Verify `localhost:8000` accessible
- [ ] Test main demo scenario (array_last)
- [ ] Have curl commands copied to clipboard
- [ ] Have 2 backup scenarios ready (error loop + array_filter)
- [ ] Ensure Ollama model downloaded (qwen2.5-coder:1.5b)
- [ ] Open architecture diagram (day5_architecture.mmd)
- [ ] Have README open as reference

---

## Post-Presentation

**Artifacts to Have Ready**:
1. ✅ Repository link (GitHub)
2. ✅ README.md (complete with examples)
3. ✅ Architecture diagram (Mermaid)
4. ✅ Demo video (recording of full scenario)
5. ✅ Protocollab integration doc (protocollab_integration.md)

