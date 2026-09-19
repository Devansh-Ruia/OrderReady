# Targeted review-form repair

Implemented on `fix/review-form-layout`. No commit was made. The submitted HEAD remains `bdeb1af02f8bae7178c3114fe250706769ec4456`.

The [baseline manifest](repair-baseline/manifest.json) and [working-state archive](repair-baseline/working-state.zip) preserve the 23 preexisting modified/untracked files. Hash comparison confirmed only `app.py`, `.streamlit/config.toml`, and `tests/test_frontend.py` changed from that working state. [Repair-only diff](repair-only.patch).

Product changes are limited to review rendering in `app.py` and native input theme settings. Header, intro, extraction, cache, validation, callbacks, existing widget keys, review locks, and ticket contract retain their baseline implementations. Test and verification artifacts are separate.

Exact theme rules:

```toml
secondaryBackgroundColor = "#F7F4EE"
showWidgetBorder = true
borderColor = "#8B8174"
```

Exact CSS replacement:

```css
/* Removed */
.st-key-workspace [data-testid="stMetricValue"] {font-size:1.5rem;}
/* Added */
.st-key-review input {font-size:16px;}
```

White panels and orange `#B6491D` accent remain. Browser measurements confirm every native review input is 40px high with 16px text, a 1px `#8B8174` border and `#F7F4EE` fill. Keyboard focus uses the native orange border. No new global overrides, fixed form height, padding overrides, or `!important` were added.

Customer inputs use two wrapping columns; sizes and Requested total use four. Native gaps are 20px between groups, 12px between columns, 8px within the quantity group, and 4px between customer/deadline inputs and messages. Native input help replaces the two popovers. Duplicate metrics are removed.

Quantity summaries distinguish missing quantities, invalid values, explicit zero, and unknown requested totals. Mismatch display derives both numbers from current validation output. Raw validator messages and questions are not changed. Customer/contact messages appear under their own input, quantity messages under the summary, deadline failures under the deadline, and unmapped validation messages afterward.

One collapsed View source details section retains the exact draft source and all original evidence. Source rendering preserves surrounding whitespace and newlines. The deadline caption uses only stored extraction evidence. Manual entry does not invent evidence. Stale drafts continue showing their own original source.

Matched screenshots use the same synthetic manual source and values: empty customer/contact, S=10, M=10, L=5, requested=30, deadline=September 28. Fresh Chrome contexts used 100% zoom, DPR 1, and visual viewport scale 1. Review panel top alignment is 70px desktop and approximately 65px mobile.

| Viewport | Before | After |
| --- | --- | --- |
| 1440 x 900 | [Desktop before](repair-matched-before-desktop-1440.png) | [Desktop after](repair-matched-after-desktop-1440.png) |
| 390 x 844 | [Mobile before](repair-matched-before-mobile-390.png) | [Mobile after](repair-matched-after-mobile-390.png) |
| 390 x 844, quantities at 70px | [Quantities before](repair-matched-before-mobile-quantities.png) | [Quantities after](repair-matched-after-mobile-quantities.png) |

Desktop review height: 946.78px to 774.77px, 172.02px shorter. Mobile review height: 1324.38px to 1162.77px, 161.61px shorter. Desktop gap from the bottom of Size S to the mismatch: 342.39px to 38.39px.

Verification performed:

- Baseline offline suite: 166 passed in 28.56s. Final `python -m pytest -q`: 175 passed in 37.56s. Nine new presentation cases cover grouping/help, warning adjacency, missing/invalid/zero quantities, exact source and stale provenance, and unmapped messages. Existing behavioral cases remain.
- Matched browser inputs have visible borders when empty. Desktop quantity controls align. Mobile columns stack without document or review-content overflow. Expanded mocked source details also have no mobile overflow.
- [Keyboard focus](repair-keyboard-focus.png) is visible. Tab order follows customer, contact, native help/input pairs for S/M/L/requested/deadline, source-details summary, then acknowledgment. Enter opens source details; Space operates acknowledgment and issue checkboxes.
- Manual mismatch plus incomplete deadline remain blocked after acknowledgment. A separate mocked extraction verifies the exact caption `Customer wrote "Needed September 28"`, every evidence string, and draft source: [source details](repair-mocked-source-details.png), [desktop](repair-mocked-desktop.png), [mobile](repair-mocked-mobile.png).
- Corrected quantities and a complete synthetic deadline remain blocked until all extraction issues are resolved. Issue resolution invalidates acknowledgment. After acknowledgment, preparation locks the inputs and downloads the expected ticket byte-for-byte: [421-byte ticket](repair-mocked-intake.txt), [prepared state](repair-prepared-ticket.png).
- Edit intake removes approval and download access. Subsequent edits keep invalid data blocked. Changing the inquiry retains the original draft's source and evidence: [stale source on mobile](repair-mocked-stale-source-mobile.png).
- No browser page errors or Streamlit exceptions were observed. The isolated wrapper mocks extraction, blocks model HTTP, skips credential files, and disables server telemetry. No paid model calls were made. Reported non-HTTP blob URLs belong to the local servers.

[Browser measurements and assertions](repair-browser-verification.json), [browser script](repair-browser-verification.cjs), [offline wrapper](repair-browser-app.py).

No known introduced defects remain from these checks. Browser coverage is desktop Chrome with the two requested viewport sizes; physical mobile devices and live model extraction were not tested. Existing `tests/test_unit.py` has a trailing-blank-line warning under `git diff --check`; its bytes are unchanged from the preserved baseline. The targeted repair diff has no whitespace errors.

Context7 failed with an expired OAuth token. `npx ctx7@latest login` restores access. Theme and layout options were verified against installed Streamlit 1.64.0 and the official [configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml), [container](https://docs.streamlit.io/develop/api-reference/layout/st.container), and [columns](https://docs.streamlit.io/develop/api-reference/layout/st.columns) documentation.

Checker implementation approval is recorded separately in [repair-checker-review.md](repair-checker-review.md).
