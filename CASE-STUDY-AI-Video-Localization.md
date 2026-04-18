# Case Study: AI-Powered Video Localization Pipeline

## Building an Automated Dubbing System for Medical E-Learning Content

**Project Duration:** 2 weeks (development) | **Cost:** ~€50 in API fees  
**Client:** Medikro Oy (Medical Device Manufacturer)  
**Role:** Full-stack implementation – strategy, development, deployment

---

## The Challenge

Medikro Academy, an e-learning platform for medical professionals, received user feedback requesting Finnish-language videos. The course contained **30 instructional videos** featuring a single narrator (Esko), originally in English.

**Initial options seemed impractical:**
- Re-recording with Esko: Weeks of studio time + editing
- Professional dubbing service: €5,000-15,000 estimated
- Manual AI dubbing (ElevenLabs Dubbing Studio): Fast but poor sync, no terminology control

**Key constraints:**
- Medical terminology must be precise and consistent
- Audio must sync with existing video footage (lip-sync not required, but timing matters)
- Narrator's voice should remain recognizable
- Budget: Minimal
- Quality bar: Professional enough for medical professionals

---

## The Solution

I designed and built an **end-to-end automated pipeline** combining multiple AI services with custom orchestration logic:

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO LOCALIZATION PIPELINE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  VIDEO   │───▶│  AUDIO   │───▶│TRANSCRIBE│───▶│ SEGMENT  │  │
│  │  INPUT   │    │ EXTRACT  │    │ (11Labs) │    │ BY TIMING│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │        │
│                                                        ▼        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  VIDEO   │◀───│  AUDIO   │◀───│GENERATE  │◀───│TRANSLATE │  │
│  │  OUTPUT  │    │   MIX    │    │TTS+CLONE │    │ (Bedrock)│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │        │
│                        ┌───────────────────────────────┘        │
│                        ▼                                        │
│               ┌─────────────────┐                               │
│               │ MEDICAL THESAURUS│                              │
│               │   (374 terms)    │                              │
│               └─────────────────┘                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Transcription | ElevenLabs Speech-to-Text | Word-level timestamps for precise segmentation |
| Translation | Amazon Bedrock (Claude) | Cost-effective, thesaurus-aware translation |
| Voice Cloning | ElevenLabs Instant Voice Clone | Preserve narrator's voice identity |
| Text-to-Speech | ElevenLabs Multilingual v2 | Natural Finnish pronunciation |
| Audio Processing | FFmpeg | Tempo adjustment, mixing, synchronization |
| QA Interface | Google Sheets API + gspread | Collaborative review with character limits |
| Deployment | SSH/SCP to WordPress hosting | Direct upload to production |

---

## Key Technical Challenges & Solutions

### 1. Timing Synchronization

**Problem:** Generated Finnish audio often didn't match the original segment duration – sometimes too long (overlap with next segment), sometimes too short (awkward silence).

**Solution:** Implemented adaptive speed control:
- Hybrid approach: First segment at 0.9x speed (fills gaps), rest at 1.0x
- Per-segment speed adjustment using FFmpeg's `atempo` filter
- Real-time duration calculation to identify overflow/underflow

```python
# Adaptive speed: if audio is 10s but slot is only 8s
speed_factor = current_duration / target_duration  # 1.25x
subprocess.run(['ffmpeg', '-i', input, '-filter:a', f'atempo={speed_factor}', output])
```

### 2. Medical Terminology Consistency

**Problem:** Generic AI translation produced inconsistent medical terms (e.g., "flow transducer" translated differently each time).

**Solution:** Built a 374-term English-Finnish medical thesaurus and injected it into the translation prompt:

```json
{
  "flow transducer": "virtausanturi",
  "calibration check": "kalibroinnin tarkistus",
  "bacterial filter": "bakteerifiltteri",
  "spirometry": "spirometria"
}
```

The translator was instructed to use exact thesaurus matches and maintain terminology consistency across all segments.

### 3. Natural Speech Flow

**Problem:** Segment-by-segment TTS sounded choppy – each segment started/ended abruptly.

**Solution:** Leveraged ElevenLabs' context parameters:
- `previous_text`: Provides preceding segment for natural continuation
- `next_text`: Signals upcoming content for appropriate intonation
- Forced sentence-ending punctuation to prevent mid-thought cutoffs

### 4. QA Workflow for Non-Technical Reviewer

**Problem:** The narrator (Esko) needed to review 366 translated segments but isn't technical.

**Solution:** Built a Google Sheets integration:
- Auto-populated sheet with English source, Finnish translation, timing constraints
- Character counter formula: `=LEN(cell)`
- Conditional formatting: Red if translation exceeds character limit
- Two-way sync: Pull edits back to JSON files for regeneration

---

## Results

### Quantitative

| Metric | Value |
|--------|-------|
| Videos processed | 3 demo + pipeline ready for 30 |
| Total API cost | ~€50 |
| Development time | ~2 weeks |
| Translation accuracy | 95%+ (after thesaurus implementation) |
| Time saved vs manual dubbing | Estimated 80-90% |

### Qualitative

- **Voice quality:** Recognizably "Esko" – colleagues confirmed it sounds like him
- **Sync quality:** Professional-grade timing with minimal manual adjustment
- **Scalability:** Pipeline is reusable for Swedish, Spanish, or other languages
- **Stakeholder reaction:** Demo approved for full production rollout

---

## Skills Demonstrated

### AI-Assisted Development
- **AI pair programming** – Directed Claude (Cursor IDE) to build custom Python scripts, debug issues, and iterate on solutions
- **Prompt engineering** – Guided AI through complex multi-step technical tasks with clear requirements
- **Quality control** – Tested outputs, identified issues, directed refinements until results met standards
- **Tool selection** – Chose appropriate AI services (ElevenLabs vs alternatives, Bedrock vs OpenAI) based on cost/quality tradeoffs

### Technical Understanding
- **System architecture** – Designed the overall pipeline and data flow
- **Audio/Video editing** – Final polish in Adobe Premiere Pro (music, timing adjustments)
- **API concepts** – Understood rate limits, costs, authentication flows
- **Server management** – SSH/SCP deployment to WordPress hosting

### Domain Expertise
- **Medical terminology** – Built 374-term thesaurus by analyzing existing Finnish course materials
- **Linguistic QA** – Identified translation errors, awkward phrasing, and timing issues
- **User perspective** – Evaluated output quality from end-user standpoint

### Problem-Solving
- Breaking down a "too expensive" problem into automatable components
- Identifying where AI works well vs. where human review is essential
- Iterative refinement – "this sounds robotic" → adjust speed → "now there's overlap" → adjust timing
- Knowing when to stop optimizing and ship (demo-first mindset)

### Project Management
- Demo-first validation before full commitment
- Clear effort/cost estimates for stakeholder decisions
- Documentation for handoff and future maintenance

### Communication
- Translating technical capabilities into business value
- Creating review interfaces for non-technical collaborators
- Writing clear proposals with ROI justification

---

## Lessons Learned

1. **AI tools are building blocks, not solutions** – The magic wasn't in any single API but in orchestrating them together with custom logic.

2. **Domain expertise matters** – Generic translation failed for medical content. The thesaurus was essential.

3. **Perfect is the enemy of shipped** – Early demos with 80% quality got stakeholder buy-in faster than waiting for 100%.

4. **Build for iteration** – Caching audio segments meant I could remix videos without re-calling expensive APIs.

---

## Links

- **Finnish Demo Course:** https://academy.medikro.com/fi/courses/demo-spirometry-fundamentals/
- **Swedish Demo Course:** https://academy.medikro.com/sv/courses/demo-spirometry-fundamentals/

---

*Case study prepared by Mila | March 2026*
