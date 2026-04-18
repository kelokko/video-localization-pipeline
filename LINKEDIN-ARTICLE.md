# I Localized 26 Videos for €15. The Agency Quote Was €15,000.

*Here's what I learned about AI, frustration, and accidentally reinventing academic research.*

---

When we launched Medikro Academy, we made a deliberate choice: **videos in English only.**

It was a pilot. We needed to test product-market fit before investing in full localization. The lesson texts? Easy — Weglot handled those. But video production? That's a different beast.

The pilot was a success. Users loved the content. But feedback from Finland, Sweden, and Spain was consistent: **"the videos are harder to follow than the rest of the content."**

Fair. Not everyone wants to learn spirometry techniques in their second language.

For commercial launch, we needed localized videos. The agency quote came back: **€4-5k per language. 2-3 months timeline. €15k total.**

The budget reality: nowhere close.

So I did what any reasonable person would do. I said "challenge accepted" and built it myself.

---

## The Impossible Triangle

You know the old saying: fast, cheap, good — pick two.

I needed all three. Plus:

- Medical terminology had to be *exact* (not "close enough")
- Audio had to sync with video timing
- The narrator's voice had to sound consistent
- Non-technical colleagues needed to review translations

Spoiler: it worked. But not on the first try.

---

## The Part Where I Got Frustrated

My first approach was obvious: use AI to translate, then generate speech.

Simple, right?

**Attempt 1:** DeepL for translation. Great quality, but Finnish translations came out longer than English. When you're dubbing video, "longer" means audio doesn't sync. No way to control output length.

**Attempt 2:** Claude with length constraints in the prompt. "Translate this, but keep it under 50 characters, and use these medical terms exactly."

The translations were... awkward. Forced. Like someone trying to explain quantum physics in exactly 280 characters.

I was asking the AI to juggle too many balls at once.

---

## The Breakthrough (Born from Frustration)

At some point I stopped trying to be clever and just simplified:

**Pass 1:** Let the AI translate naturally. No length constraints. Just accuracy and terminology.

**Pass 2:** A separate script checks which phrases are too long, then asks the AI to shorten *only those*.

It worked beautifully.

The first pass produced natural, accurate translations. The second pass only touched ~15% of segments — surgical fixes without messing up everything else.

---

## Then I Googled It

Turns out this is called the **"generate-then-edit paradigm"** — a well-studied principle in NLP research.

Academic papers explain that forcing constraints during generation "may hurt the expressiveness of the model and lead to potential performance degradation, impacting the fluency and naturalness of the output."

I reinvented it by accident when I got frustrated enough to try something different.

Which I think says something about why the pattern exists in the first place.

---

## The Results

**AI Pipeline:**

- Development time: 1 day
- Processing 26 videos: ~30 minutes
- Cost per language: ~€15
- Change requests: 5 minutes

**Agency Quote:**

- Cost per language: €4-5k
- Timeline: 3-4 months (for 3 languages)
- Change requests: 2 weeks + fees

I showed a few example videos to colleagues. The response? "YESSS LET'S DO IT!"

---

## What I Actually Learned

**1. AI tools are building blocks, not solutions.**

No single API solved this. The value came from stitching together transcription, translation, voice cloning, and audio processing — with custom logic handling the gaps between them.

**2. "AI translation is too bad for specialized content" — solved problem.**

Glossaries exist. Feed the AI your terminology, it uses your language. Don't have a glossary? Use existing localized content to auto-generate one. Claude extracted ~400 medical term pairs from our website in minutes.

**3. Design for inevitable revisions.**

Save outputs per-segment, not per-video. When QA edits a translation, the sync script auto-deletes that segment's audio. Re-run = only changed segments regenerate. Fixing one word = one API call, not a full video.

**4. Human-in-the-loop means designing for non-technical reviewers.**

I built a Google Sheets interface so colleagues could review translations without touching JSON files. Character counts auto-update. Cells turn red when edits break the length constraints. Edits sync back to the pipeline automatically.

The experts stay in their comfort zone (spreadsheets), the code stays in mine.

---

## The Bigger Picture

This project wasn't about replacing agencies or humans. It was about **making certain projects possible** that wouldn't have happened otherwise.

At €15k, the localization would have been deprioritized indefinitely. At €45, it shipped.

That's the real ROI of learning to build with AI tools — not doing things cheaper, but **doing things that wouldn't have been done at all.**

---

*What's a project you've automated that seemed impossible at first? I'd love to hear about it in the comments.*

---

**Tech stack for the curious:** ElevenLabs (transcription + voice cloning + TTS), Amazon Bedrock/Claude (translation), FFmpeg (audio processing), Google Sheets API (QA workflow), Python.

*Full technical case study with code examples: [link to GitHub repo]*