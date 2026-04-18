# Case Study: AI-Powered Video Localization Pipeline

## Building an Automated Dubbing System for Medical E-Learning Content

**Project Duration:** 2 weeks (development) | **Cost:** ~€15 per language in API fees  
**Client:** Medikro Oy (Medical Device Manufacturer)  
**Role:** Full-stack implementation – strategy, development, deployment

---

## The Challenge

Medikro Academy, an e-learning platform for medical device training, was launched in pilot phase with videos in English and textual lesson materials localized to Finnish, Swedish, and Spanish — balancing investment with localization level for market fit testing.

The pilot proved a total success across all markets. However, users consistently highlighted that **English-language videos were harder to follow** than content in their local languages. Localizing the videos was identified as a clear value-increasing / friction-removing action for successful commercial launch.

**Content scope:** 26 instructional videos (~1 hour total, ~5,000 words) featuring a single narrator.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Re-record with original trainer** | Authentic voice | Only possible for Finnish (not Swedish/Spanish); high risk of deviating from script causing post-production sync issues |
| **In-house production** (transcribe, translate, hire voice actors, edit) | Full control | No translation resources = unpredictable timing & quality; no video editing expertise; commissioning voice acting felt risky |
| **Agency end-to-end** | Professional quality | €4-5k per language, €9.5-15.5k for all three; 2-3 months timeline; way over budget |

### Key Constraints

- **Terminology:** Medical terms must be precise across languages and consistent with Medikro's existing documentation
- **Timing:** Audio must sync with video despite different phrase lengths across languages — many videos have screencasts where commentary must closely follow the visuals
- **Voice consistency:** Same narrator voice across all videos within a language; ideally recognizable across languages
- **Resources:** Manual work must be minimized to fit limited in-house time and skills
- **Quality bar:** Professional enough for paid professional training material

**Budget reality:** Make it fast, cheap, and high quality. (Pick three? Challenge accepted.)

---

## The Solution

I designed an **AI-powered workflow** that streamlined the process end-to-end, minimizing manual operations while maintaining precise control at each step to ensure quality targets. The workflow is fully reusable across projects and languages, and naturally includes a "human-in-the-loop" stage without needing to forward files between stakeholders and developer.

### Step 1: Building the Terminology Glossary

The Academy already had textual lesson content translated and validated by internal experts — covering vocabulary from the videos quite comprehensively.

**Process:**
1. Scraped full text content from Academy website in English + 3 target languages
2. Claude (via Cursor) analyzed the content and built JSON files with term pairs for all medical terminology found
3. Result: ~400 terms per language in structured thesaurus format

```json
{
  "flow transducer": "virtausanturi",
  "calibration check": "kalibroinnin tarkistus",
  "bacterial filter": "bakteerifiltteri"
}
```

### Step 2: Extract Source Audio

Downloaded all videos from Academy hosting via SSH, then used Python/FFmpeg to extract audio tracks.

### Step 3: Transcription with Timestamps

Experimented with local and cloud speech-to-text services. **ElevenLabs Speech-to-Text** provided the best results:
- Precise word detection
- Automatic filler word removal
- Word-level timestamps for future revoicing
- Sentence boundary detection

A Python script batch-transcribed all 26 audios in under 10 minutes.

### Step 4: Thesaurus-Aware Translation

Initial attempt with DeepL API revealed a critical issue: **same phrases have very different lengths across languages**. Simple translation wasn't enough — I needed a service that could edit translations to maintain similar phrase lengths.

**Solution:** Claude Sonnet via Amazon Bedrock, with a custom prompt that:
- Respected the medical thesaurus exactly
- Adjusted phrase lengths to match original timing
- Maintained natural Finnish phrasing

After fine-tuning the prompt on one video, batch-translated all transcripts.

### Step 5: Voice Cloning & TTS Generation

**Voice Cloning:** Uploaded English audio to ElevenLabs, which analyzed and created a voice profile mimicking the original narrator.

**TTS Generation:** Called ElevenLabs Text-to-Speech API using:
- Cloned voice ID
- Translated JSON segments as source
- Optimized parameters for natural speech (discovered through experimentation: 0.9x speed + context parameters + period endings = best quality)

**Result:** Generated audio was eerily similar to the original narrator — colleagues couldn't tell the difference.

### Step 6: Audio-Video Synchronization

Initial approach (replacing audio as single track) produced disappointing sync — translated text skipped all pauses and filler words present in English.

**Solution:** Use original transcript timestamps to:
1. Chop generated audio into segments
2. Place each segment at its corresponding timestamp
3. Mix with FFmpeg

Result: ~90% accurate sync from automated pipeline. Remaining 10% tuned manually in video editor — incomparably faster than manual sync from scratch.

### Step 7: QA Workflow for Non-Technical Reviewers

I'm not a native Finnish speaker, so translations needed expert review. Requirements:
- Easy for colleagues to review and edit (not JSON files)
- Prevent edits from breaking carefully calibrated phrase lengths
- Avoid manual copy-paste from Office docs back to JSON

**Solution:** Google Sheets integration that:
- Populates sheet from JSON (English source + Finnish translation)
- Shows character counts per phrase
- Highlights cells red when translations exceed ±10-20% of target length
- Syncs edits back to JSON and regenerates only affected audio segments

### Step 8: Deployment

Localized videos uploaded to web hosting, with links stored for frontend integration.

---

## Technical Architecture

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
│               │   (~400 terms)   │                              │
│               └─────────────────┘                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Transcription | ElevenLabs Speech-to-Text | Word-level timestamps for precise segmentation |
| Translation | Amazon Bedrock (Claude) | Thesaurus-aware, length-controlled translation |
| Voice Cloning | ElevenLabs Instant Voice Clone | Preserve narrator's voice identity |
| Text-to-Speech | ElevenLabs Multilingual v2 | Natural pronunciation in target language |
| Audio Processing | FFmpeg | Tempo adjustment, mixing, synchronization |
| QA Interface | Google Sheets API | Collaborative review with length constraints |
| Development | Cursor IDE + Claude | AI pair-programming for Python scripts |

---

## Results

### Cost Comparison (Verified)

| Approach | Finnish | All 3 Languages | Timeline |
|----------|---------|-----------------|----------|
| **AI Pipeline** | ~€15 | ~€45 | 4-6 weeks |
| **Agency Quote** | €4-5k | €9.5-15.5k | 3-4 months* |

*Agency timeline assumes smooth execution. Real-world projects typically add 2-3 weeks per language for internal review cycles, stakeholder feedback, and change requests.

**Finnish cost breakdown (verified from API billing):**
- ElevenLabs Creator subscription (50% first-month discount): €11
- Speech-to-Text overage (22.8 min beyond included 30 min): €2
- AWS Bedrock translation API: €0.50
- **Total: ~€13.50**

### Why AI Pipeline is Faster in Practice

| Scenario | Agency | AI Pipeline |
|----------|--------|-------------|
| "Can we change this word?" | Email → quote → re-record → 2 weeks | Regenerate → 5 minutes |
| QA feedback on 50 segments | Send spreadsheet → wait for batch re-record | Edit in Google Sheets → auto-regenerate affected segments |
| Stakeholder changes mind | Change request fee + scheduling | Just run the script again |

### Quality Outcomes

- **Voice quality:** Colleagues confirmed the cloned voice sounds like the original narrator
- **Sync quality:** 90% automated sync accuracy; remaining 10% quick manual adjustment
- **Terminology:** 100% consistent with existing Medikro documentation (thanks to thesaurus)
- **Stakeholder reaction:** Demo approved for full production rollout

---

## Skills Demonstrated

### AI-Assisted Development
- Directed Claude (Cursor IDE) to build Python scripts, debug issues, iterate on solutions
- Prompt engineering for translation quality and length control
- Tool selection based on cost/quality tradeoffs (ElevenLabs vs alternatives, Bedrock vs OpenAI)

### Technical Execution
- System architecture design and data flow orchestration
- API integration (ElevenLabs, AWS Bedrock, Google Sheets)
- Audio/video processing with FFmpeg
- Server management (SSH, deployment)

### Domain & Business
- Medical terminology management across 4 languages
- QA workflow design for non-technical collaborators
- Cost/benefit analysis and stakeholder communication
- Demo-first validation approach

---

## Lessons Learned

1. **AI tools are building blocks, not solutions** — The value came from orchestrating multiple services with custom logic, not from any single API.

2. **Domain expertise is essential** — Generic translation failed for medical content. The thesaurus built from existing validated content was crucial.

3. **Design for iteration** — Caching audio segments meant regenerating specific phrases without re-calling expensive APIs for the entire video.

4. **Human-in-the-loop, not human-out-of-loop** — The Google Sheets QA interface let domain experts contribute without touching code or JSON files.

5. **Demo first, perfect later** — Getting stakeholder buy-in on 3 videos before processing all 26 saved potential rework.

---

## Links

- **Finnish Demo Course:** https://academy.medikro.com/fi/courses/demo-spirometry-fundamentals/
- **Swedish Demo Course:** https://academy.medikro.com/sv/courses/demo-spirometry-fundamentals/

---

*Case study prepared by Mila | April 2026*
