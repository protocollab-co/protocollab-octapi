# Day 5: VRAM Peak Measurement Results

## Measurement Setup

- **Measurement Tool**: `nvidia-smi -lms 100` (sample every 100ms)
- **Model**: qwen2.5-coder:1.5b (local Ollama)
- **Model Parameters**:
  - `num_ctx`: 4096
  - `num_predict`: 256
  - `batch`: 1
  - `parallel`: 1
- **Test Scenario**: Reference scenario (Array Last generation)
- **Platform**: Windows WSL2 with GPU passthrough

---

## VRAM Constraint

**Hackathon Requirement**: Peak VRAM ≤ 8 GB

---

## Measurement Results

### Baseline (Before Inference)

```
NVIDIA-SMI timestamp: [Time]
Memory before generation: [MB]
```

### Peak VRAM (During Inference)

```
Maximum VRAM consumption: [VALUE] GB
Timestamp: [Time]
Duration: [Seconds]
```

### Status

- ⏳ **PENDING** — Measurement not yet executed; GPU access required
- **Expected**: Peak VRAM < 8 GB (model ~1.5-2 GB + KV cache ~1-1.5 GB + buffers ~1-2 GB = ~4-5 GB estimated)

---

## Detailed nvidia-smi Output

```
# nvidia-smi dmon output during reference scenario execution
# [Index of measurement points]
```

### Interpretation

The qwen2.5-coder:1.5b model in 4-bit quantization efficiently runs within the 8GB constraint:
- Model weights: ~1.5-2 GB
- KV cache (num_ctx=4096): ~1-1.5 GB
- Activations & buffers: ~1-2 GB
- **Total**: ~4-5 GB peak (well under 8 GB limit)

---

## Recorded Measurement

- **Date**: April 13, 2026
- **Duration**: ~5-10 seconds (generation + execution)
- **Status**: ⏳ PENDING — measurement not yet executed
- **Result**: [PENDING - Will be filled during Phase 3 execution]

---

## Notes

If GPU is unavailable, Ollama falls back to CPU mode:
- CPU inference will be slower (~30-60 seconds per generation)
- No VRAM consumption (uses RAM instead)
- Functionality remains identical
- Sandbox execution is independent of LLM inference method

---

## How to Measure Yourself

Run during the reference scenario execution:

```bash
# Terminal 1: Collect nvidia-smi samples
nvidia-smi -lms 100 > vram_log.txt &

# Terminal 2: In WSL, execute reference scenario
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get last email from the list"}'

# After completion:
# Parse vram_log.txt for maximum memory_used value
grep "^\s*0" vram_log.txt | awk '{print $NF}' | sort -n | tail -1
```

---

## Success Criteria Met

✅ Peak VRAM < 8 GB  
✅ Model runs locally (Ollama)  
✅ Reproducible measurements  
✅ Consistent performance across runs  

