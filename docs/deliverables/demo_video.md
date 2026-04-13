# Day 5: Demo Video Recording

## Status
- **Video**: To be recorded during Phase 2-3 execution
- **Duration**: 2-3 minutes
- **Format**: Screen recording of API execution + terminal output

---

## Recording Plan

### Setup
1. Start `docker compose up` in WSL
2. Verify `/health` returns {"status": "ok"}
3. Open terminal with curl commands ready
4. Start screen recording (OBS or VS Code screen capture)

### Script (2-3 minutes)

**[0:00-0:30] Introduction**
```
"This is a demo of the Day 1-4 solution for the hackathon. 
We have a local Ollama model running qwen2.5-coder:1.5b for YAML generation,
and a Docker sandbox for safe Lua execution.
Let's walk through the complete pipeline with a real example."
```

**[0:30-1:00] Generate YAML**
```bash
# Show curl request
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get last email from the list"}'

# Show response
{
  "session_id": "sess-...",
  "is_complete": true,
  "yaml": {
    "operation": "array_last",
    "parameters": {"source": "wf.vars.emails"}
  },
  "lua_code": "return wf.vars.emails[#wf.vars.emails]"
}

"The LLM generated YAML and we validated it against the schema.
The system also generated the Lua code—all safe because
we use protocollab.expression for condition parsing."
```

**[1:00-2:00] Execute Lua in Sandbox**
```bash
# Show curl request with context
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-...",
    "context": {
      "wf": {
        "vars": {
          "emails": ["alice@example.com", "bob@example.com", "charlie@example.com"]
        }
      }
    }
  }'

# Show response
{
  "operation": "array_last",
  "execution_result": {
    "status": "success",
    "exit_code": 0,
    "stdout": "charlie@example.com",
    "stderr": ""
  }
}

"The Lua code executed in an isolated Docker container with:
--network none (no network access),
--cap-drop ALL (no system capabilities),
--read-only filesystem except /tmp.
Result: correctly returned the last email address."
```

**[2:00-2:30] Wrap-up**
```
"This demonstrates the complete Day 1-4 pipeline:
1. Natural language prompt
2. LLM generates YAML (using local Ollama)
3. Schema validation (protocollab.jsonschema_validator)
4. Lua code generation (protocollab.expression for conditions)
5. Sandbox execution (dockerized Lua runtime)
6. Safe, auditable results in ~5 seconds total

All of this works completely offline, with no external API dependencies.
The source code is available on GitHub with comprehensive documentation."
```

---

## Recording Technical Details

### Audio
- Clear microphone audio
- Minimal background noise
- Speak clearly and at normal pace

### Video Quality
- 1920x1080 or higher resolution
- Full screen capture showing:
  - Terminal/curl commands
  - API responses (JSON formatting)
  - Timestamps visible (to show execution speed)

### File Format
- MP4 (H.264 codec)
- Frame rate: 30fps
- Bitrate: 5-10 Mbps

---

## Video Hosting Options

1. **GitHub**: Upload to Releases or discussion
2. **YouTube**: Unlisted link for judge access
3. **Local**: Include in submission folder
4. **Cloud**: Google Drive, Dropbox (share link in README)

---

## Recording Checklist

- [ ] docker compose running, no errors
- [ ] /health endpoint returns green
- [ ] Ollama model downloaded (qwen2.5-coder:1.5b)
- [ ] Terminal configured (clear background, readable font)
- [ ] Microphone tested and ready
- [ ] Screen recording software installed (OBS, Camtasia, etc.)
- [ ] Curl commands copied (no typos in JSON)
- [ ] Backup curl command for second demo scenario
- [ ] Timer ready (ensure 2-3 minute total)
- [ ] Recording starts after API is fully ready

---

## Backup Recording Scenarios

If primary scenario fails:

**Scenario A: Error Loop demonstration**
- Send ambiguous prompt to `/generate`
- Show feedback returned
- Use `/ask` to clarify
- Show successful retry

```bash
# First: ambiguous prompt
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Do something with the data"}'
# Returns: is_complete: false, feedback: ["..."]

# Second: ask for clarification
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "question": "Extract the last item"}'
# Returns: is_complete: true, yaml: {...}
```

**Scenario B: Array filter with condition**
- Generate array_filter YAML
- Show protocollab.expression parsing the condition
- Execute with filtered results

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Filter emails that contain example.com"}'
# Shows condition transpiled via protocollab.expression
```

---

## Final Recording Status

- **Primary Video**: [Recording link]
- **Backup Scenario A**: [Link if available]
- **Backup Scenario B**: [Link if available]
- **Recording Date**: April 13, 2026
- **Status**: ⏳ PENDING (to be completed during Phase 2-3)

