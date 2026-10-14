# OTT and QA engineer sourcing

Daily active sourcing in two tracks:

- **OTT track:** OTT Test Engineer with analytics tools.
- **Kafka / DB / API track:** non-OTT QA engineer with Kafka testing, database testing and API testing with Postman.

Both tracks put immediate joiners and people open to work first.

### OTT track

| Criterion | Target |
|---|---|
| Domain | OTT / video streaming app testing (playback, DRM, ABR, ads, Smart TV and devices) |
| Analytics tools | Conviva, Mixpanel, Adobe Analytics / Heartbeat, CleverTap, Firebase, GA4, Kochava, AppsFlyer, Braze, mParticle, New Relic, Mux, Charles Proxy for event checks |
| Experience | 2 to 6 years |
| Availability | Open to work or immediate joiner preferred (not required) |
| Location | India |

### Kafka / DB / API track

| Criterion | Target |
|---|---|
| Kafka | Topic / producer-consumer / event validation |
| Database testing | SQL, MySQL, PostgreSQL, Oracle, MongoDB validation |
| API testing | REST APIs with Postman (Rest Assured is a plus) |
| Experience | 2 to 6 years |
| Availability | Immediate joiner, open to work or serving notice |
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

Kafka / DB / API track:

```
("QA engineer" OR "test engineer" OR "SDET") AND "Kafka" AND ("database testing" OR SQL OR PostgreSQL OR MongoDB)
AND (Postman OR "API testing") AND ("immediate joiner" OR "open to work" OR "serving notice") AND India
```

Rotate the daily OTT search across: analytics tool names, device platforms, OTT brands
(JioHotstar, ZEE5, SonyLIV, Sun NXT, DAZN, Amagi, Quickplay, Diagnal, Ovyo, GlobalLogic, Tata Elxsi, LTTS)
and availability phrases ("immediate joiner", "open to work", "serving notice", "available to join").

## Fit score (0-100)

- OTT track: OTT or video streaming testing 30 (10 for an adjacent domain); analytics tools named, 10 each up to 30
- Kafka / DB / API track: Kafka 30, database testing 15, Postman / REST API testing 15
- Both: experience in 2-6 years 20 (10 when not stated, 0 outside)
- Both: immediate joiner or open to work on profile 20, serving notice 10

Hot is 75 or more, Warm 55-74, Nurture below 55. See `score_and_merge.py`.

## Daily run

1. Run 3-4 people searches per track using the strings above, rotating the variant each day.
2. Keep India profiles with 2-6 years (or unstated) that fit a track. Skip leads, managers and 9+ years; 7-8 years only with an immediate or open-to-work signal, noted as above the band.
3. Write them as a JSON array of records:
   `track ("OTT" | "Kafka / DB / API"), name, profile_url, headline, company, city, exp_years (number or null), availability ("Immediate joiner" | "Open to work" | "Serving notice" | "Not stated"), analytics_tools [..], skills [any of "Kafka", "DB testing", "Postman API"], platforms [..], ott_domain (bool, default true), notes`.
   Record only what the profile says; never guess experience or availability.
4. Download the dashboard's current candidates file, then:
   `python3 score_and_merge.py current.json new.json merged.json --run-date YYYY-MM-DD`
5. Upload `merged.json` and the updated runs file to the dashboard and point its two sources at them.
