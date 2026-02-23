# Remote Debugging Setup for OAK C++ Apps

This example demonstrates a clean and reproducible VS Code remote debugging workflow for C++ OAK applications.

> ⚠️ **Important:** Open this `debugging_example` folder itself as the root workspace in VS Code.  
> Do NOT open the parent `oak-examples` directory. The debug configuration relies on `${workspaceFolder}` resolving to this example directory.

---

## Quick Start

1. Open the `debugging_example` directory directly in VS Code.
2. Press **F5** (Run → Start Debugging).
3. Enter the **Device IP address** when prompted.
4. Enter the **Device password** if required.

That’s it — the example handles the rest automatically.

---

## What Happens Under the Hood

When you start debugging:

- A local placeholder binary is created at:
  ```
  build/main_device
  ```
  (required by VS Code's C++ debugger validation step).

- Your device IP is written to:
  ```
  .vscode/oak.env
  ```
  This ensures the IP is stored locally and reused consistently across tasks.

- A `.vscode/oak.gdb` file is generated dynamically.  
  This file instructs GDB to:
  - Connect to `gdbserver` on the device
  - Pull the binary directly from the container
  - Reload symbols
  - Configure source path mapping

- `oakctl` connects to the device and starts the application.

- VS Code attaches GDB to `gdbserver` on port `5678`.

All of this is automated through `tasks.json` and `launch.json`.

---

## Required Runtime Configuration

Your container must start the backend via `gdbserver`. Update `backend-run.sh`:

```sh
#!/bin/sh
gdbserver 0.0.0.0:5678 /app/build/main
```

---

## oakapp.toml Configuration

Ensure your `build_steps` include debug symbols and install `gdbserver`:

```toml
build_steps = [
    # Install gdbserver
    "apt-get install -y --no-install-recommends gdb gdbserver",

    # Create and enable backend service startup.
    "mkdir -p /etc/service/backend",
    "cp /app/backend-run.sh /etc/service/backend/run",
    "chmod +x /etc/service/backend/run",

    # Build in Debug mode so symbols are available
    "cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Debug",
    "cmake --build /app/build --parallel",
]
```

---

## Notes

- The device IP is stored locally in `.vscode/oak.env` for consistency.
- `.vscode/oak.gdb` is regenerated automatically when debugging starts.
- No manual GDB commands are required.
- No hardcoded paths are used — the setup relies entirely on `${workspaceFolder}`.

This approach keeps the configuration minimal, reproducible, and portable across different OAK C++ projects.