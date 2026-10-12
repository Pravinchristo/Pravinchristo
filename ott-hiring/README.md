# OTT Test Engineer sourcing

Daily active sourcing for an **OTT Test Engineer with analytics tools**.

| Criterion | Target |
|---|---|
| Domain | OTT / video streaming app testing (playback, DRM, ABR, ads, Smart TV and devices) |
| Analytics tools | Conviva, Mixpanel, Adobe Analytics / Heartbeat, CleverTap, Firebase, GA4, Kochava, AppsFlyer, Braze, mParticle, New Relic, Mux, Charles Proxy for event checks |
| Experience | 2 to 6 years |
| Availability | Open to work or immediate joiner preferred (not required) |
| Location | India |

Results go to the **OTT Hiring** dashboard: https://claude.ai/artifact/2ZaumQD3mmBZzqbJzUng2q
Candidate data lives only in that private dashboard, never in this repo.

## Search strings

LinkedIn / X-ray (Google: prefix with `site:linkedin.com/in`):

```
("OTT" OR "video streaming" OR "media streaming") AND ("test engineer" OR "QA engineer" OR "software tester" OR "quality analyst")
AND ("Conviva" OR "Mixpanel" OR "Adobe Analytics" OR "CleverTap" OR "Firebase" OR "Charles Proxy" OR "analytics validation" OR "analytics testing")
AND ("open to work" OR "immediate joiner" OR "serving notice")
AND (India OR Bengaluru OR Bangalore OR Chennai OR Hyderabad OR Pune OR Mumbai OR Noida OR Gurugram)
```

Device variant:

```
("Roku" OR "Fire TV" OR "Android TV" OR "Tizen" OR "webOS" OR "Apple TV") AND ("QA" OR "tester") AND ("analytics" OR "Conviva" OR "Charles Proxy") AND India
```

Rotate the daily search across: analytics tool names, device platforms, OTT brands
(JioHotstar, ZEE5, SonyLIV, Sun NXT, DAZN, Amagi, Quickplay, Diagnal, Ovyo, GlobalLogic, Tata Elxsi, LTTS)
and availability phrases ("immediate joiner", "open to work", "serving notice", "available to join").

## Fit score (0-100)

- OTT or video streaming testing: 30 (10 for an adjacent domain)
- Analytics tools named: 10 each, up to 30
- Experience in 2-6 years: 20 (10 when not stated, 0 outside)
- Open to work or immediate joiner on profile: 20

Hot is 75 or more, Warm 55-74, Nurture below 55. See `score_and_merge.py`.

## Daily run

1. Run 3-4 people searches using the strings above, rotating the variant each day.
2. Keep profiles in India with OTT/streaming QA and 2-6 years (or unstated). Skip leads, managers and 7+ years.
3. Write them as a JSON array of records:
   `name, profile_url, headline, company, city, exp_years (number or null), availability ("Open to work" | "Immediate joiner" | "Not stated"), analytics_tools [..], platforms [..], ott_domain (bool, default true), notes`.
   Record only what the profile says; never guess experience or availability.
4. Download the dashboard's current candidates file, then:
   `python3 score_and_merge.py current.json new.json merged.json --run-date YYYY-MM-DD`
5. Upload `merged.json` and the updated runs file to the dashboard and point its two sources at them.
