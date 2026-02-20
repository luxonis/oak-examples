# Remote Debugging Setup for OAK C++ Apps

This example shows the steps to add VS Code remote debugging to any C++ OAK app.

## 1. Copy `.vscode/launch.json`

Copy the `.vscode/launch.json` from this project into your app's `.vscode/` folder. No changes needed — it uses `${workspaceFolder}` throughout so it works in any project location.

On launch it will prompt for:

- **Board IP** — IP address of your OAK device

## 2. Update `backend-run.sh`

Your `backend-run.sh` should start `gdbserver` wrapping your binary instead of running it directly:

```sh
#!/bin/sh
gdbserver 0.0.0.0:5678 /app/build/main
```

## 3. Update `oakapp.toml`

Add the following to your `build_steps`:

```toml
build_steps = [
    # Install gdbserver
    "apt-get install -y --no-install-recommends gdb gdbserver",

    # Create and enable backend service startup.
    "mkdir -p /etc/service/backend",
    "cp /app/backend-run.sh /etc/service/backend/run",
    "chmod +x /etc/service/backend/run",

    # Build in Debug mode so the binary has symbols
    "cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    "cmake --build /app/build -- -j",
]
```

## 4. Deploy and Debug

```bash
oakctl app run .
```

Then set breakpoints and press **F5** in VS Code. GDB connects to `gdbserver` on port 5678, pulls the binary directly from the container, reloads symbols, and starts the debug session.
