# Checkpoint 3 Presentation Checks

`npm test` bundles the TypeScript component/API tests with the existing Vite
esbuild dependency into a disposable temporary directory, runs Node's test
runner, and removes the bundle. No new runtime/test package is required for
these checks. `npm run build` separately checks production TypeScript.

`npm run test:browser` requires an available Playwright installation and
Chromium. Set `PLAYWRIGHT_MODULE` to its ES module entry point and, if needed,
`PLAYWRIGHT_EXECUTABLE_PATH` to an existing browser executable. No browser or
model is downloaded by the suite. This project does not vendor that external
browser toolchain. Example with a normally installed external toolchain:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
PLAYWRIGHT_EXECUTABLE_PATH=/absolute/path/to/chromium \
npm run test:browser
```

The browser harness starts and stops its own loopback-only Vite server, beginning
at port 5174 and selecting the next free port if occupied. It does not use the
normal Compose frontend. Every non-server HTTP request is intercepted; unknown
requests fail the test rather than reaching the application. All users, tokens,
facts, jobs and runs are synthetic. Mutation assertions inspect mocked requests,
not application/database state. Desktop/mobile screenshots go to the OS
temporary directory, not tracked files or frozen evaluation directories.

Coverage includes navigation without writes/legacy recommendations, explicit
single run requests, conflict handling without retry, additive roles, owned fact
requests, manager group/classification/applicability forms, confirmed deletions,
unreplayable evidence removal, error/empty states, native labels and keyboard
access, and narrow-screen overflow. These are targeted accessibility checks,
not a full assistive-technology certification. Corpus fact entry and a separately
authorized non-null demonstration remain outstanding Phase 6 acceptance work.
