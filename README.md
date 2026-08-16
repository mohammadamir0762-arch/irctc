# PNR Confirmation Predictor (PS91)

Predicts the probability a waitlisted/RAC Indian Railways ticket confirms by
chart preparation, given train/quota/class/waitlist-position style features.

## Status

- **Model**: trained on **real** waitlist outcomes — 28,748 real waitlisted
  tickets (39,724 observations) from the Kaggle *Railway Waitinglist
  Dataset*. Test **AUC 0.796**, Brier 0.0447, grouped train/test split so
  observations of the same ticket never straddle the split. `GET /model`
  returns these numbers live.
- **Inputs** are only what real data supports and the PNR lookup actually
  provides: travel class, waitlist position at booking, current waitlist
  position, days until journey. No estimated or invented features.
- **Primary flow**: enter a 10-digit PNR (`GET /pnr/{pnr_number}`) — the
  backend looks up the ticket and predicts from it.
- **Live provider**: wired to `irctc1` via RapidAPI and verified against a
  real response. Falls back to mock data when no key is set.
- **Data flywheel**: every check is logged to `backend/data/pnr_log.sqlite3`;
  `python -m app.poll_outcomes` captures real outcomes after the journey.

### On the datasets

Three Kaggle datasets were evaluated. Only one is usable:

| Dataset | Verdict |
|---|---|
| Railway Waitinglist Data | **Real and used.** Class mix matches reality, irregular missing data, confirmation rate falls cleanly with waitlist position (32.7% at WL 1-5 to 1.6% at WL 120+). |
| Railway Ticket Confirmation | **Fake — discarded.** Sequential PNRs, 30,000 unique journey dates for 30,000 rows, perfectly uniform Train Type x Class grid (Shatabdi with Sleeper class). Its label is a tautology: every row with a waitlist position is "Not Confirmed", giving AUC 1.0 and nothing to learn. |
| Railofy testing data | **Unusable.** Competition test split — no target column. |

Within the usable dataset, the `status1Day` column is **excluded**: it has
~30k rows (double the others), a 0.3% confirmation rate, and no relationship
between position and outcome (flat ~0.2-0.3% from WL 1 through WL 900).
Training on it inflated AUC to 0.874 by learning a data artifact; 0.796 is
the honest number.

The earlier synthetic model was removed. It was circular — trained on labels
produced by a hand-written formula, so it could only re-learn that formula.

## Project layout

```
backend/
  app/
    train_real.py       trains on the real Kaggle dataset
    model.py             loads model, serves predictions + "why" factors
    pnr_provider.py       fetches PNR status (indianrailapi / rapidapi / mock)
    pnr_mapper.py          maps canonical PNR response -> model features
    test_provider.py        CLI: verify a real provider key end-to-end
    storage.py              SQLite log of every check (the data flywheel)
    poll_outcomes.py         re-checks past-due PNRs to capture real outcomes
    main.py                   FastAPI app (/pnr, /predict, /options, /health)
  models/                  model.joblib + metadata.json (generated)
  data/                    pnr_log.sqlite3 (generated)
  requirements.txt
frontend/
  index.html / app.js / style.css   plain JS UI, no build step
dataset/
  Railway Ticket WaitingList Data.csv   the real training data
  Railofy_training_data_for_model.csv   benchmark only (see Validation)
analysis/
  benchmark.py                       reproduces every number in Validation
mobile/
  App.js / config.js                 Expo (React Native) app, same PNR flow
```

## Running it locally

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.train_real     # trains on dataset/ and saves the model (run once)
uvicorn app.main:app --port 8000
```

In another terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Then open http://localhost:5500. `frontend/config.js` detects it is running
on localhost and talks to the local backend; served from anywhere else it
uses the deployed API instead, so no edit is needed to switch between them.

## API

- `GET /pnr/{pnr_number}` — the main endpoint. Looks up the PNR via a
  provider (see below), maps the response into model features, and returns
  either a resolved status (`{"resolved": true, "status": "Confirmed"}`) or
  a prediction (`probability`, `confidence_label`, `top_factors`,
  `pnr_summary`, `estimated_fields`, `is_mock`).
- `GET /options` — valid travel classes (used by the "Advanced" form)
- `GET /model` — what the model is and how well it performs (source, row
  counts, test AUC/Brier), so its numbers can be judged rather than trusted.
- `POST /predict` — manual/advanced path: `{travel_class, booking_position,
  current_position, days_before_journey}` → same prediction shape.
- `GET /health`

### Confidence labels

Waitlisted tickets confirm ~5% of the time overall, and the model's 99th
percentile output is ~0.26 — so a conventional "75% = likely" cutoff would
label everything "unlikely" and convey nothing. The bands are set from the
real distribution and checked against real outcomes:

| Label | Threshold | Actually confirmed |
|---|---|---|
| Good chance | >= 0.20 | 36% |
| Some chance | >= 0.10 | 19% |
| Unlikely | >= 0.05 | 12% |
| Very unlikely | < 0.05 | under 5% |

## PNR lookup: real provider vs. mock

`backend/app/pnr_provider.py` selects a provider from environment variables:

| `PNR_PROVIDER` | Also needs | Notes |
|---|---|---|
| `mock` (default when no key) | — | Deterministic fake data; flagged `"is_mock": true` in responses and shown as a banner in both UIs |
| `indianrailapi` (default when a key is set) | `PNR_API_KEY` | indianrailapi.com's documented `PNRCheck` endpoint |
| `rapidapi` | `PNR_API_KEY`, `PNR_RAPIDAPI_HOST`, optionally `PNR_RAPIDAPI_PATH` | Generic adapter for the many IRCTC listings on RapidAPI |

Each provider normalises its own response into one canonical shape, so
`pnr_mapper.py` and everything downstream never change when you switch.

### Quota reality (important)

The `irctc1` free plan is **10 requests per MONTH**, not per day. Read from
the live response headers:

```
x-ratelimit-basic-limit: 10
x-ratelimit-basic-reset: ~31 days
```

That is why `setenv.sh` defaults to `PNR_PROVIDER=mock`. Switch to the real
provider only when deliberately spending a request. To check remaining quota
without wasting a call, read the `x-ratelimit-basic-remaining` header on any
response you already made.

This also rules out the availability-crawler idea on the free tier: even 30
polls/day would need ~900 requests/month, 90x the allowance.

### Choosing a provider

Pricing pages are login-gated/JS-rendered, so **verify quota and cost
yourself before committing**; the only verified number in this repo is the
10/month above.

What actually differs, and matters more than price at this stage:

- **indianrailapi.com** — single vendor, documented endpoint, response shape
  already matches the canonical shape. Least integration work.
- **RapidAPI listings** — several competing sellers behind one signup and
  one billing account, so you can switch sellers without a new contract if
  one degrades. Each has its own response schema, so expect to adjust the
  adapter's field mapping once (see below).

Both are *unofficial* wrappers over IRCTC's public lookup, so treat either
as a bootstrap, not a foundation: they break when IRCTC changes its pages,
and rate-limit aggressively. The durable path is IRCTC Authorised Partner
status once you have traction — that's the route ConfirmTkt and Trainman
took.

### Verifying a provider works

Once you have a key, don't guess whether the wiring is right:

```bash
cd backend && source venv/bin/activate
export PNR_API_KEY=your_key_here
export PNR_PROVIDER=indianrailapi        # or rapidapi (+ PNR_RAPIDAPI_HOST)
python -m app.test_provider 1234567890   # use a real, currently-waitlisted PNR
```

It prints the provider selected, the raw response, the normalised canonical
shape, the derived model features, and the final prediction — so if a
provider's field names differ from what the adapter expects, the raw dump
shows exactly what to change in `RapidAPIProvider._normalise()`. Adjusting
that mapping for your specific listing is expected, not a bug.

The RapidAPI adapter is verified against a **real `irctc1` response**
(`Pnr`/`TrainNo`/`Class`/`Doj`, payload nested under `data`, top-level
`Quota`), and also handles the other common spellings and several date
formats. Note that key lookups are case-sensitive, which is why every
observed spelling is listed explicitly in `_normalise()`.

Status strings differ by provider and both are handled:

| Provider | `CurrentStatus` | Quota from |
|---|---|---|
| indianrailapi | `"GNWL/-/16/GN"` (slash) | the status string |
| irctc1 / RapidAPI | `"CNF"`, `"WL 12"` (bare/spaced) | top-level `Quota` |

The parser reads a queue position **only** for WL/RAC statuses, so the
trailing numbers in a confirmed `"CNF B5 55"` are correctly treated as
coach/berth rather than a waitlist position. If a waitlisted status has no
readable position anywhere, the request is refused with a clear error
rather than scored on a guess.

Every model input is read directly from the provider response — there are no
estimated or invented features. (`estimated_fields` remains in the response
shape, always empty, from when the earlier model did rely on estimates.)

## Validation & benchmark

`python analysis/benchmark.py` reproduces every number below. No API calls,
no network, no paid services.

**The four deployed features are the determining ones.** Measured on real
tickets:

| Factor | Effect |
|---|---|
| Waitlist position (7d out) | 12.9% confirm at WL 1-5 → 0.2% at WL 60+ (**65x**) |
| Days until journey (WL 1-5) | 6.6% at 30d → 12.9% at 7d → 15.1% at 2d (**2.3x**) |
| Travel class (WL 1-15, 7d out) | 2A 5.2% → CC 33.6% (**6.5x**) |

**How much signal we capture.** Benchmarked against the Railofy Kaggle
competition dataset (36,775 labelled tickets, 23 features):

| Model | AUC |
|---|---|
| Random baseline | 0.500 |
| **Deployed model** (4 features, real data, live) | **0.799** |
| Railofy ceiling (23 features, not deployable) | 0.945 |

The deployed model captures **67% of the achievable signal above random**
using 4 features instead of 23.

**What would help most.** Permutation importance over all 23 Railofy
features ranks current waitlist position **#1 by more than 2x** over
anything else; days-to-departure is 4th, quota 5th, route distance 6th. So
the deployed model holds the single strongest predictor, and the main gap is
quota — worth a lot: General 26.3%, Pooled 44.1%, Remote Location 45.3%.

**Why the 0.945 model is not deployed.** Railofy encodes waitlist position
as a fraction (1/2, 1/3, 1/4 ...) of a denominator absent from the file, so
a real "WL 25" cannot be converted to its input scale. Quantile-mapping real
values onto its distribution and scoring against real labels gives **AUC
0.480 — worse than random**. Shipping it would look better on paper and be
worse in practice, so it stays a benchmark.

## Data flywheel

`backend/app/storage.py` logs every `/pnr/{pnr_number}` check to a local
SQLite file (`backend/data/pnr_log.sqlite3`) — feature snapshot, predicted
probability, and (once known) the real outcome. It also records quota, train
number, and route, which the current model cannot use but which no public
dataset provides. This is the only realistic path to the missing features:
real usage accumulates real labelled rows as a byproduct of people checking
their PNRs.

Blocked in practice by the 10-requests/month quota — see "Quota reality".

- `GET /flywheel/stats` — quick visibility: total checks logged, how many
  have a captured outcome, how many are real (non-mock).
- `python -m app.poll_outcomes` — run periodically (e.g. a daily cron once
  live) to re-check PNRs past their journey date and record what actually
  happened. Verified locally: it correctly finds past-due unresolved rows
  and only records an outcome once the status actually resolves (leaves
  still-waitlisted rows pending rather than guessing).
- Retraining on collected data isn't built yet — it would follow
  `train_real.py`'s pipeline, reading logged rows instead of the Kaggle CSV,
  once the row count justifies it.

## Mobile app

`mobile/` is an Expo (React Native, SDK 57) app with one screen mirroring
the web app's PNR-first flow — same `/pnr/{pnr_number}` call, same result
layout. Confirmed it bundles cleanly (`npx expo export --platform android`
succeeded, 579 modules, no errors) but hasn't been run on an actual device
or emulator from here — that needs a physical run to confirm.

```bash
cd mobile
npm start        # opens Expo dev tools / QR code
```

Scan the QR code with the **Expo Go** app (iOS or Android, free, no
developer account needed). `mobile/config.js` points at the deployed Render
backend, so the phone does not need to be on the same network as this
computer and nothing has to be running locally. To develop against a local
backend instead, set `USE_LOCAL = true` in that file and update `LAN_IP`.

Note: some networks (including some campus and office WiFi) block Vercel and
Render outright. If the site or app will not load, try mobile data before
assuming something is broken.

Publishing later: Android as a sideloaded APK is free
(`eas build --platform android` or a local build); Play Store listing is a
$25 one-time fee. iOS testing via Expo Go is free; an actual App Store
listing needs a $99/year Apple Developer account and, for the final signed
build, a Mac (Expo's cloud build service can substitute for most of the
process).

## Live

| | URL |
|---|---|
| Web app | https://irctc-smoky.vercel.app |
| API | https://pnr-predictor-api.onrender.com |

Both on free tiers. The API sleeps after ~15 minutes idle and takes about a
minute to wake; both UIs show a message instead of hanging silently. Open the
site a couple of minutes before demoing so it is already warm.

## Next steps

1. **Test the mobile app on a device** via Expo Go. It bundles cleanly (579
   modules, no errors) but has never actually been run.
2. **Verify against a real waitlisted PNR.** Confirmed tickets are verified
   end-to-end; the waitlisted path is inferred from the provider schema and
   has never seen a live WL response. Costs one of the 10 monthly requests.
3. **Extend the model beyond four features.** Quota is the biggest gap (5th
   by importance; General 26% vs Remote Location 45%). It is available from
   the PNR lookup but absent from every usable training set, so it needs
   self-collected data — which needs paid API quota.
4. **Add caching and per-IP rate limiting** before switching off mock mode.
   Ten requests a month disappear instantly on a public URL.
5. **Benchmark against the provider's own `PredictionPercentage`** — log it
   next to our prediction and the real outcome to see which is better
   calibrated.
