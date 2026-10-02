# Publish OAK App (CI helper)

This script is used by the `publish_oakapp` GitHub Actions workflow to
adjust an example's `oakapp.toml`, build the app, and publish it to Hub.
The workflow supports both manual runs (`workflow_dispatch`) and calls
from other workflows (`workflow_call`), taking `root_dir` and an optional
`new_identifier` override. Callers must pass `GITLAB_TOKEN` and
`OAKCTL_HUB_TOKEN` secrets.

It also supports local runs outside of Docker, as long as `oakctl` is
available in your PATH and you have a valid Hub token.

## Local usage

Run from the repo root and pass required environment variables:

```bash
ROOT_DIR="neural-networks/generic-example" \
OAKCTL_HUB_TOKEN="your_token_here" \
.github/ci/publish_oakapp/publish_oakapp.sh
```

Optional environment variables:

- `LUXONIS_OFFICIAL_IDENTIFIER=true` to replace
  `com.example.<top-level-folder>` with `com.luxonis` on the `identifier`
  line. Defaults to `true`.
- `NEW_IDENTIFIER="com.luxonis.myapp"` to override the `identifier`
  line (takes precedence over `LUXONIS_OFFICIAL_IDENTIFIER`).

Notes:

- The script requires `oakapp.toml` inside `ROOT_DIR`.
- It restores the original `oakapp.toml` and deletes the built `.oakapp`
  file on exit, even if the run fails.
- This performs a real publish; consider using a temp copy of an example
  if you want to avoid touching your working tree.

## Bulk publishing

The `Publish OAK Apps` workflow publishes the curated list in
`.github/publish_oakapps.txt`. Run it from GitHub Actions with an optional
comma-separated `exclude_apps` input. Set `dry_run` to validate the list and
show the identifier plan without reserving a testbed or publishing.
Each selected app calls the reusable `publish_oakapp.yaml` workflow,
which handles runner setup, a reservation name derived from the app path,
publishing, and a per-app result summary. The bulk workflow keeps list
validation, dry-run handling, and a matrix of up to three parallel apps;
a failed publish does not cancel the other matrix jobs.

For example, from the repository root:

```bash
gh workflow run publish_oakapps.yaml \
  --repo luxonis/oak-examples \
  --ref main \
  -f exclude_apps=apps/dino-tracking,neural-networks/ocr/general-ocr
```
