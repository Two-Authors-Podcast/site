# Weekly transcript workflow

Episodes are always identified by season and episode number, never by air date or by the order the files arrive.
The key is `s<season>e<episode>` with no leading zeros, for example `s4e44`. Riverside and Podbean file names such as
`2APS04E44` carry the same numbers.

## Nick's steps

1. When the producer sends the finished MP3, import it into Riverside and download the SRT transcript.
2. Upload the SRT and the show notes to the Podcast Interviews project in Claude.
3. Download the corrected SRT that Claude returns, named `2APS04E44-corrected.srt`.
4. When the producer has uploaded the episode to Podbean, open it, click "Episode Transcripts", upload the corrected SRT, click "Save", then click "Update".

## Claude's steps

1. Confirm the season and episode number from the SRT file name and the show notes. Stop and ask if they disagree.
2. Run `python3 tools/fix_srt.py INPUT.srt 2APS04E44-corrected.srt`, then read the whole result for errors the glossary does not cover.
3. Add any new names or terms to `tools/glossary.json`.
4. Write the readable transcript to `transcripts/s4e44.txt`, and the guest's speaker label and biography to `transcripts/s4e44.json`.
5. Commit and push. The site shows the transcript as soon as the episode appears in the Podbean feed.

## Why there are no timing conflicts

- The site only builds pages for episodes that are live in the Podbean feed, so a transcript added weeks early waits unseen until its episode airs.
- Transcripts are matched by season and episode number, so episodes prepared out of order cannot be mixed up.
- If Podbean is missing the episode number, the build reads it from the audio file name (for example `2APS04E44.mp3`).
- The build log lists transcripts still waiting for their episode, and warns if an episode number appears twice in the feed.
- The site rebuilds every 15 minutes.
