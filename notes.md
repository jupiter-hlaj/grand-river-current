# notes

This project started as a way to just poke around the GRT GTFS Realtime feed and ended up turning into something more real than I expected. That's mostly a good thing, but it also means some of the early decisions got baked in before I really thought through what this was supposed to be.

## what this was actually supposed to be

The original idea was two things running together: a useful transit tracker (stop data, live bus positions, arrivals) and a gamification layer on top of the transit system. Things like king of the stop, most km ridden, streak riding, that kind of thing. The goal was to give someone waiting at a stop something to actually engage with beyond just staring at an ETA. The stop data is immediately useful, the game layer keeps them coming back.

That second part never got built, and a lot of the architectural confusion in the current codebase traces back to that. The system was half-designed for a product that doesn't exist yet.

## the dynamodb situation

DynamoDB ended up being used as a catch-all for everything — live bus positions, static GTFS data (stops, trips, routes, schedules), and historical snapshots. The thinking at the time was that batch_get_item let you pull all these different things together in one shot, which seemed efficient. It kind of is, but it's also using a database to solve a problem that isn't really a database problem.

The static GTFS data almost never changes. Storing it in DynamoDB means paying for reads every time a user hits the API, when it could just live in S3 or even be bundled into the Lambda itself. The live bus data (BUS_ALL) is basically a cache — one record that gets overwritten constantly — which is a weird thing to put in a database. And the historical snapshots use a flat PK-per-record pattern (BUS_HISTORY#{timestamp}) which makes time-range queries basically impossible without a full table scan.

So it's doing three jobs and not doing any of them particularly well.

## what should have happened

Enrich the data once at ingest, not at read time. The reader Lambda does a lot of work per request — fetching trip details, joining with stop data, calculating arrivals — and it does all of that for every user who hits the API. If the ingest Lambda had written fully-enriched bus positions from the start, the reader Lambda wouldn't need to exist. Just serve a file from S3 through CloudFront.

For historical data, S3 with time-partitioned files (hourly rollups) would have been the right call. Fast to write, cheap to store, easy to fetch a slice of time for replay. And if you actually need to run arbitrary queries across history, Athena can sit on top of S3 without needing to load anything into a database.

DynamoDB is actually the right tool — just for the wrong layer. User profiles, check-ins, leaderboards, ride history — that's where it belongs. Key-value access patterns, high read throughput, that's DynamoDB's home turf.

## the historical data and why it matters

The historical bus positions aren't just for replay or analysis — they're the verification layer for the gamification. If someone claims they rode route 7 for 12km, you need to be able to cross-reference their location with where that bus actually was. Without the historical record, the game mechanics are self-reported and trivially exploitable. With it, you can actually validate rides and award things honestly.

That's why the 30-second snapshot cadence matters. It's not just about display fidelity, it's about having enough resolution to reconstruct what happened on a given trip.

## the architecture that actually makes sense

Two layers sharing one pipeline:

Transit layer — live bus positions in S3 (one overwritten file), enriched at ingest, served via CloudFront. Historical positions in time-partitioned S3 files. Static GTFS data loaded into Lambda memory or stored in S3, not in a database.

Gamification layer — DynamoDB for user data, check-ins, leaderboards. Uses the historical bus positions from S3/Athena for ride verification. EventBridge or Lambda triggers to process completed rides and update scores.

The ingest Lambda feeds both. Everything else is either a file serve or a DynamoDB lookup. Simple.

## current state

What exists right now works as a live tracker and is mostly fine for that. The historical data is being stored but can't really be queried in any useful way with the current schema. The gamification layer doesn't exist. If this stays a personal tracker it's fine as-is. If it becomes something for actual users the whole thing should probably be rebuilt with this in mind from the start rather than patched.
