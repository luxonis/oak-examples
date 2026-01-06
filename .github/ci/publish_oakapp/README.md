# Publish OAK App (CI helper)

This script is used by the `publish_oakapp` GitHub Actions workflow to
adjust an example's `oakapp.toml`, build the app, and publish it to Hub.

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

- `LUXONIS_OFFICIAL=true` to replace `com.example` with `com.luxonis`
  on the `identifier` line. Defaults to `true`.
- `NEW_IDENTIFIER="com.luxonis.myapp"` to override the `identifier`
  line (takes precedence over `LUXONIS_OFFICIAL`).

Notes:

- The script requires `oakapp.toml` inside `ROOT_DIR`.
- It restores the original `oakapp.toml` and deletes the built `.oakapp`
  file on exit, even if the run fails.
- This performs a real publish; consider using a temp copy of an example
  if you want to avoid touching your working tree.
