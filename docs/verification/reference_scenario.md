# Day 5: Reference Scenario Execution

## Overview
This document describes the reference test scenario used for Day 5 final verification. The scenario exercises the complete pipeline: **prompt → YAML generation → validation → Lua codegen → sandbox execution**.

## Reference Scenario: Array Last Operation

### Objective
Extract the last email from a list of email addresses using the `array_last` operation.

### Step 1: Generate YAML

**Request:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get last email from the list"}'
```

**Expected Response (200 OK):**
```json
{
  "session_id": "sess-<uuid>",
  "is_complete": true,
  "yaml": {
    "operation": "array_last",
    "parameters": {
      "source": "wf.vars.emails"
    }
  },
  "lua_code": "return wf.vars.emails[#wf.vars.emails]",
  "feedback": []
}
```

**Validation:**
- ✓ `is_complete == true` (YAML generation successful)
- ✓ `operation == "array_last"` (correct operation selected)
- ✓ `lua_code` field is populated with valid Lua
- ✓ `feedback` is empty (no validation errors)

---

### Step 2: Ask Clarification (if needed)

If Step 1 returns `is_complete: false`, use the `/ask` endpoint to provide clarification:

**Request:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-<uuid>",
    "question": "Extract the last item from the list"
  }'
```

**Expected Response (200 OK):**
```json
{
  "session_id": "sess-<uuid>",
  "is_complete": true,
  "yaml": {
    "operation": "array_last",
    "parameters": {
      "source": "wf.vars.emails"
    }
  },
  "lua_code": "return wf.vars.emails[#wf.vars.emails]",
  "feedback": []
}
```

---

### Step 3: Execute Generated Lua Code

**Request:**
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-<uuid>",
    "context": {
      "wf": {
        "vars": {
          "emails": [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com"
          ]
        }
      }
    }
  }'
```

**Expected Response (200 OK):**
```json
{
  "session_id": "sess-<uuid>",
  "operation": "array_last",
  "yaml": {
    "operation": "array_last",
    "parameters": {
      "source": "wf.vars.emails"
    }
  },
  "lua_code": "return wf.vars.emails[#wf.vars.emails]",
  "execution_result": {
    "status": "success",
    "exit_code": 0,
    "stdout": "charlie@example.com",
    "stderr": ""
  }
}
```

**Validation:**
- ✓ `status == "success"` (Lua execution completed without error)
- ✓ `exit_code == 0` (sandboxed process exited cleanly)
- ✓ `stdout` contains `"charlie@example.com"` (correct result)
- ✓ `stderr` is empty (no warnings/errors)

---

## Expected Timeline

| Step | Duration | Description |
|------|----------|-------------|
| 1. Generate YAML | ~2-5 seconds | Ollama inference for YAML generation |
| 2. Ask (if needed) | ~2-5 seconds | Clarification round with Ollama |
| 3. Execute | ~1-2 seconds | Lua sandbox execution (no inference) |
| **Total** | **~5-10 seconds** | Full reference scenario |

---

## Success Criteria

For Day 5 verification to **pass**, the reference scenario must:

1. ✅ Generate valid YAML on first attempt (or succeed after ask loop)
2. ✅ Produce syntactically correct Lua code (validated by luac)
3. ✅ Execute in sandbox with exit_code=0
4. ✅ Return expected output: `"charlie@example.com"`
5. ✅ Complete within ~10 seconds

---

## Integration with Day 1-4

This scenario validates:

- **Day 1** (Lua Codegen): ✓ Array_last template generates correct Lua
- **Day 2** (Schema Validation): ✓ Generated YAML passes jsonschema validation
- **Day 3** (Sandbox Execution): ✓ Lua runs in Docker with correct output
- **Day 4** (UI + E2E): ✓ Full endpoint flow works end-to-end

---

## Protocollab Integration

This scenario exercises the following protocollab components:

| Component | Role | Evidence |
|-----------|------|----------|
| `yaml_serializer` | Multi-document YAML parsing in /generate | Generates valid YAML output |
| `jsonschema_validator` | Parameter validation | Accepts valid parameters, rejects invalid |
| `protocollab.expression` | Array.last condition (if used in variations) | Results match expected for array operations |

---

## Recorded Date & Results

- **Date Executed**: [Will be filled during Phase 2]
- **Scenario Status**: [PASS / FAIL]
- **Total Time**: [seconds]
- **Model Used**: qwen2.5-coder:1.5b
- **GPU VRAM Peak**: [Will be measured in Phase 3]
- **Notes**: [Any additional observations]

