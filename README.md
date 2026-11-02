# twoauthorspodcast.com

The website for The Two Authors' Podcast, built automatically from the Podbean feed.

## How it works

- Every hour, GitHub runs `build.py`, which reads the Podbean RSS feed and makes a page for every episode. A new episode appears on the site within an hour of going live on Podbean, with nobody doing anything.
- A corrected transcript is added to an episode page by putting a file named `transcripts/s<season>e<episode>.txt` in this repository, for example `transcripts/s4e43.txt`. An optional `transcripts/s4e43.json` holds the guest biography and the guest's speaker label.
- Transcript files use `## Heading` for each topic and `NAME: what they said` for each speaker turn.

## Building it on your own computer

    python3 build.py

The finished site is written to the `_site` folder.
