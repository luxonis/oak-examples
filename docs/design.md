# Frontend design

The custom React frontends in this repository (every `frontend/` that depends on
`@luxonis/depthai-viewer-common`) share one page shell and one set of design rules, so each example
looks like part of the same family and is a clean starting point to copy.

## Luxonis design

- Default mode: functional
- Foundation: ui-libs; use the versions installed in each frontend (`@luxonis/ui-components` 1.3.9).
- Fonts: library and system default; frontends do not set their own font stack.
- Image files: WebP, including animated images.
- Area overrides: none.
- Decisions: see below.

## Page shell

Every frontend renders its page through `src/AppShell.tsx` and styles it with the shared block of
`src/index.css`. The reference copies live in
[custom-frontend/raw-stream/frontend](../custom-frontend/raw-stream/frontend/src). Every other frontend
holds a byte-identical copy, so a copied example stays standalone.

- Header: the app name as the page title (`<h1>` with `PageTitle`), and on the right an optional
  `status` slot for app badges followed by the connection `Badge`.
- Streams: the `Streams` viewer and anything drawn over it. It fills the space next to the side
  column, and has a fixed height on screens narrower than 48rem.
- `below`: content that belongs under the stream, such as a history list. The stream then sits in a
  16:9 viewer and the column scrolls on wide screens and grows with the page on narrow ones.
- `fitContent`: lets a streams area that holds several viewers grow with the page on narrow screens.
- Side column: 24rem wide on screens of 48rem and wider, full width below. Controls are grouped in
  `Card variant="outline" intent="white"` cards, one card per task. On the gray intent the Slider
  track is not visible.
- `LoadingState` for waiting on streams or models, and `Steps` for numbered instructions.
- `src/Notifications.tsx` is shared the same way, from
  [apps/dino-tracking/frontend](../apps/dino-tracking/frontend/src), by frontends that show toasts.

Width-dependent layout is plain CSS with `app-` class names. The Luxonis libraries load their own
Tailwind utilities after the app's, so a responsive utility such as `md:flex-row` loses to their
`.flex-col`. App-specific CSS goes below the `/* App-specific styles */` line in `src/index.css`.

## Rules

- Text comes from the library text components (`PageTitle`, `SubHeader`, `NormalText`, `Label`,
  `SubLabel`), not Tailwind typography utilities.
- Colors come from component intents and `--lux-*` variables, never hex values or Tailwind palette
  classes.
- Use library controls: `Select`, `Accordion`, `Progress`, `Badge`, `Alert`. A choice between a few
  modes is a `fieldset` of buttons, with the selected one `filled`/`active` and `aria-pressed`.
- No middle dot (U+00B7) as a separator.
- The `index.html` title matches the `AppShell` title.

## Check

```bash
python3 scripts/check_frontends.py         # report problems
python3 scripts/check_frontends.py --fix   # copy the shared files into every frontend
```

CI runs the check on pull requests.
