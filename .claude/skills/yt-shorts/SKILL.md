---
name: yt-shorts
description: >-
  Find the Shorts hiding inside a long video and write them, using the
  transcript to pick self-contained moments. Use for "cut this into shorts",
  "clip this", "repurpose this video", "what should I clip".
---

# yt-shorts

A Short cut out of a long video is not a clip of the best moment. It is a moment that **survives
without the video around it**, which is a much smaller set.

## Picking

Read the transcript and find spans of 20-55 seconds where all three are true:

1. It opens on a complete thought. If the first sentence needs the previous minute, it is not a Short.
2. There is a turn in it - a claim, then something that complicates or proves it.
3. It ends on a line, not a trail-off.

Rank the candidates and show the user the top five with their timecodes and first line, so they can
reject one without reading the whole transcript.

## Writing each one

- **A NEW first line.** The long video's line assumes context this viewer does not have. Write the
  replacement and run it through `../yt-script/hookscore.py`.
- **On-screen text for the first two seconds**, different words from the spoken line.
- **A loop point**: what the last line sets up so the first line answers it.
- Vertical framing note - what gets cropped out of a 16:9 frame and whether that matters.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**

## This account (added locally)

- Write everything the user reads in Korean. The Python tools in this pack score Korean text as
  well as English; the Korean rules were added in this repository (see `.claude/third-party/NOTICE`)
  and are uncalibrated heuristics.
- Transcripts: the usual input here is a transcript pasted from YouTube (a `0:00` line, then the
  words) or an .srt/.vtt file. There is no speech recognition in this environment.
- Rendering: the spans can be turned into vertical videos in the shorts factory page
  (`shorts/index.html`): load the video file, paste the same transcript, add each span with its
  start and end, and use the new first line as the title.
