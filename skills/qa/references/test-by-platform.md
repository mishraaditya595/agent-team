# Testing by platform

Use the cheapest method that really exercises the AC. Check `project.md` `## Stack` to pick.

- **Web app:** run it locally; use Playwright (or a browser tool the session has) to click through the AC. Needs UI → the workflow runs QA on the `standard` tier.
- **Flutter / mobile:** `flutter test` for widget tests; `flutter test integration_test/` on an emulator if one is available. No emulator → widget tests that pump the screen and assert on what the user sees.
- **Backend / API:** start the service locally; make real requests (`curl` or the project's HTTP test client) and assert on status and body. Check the data store if the AC is about persistence.
- **CLI / library:** call it the way a user would; assert on output and exit code.
- **No way to exercise it here** (needs a device, a paid service, production data): mark the AC `UNVERIFIED` with the reason. UNVERIFIED counts as FAIL unless `plan.md` marks that AC as manual — then list it for the owner to check before merging.
