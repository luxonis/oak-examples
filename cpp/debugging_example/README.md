# Quick Start

Follow these steps to enable remote debugging for your OAK C++ application.

## Requirements

### Open the Correct Folder

You must open the **`debugging_example` directory itself as the VS Code workspace root**.

Do **not** open the parent `oak-examples` directory. The debug configuration relies on `${workspaceFolder}` resolving to this example directory.

### Install oakctl

Debugging uses `oakctl` to discover devices and start applications on the device.

Install `oakctl` by following the official documentation:

https://docs.luxonis.com/software-v3/oak-apps/oakctl/

Make sure the `oakctl` command is available in your terminal before starting debugging.

______________________________________________________________________

## 1. Install the VS Code C/C++ Extension

Install the official Microsoft **C/C++ extension** for VS Code.

Name: **C/C++**\
VS Marketplace Link: https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools

Or install from VS Code:

1. Open **Extensions** (Ctrl+Shift+X)
2. Search for **C/C++**
3. Install **C/C++ (Microsoft)**

This extension provides the `cppdbg` debugger used by this example.

______________________________________________________________________

## 2. Install GDB

### Ubuntu

Install the multi‑architecture GDB package:

```bash
sudo apt update
sudo apt install gdb-multiarch
```

### macOS

Install GDB with Homebrew:

```bash
brew install gdb
```

After installing on macOS, **remove the `miDebuggerPath` field** from `.vscode/launch.json` if it exists. The debugger will automatically use the system GDB.

## 3. Start Debugging

1. Open the `debugging_example` directory directly in VS Code.
2. Press **F5** (Run → Start Debugging).
3. Enter the **Device IP address** when prompted.
   - If the field is left empty, the debugger will automatically run `oakctl list` to discover available devices and prompt you to select one.
4. Enter the **Device password** if required.

The debugger will automatically attach to the device.

______________________________________________________________________

## What Happens Behind the Scenes

When you start debugging:

- A local placeholder binary is created at:

```
build/main_device
```

(This is required by VS Code's C++ debugger validation step.)

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

______________________________________________________________________

## Notes

- The device IP is stored locally in `.vscode/oak.env` for consistency.
- `.vscode/oak.gdb` is regenerated automatically when debugging starts.
- No manual GDB commands are required.
- No hardcoded paths are used — the setup relies entirely on `${workspaceFolder}`.

This approach keeps the configuration minimal, reproducible, and portable across different OAK C++ projects.
