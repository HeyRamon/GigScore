/* =============================================================================
   Configuration and copy for the CreditWise demo.

   Everything that used to be a magic number, an inline string, or a value
   duplicated between markup and script lives here. app.js imports nothing else.
   ============================================================================= */

const GIGSCORE_CONFIG = (function buildConfig() {
  "use strict";

  /* The state contract this build understands. A payload with a different major
     version is rejected rather than half-rendered. */
  const SCHEMA_VERSION = 1;

  /* Fields every member record must carry for render() to be safe. */
  const REQUIRED_MEMBER_FIELDS = [
    "name",
    "score",
    "band",
    "week_delta",
    "updated_line",
    "factors",
    "accounts",
    "coach",
    "sources_connected",
    "sources_total",
  ];

  /* The GigScore range, in one place. */
  const SCORE = {
    MIN: 300,
    MAX: 850,
    /* A sliver of fill so a bar at 0% still reads as a bar. */
    MIN_VISIBLE_PROGRESS_PCT: 6,
    get RANGE() {
      return this.MAX - this.MIN;
    },
  };

  /* Band floors, ordered low to high. The floor lookup falls back to SCORE.MIN
     via findBandFloor() rather than by repeating the number at each call site. */
  const BANDS = [
    { name: "Needs work", floor: SCORE.MIN },
    { name: "Fair", floor: 580 },
    { name: "Good", floor: 670 },
    { name: "Very good", floor: 740 },
    { name: "Excellent", floor: 800 },
  ];

  /* Factor status -> status modifier class. Unknown statuses read as healthy,
     matching the previous behaviour, but are reported by app.js. */
  const FACTOR_STATUS_MODIFIER = {
    "Needs work": "poor",
    Fair: "watch",
    Good: "good",
    Excellent: "good",
  };
  const DEFAULT_STATUS_MODIFIER = "good";

  /* Ledger event copy. Labels only - the point value is read from the event's
     own delta, so the two can no longer disagree. Keys mirror the event_type
     values emitted by the scoring pipeline; app.js logs any key it cannot find
     instead of printing a raw identifier to the presenter's screen. */
  const EVENT_LABELS = {
    rent_reported_on_time: "rent reported on time",
    subscription_reported_on_time: "subscription reported on time",
    consistency_streak_4wk: "4-week consistency streak",
    steady_tuesday_pair: "two steady Tuesdays",
    source_connected: "new income source connected",
    rent_payment_missed: "rent reported late",
  };

  /* Presenter-facing strings, kept out of the render functions. */
  const COPY = {
    scoreUpAffix: "▲ +",
    scoreDownAffix: "▼ ",
    weekSuffix: " this week",
    noEvents: "no scoreable events",
    cohortFootnote:
      "Same pipeline, same SQL weights; only the verified events differ.",
    feedbackLogged: "Thanks — feedback logged to the audit trail.",
    unknownEvent: "unrecognised event",
    liveDataUnavailable:
      "Showing bundled demo data — state.json could not be loaded.",
    liveDataRejected:
      "Showing bundled demo data — state.json did not match the expected schema.",
  };

  /* Where the live state lives when the demo is served over http. */
  const STATE_URL = "state.json";

  return {
    SCHEMA_VERSION,
    REQUIRED_MEMBER_FIELDS,
    SCORE,
    BANDS,
    FACTOR_STATUS_MODIFIER,
    DEFAULT_STATUS_MODIFIER,
    EVENT_LABELS,
    COPY,
    STATE_URL,
  };
})();
