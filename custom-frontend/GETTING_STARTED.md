# Building a Custom Front End for DepthAI

This guide walks you through setting up a React frontend that displays live camera streams from OAK devices and communicates with your Python backend. By the end, you'll have a working development environment ready to customize.

### Prerequisites

- Node.js and npm installed

> We recommend using nvm (Node Version Manager) to install and manage Node.js and npm.

- Python with DepthAI installed
- A Luxonis OAK device (required to run the application)

## Table of Contents

- [Quick Start](#quick-start)
- [Starting From Scratch](#starting-from-scratch)
  - [Project Setup](#project-setup)
  - [Build Your Front End](#build-your-front-end)
- [Run the Application](#run-the-application)
  - [Peripheral Mode](#peripheral-mode)
  - [Standalone Mode (RVC4 only)](#standalone-mode-rvc4-only)
- [What's Next](#whats-next)
- [Known Issues](#known-issues)

______________________________________________________________________

# Quick Start

If you want to skip setup and start modifying a working app immediately,
see the [`raw-stream`](./raw-stream) example.

For a more advanced reference featuring AI inference, WebRTC,
and richer UI patterns, see
[`open-vocabulary-object-detection`](./open-vocabulary-object-detection).

______________________________________________________________________

# Starting From Scratch

## Project Setup

### Create a React + TypeScript Project

`@luxonis/depthai-viewer-common` library provides React components and hooks to build a custom frontend for DepthAI applications with ease.

We recommend using [Vite](https://vite.dev/guide/) to scaffold your project with the `react-ts` template.

```bash
npm create vite@latest frontend -- --template react-ts
```

### Declare and Install Dependencies

Your `package.json` needs the following dependencies and scripts:

**Dependencies:**

```json
"dependencies": {
  "@luxonis/depthai-viewer-common": "^1.6.2",
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router": "^7.5.0",
  "react-router-dom": "^7.5.0"
},
"devDependencies": {
  "@pandacss/dev": "0.53.0",
  "@types/react": "^18.3.20",
  "@types/react-dom": "^18.3.6",
  "@vitejs/plugin-react": "^4.3.4",
  "globals": "^16.0.0",
  "typescript": "~5.7.2",
  "vite": "^6.3.1"
}
```

**Scripts** (required for PandaCSS codegen):

```json
 "scripts": {
     "dev": "vite",
     "build": "npm run styleGen && tsc -b && vite build",
     "preview": "vite preview",
     "styleGen": "panda codegen"
 }
```

See [package.json](./raw-stream/frontend/package.json) for a complete example.

Then install the dependencies:

```bash
npm i
```

> ⚠️ **React version requirement**
>
> `@luxonis/depthai-viewer-common` currently supports **React 18.x only**.
>
> An **RC (Release Candidate)** version with **React 19.x** support can be found
> [here](https://www.npmjs.com/package/@luxonis/depthai-viewer-common?activeTab=versions).
> This version is not yet an official release and may contain unresolved issues.

### Configure PandaCSS

Our packages use Luxonis common UI components from
`@luxonis/common-fe-components` package, which depends on PandaCSS for
tokens, recipes, and layered styles.

To use these components, [PandaCSS](https://panda-css.com/) is required.

**Initialize PandaCSS** in your project root:

```bash
npx panda init --postcss
```

**Edit `panda.config.ts`** with the preset from our style lib:

```typescript
import { defineConfig, defineGlobalStyles } from "@pandacss/dev";
import { pandaPreset } from "@luxonis/common-fe-components";

export default defineConfig({
  presets: [pandaPreset],
  preflight: true,
  include: ["./src/**/*.{ts,tsx}"],
  exclude: [],
  jsxFramework: "react",
  outdir: "styled-system",
  forceConsistentTypeExtension: true,
});

```

See [panda.config.ts](./raw-stream/frontend/panda.config.ts)

### Configure Vite

Your `vite.config.ts` needs the following settings:

#### Relative base path (required for Luxonis Hub)

```typescript
base: "",
```

This makes asset paths relative instead of absolute, which is required when deploying to [Luxonis Hub](https://hub.luxonis.com).

> ⚠️ **Important:** Avoid using paths starting with `/` anywhere in your code (e.g., `/images/logo.png`). Use relative paths instead (e.g., `./images/logo.png` or `images/logo.png`). Absolute paths will break when deployed to Luxonis Hub and cause cryptic errors or blank pages.

#### FoxGlove compatibility

Some Luxonis tooling assumes a `global` object to exist.
Vite does not define this by default, so it must be added explicitly.

```
define: {
    global: {},
},
```

- Use `esm` for workers and bundling

```
    worker: {
        format: "es",
    },
    build: {
        rollupOptions: {
            output: {
                format: "esm",
            },
        },
    },
```

See [vite.config.ts](./raw-stream/frontend/vite.config.ts) for a complete example.

### Configure TypeScript

Replace Vite-generated TypeScript config files with the following configurations to ensure compatibility with Luxonis packages

**Replace `tsconfig.app.json`:**

```json
{
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/example.app.tsbuildinfo",
    "target": "ESNext",
    "useDefineForClassFields": true,
    "lib": [
      "ESNext",
      "WebWorker",
      "DOM",
      "DOM.Iterable"
    ],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": [
    "src"
  ]
}

```

See [tsconfig.app.json](./raw-stream/frontend/tsconfig.app.json)

**Replace `tsconfig.node.json`:**

```json
{
	"compilerOptions": {
		"composite": true,
		"tsBuildInfoFile": "./node_modules/.tmp/tsconfig-example.node.tsbuildinfo",
		"skipLibCheck": true,
		"module": "ESNext",
		"moduleResolution": "bundler",
		"allowSyntheticDefaultImports": true,
		"strict": true,
		"noEmit": true
	},
	"include": ["vite.config.ts"]
}

```

See [tsconfig.node.json](./raw-stream/frontend/tsconfig.node.json)

______________________________________________________________________

## Build Your Front End

### Global CSS Setup

Luxonis frontend components rely on PandaCSS layered styles. The generated index.css must be replaced.

**Update `index.css`:**

Add this code to an `src/index.css` file imported in the root component of your project:

```css
@layer reset, base, tokens, recipes, utilities;
```

This enables PandaCSS layered styles and prevents style ordering issues
in Luxonis UI components.

> **Note:** Feel free to remove src/App.css file as we don't need it anymore, and make sure to remove the import from the src/App.tsx file.

### Import Styles

In your application entrypoint, import styles in this order:

```typescript
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/common-fe-components/styles';
import '@luxonis/depthai-pipeline-lib/styles';
```

See [main.tsx](./raw-stream/frontend/src/main.tsx) for a complete example.

### Configure Routing

To be able to host your app on Luxonis Hub, you need to set the `basename` of your `BrowserRouter` to include the base path and app version from the URL.

> **Note:** This configuration is **only required when hosting the frontend on Luxonis Hub**.\
> If you are running the frontend locally or hosting it elsewhere, no `basename` configuration is needed.

`DepthAIContext` manages the connection to your backend and provides it to child components via React context.

```tsx
function getBasePath(): string {
  return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? "";
}

<BrowserRouter basename={getBasePath()}>
  <DepthAIContext>
    {/* your routes */}
  </DepthAIContext>
</BrowserRouter>
```

See [main.tsx](./raw-stream/frontend/src/main.tsx) for a complete example.

### Displaying Streams

Video streams are the core of most DepthAI applications. They are registered in your Python backend and can be displayed in the frontend using the `Streams` component.

```tsx
import { Streams } from "@luxonis/depthai-viewer-common";
```

This component automatically renders all streams added via `visualizer.addTopic()` in your Python backend:

```python
# Backend: add a stream topic
visualizer.addTopic("RGB RAW", rgb_output)
```

If your backend publishes multiple topics, use `defaultTopics` to set the initial stream and `allowedTopics` to restrict which streams are available. The frontend will display a toolbar for switching between them.

```tsx
    <Streams
          defaultTopics={['RGB RAW']}
          allowedTopics={['RGB RAW', 'RGB H.264']}
    />
```

> **Note:** Topic names must match exactly between frontend and backend.

For additional customization options, explore the `Streams` component props.

### Frontend-Backend Communication

Services allow your frontend and Python backend to exchange messages.
To set up a service, register it in your backend with a unique name and a handler function.

**Backend** — register a service:

```python
def handle_message(message):
    print("Received:", message)
    return {"status": "ok"}

visualizer.registerService("My Service", handle_message)
```

Then, call it from the frontend using the `daiConnection.postToService()` method.

**Front End** — call the service:

```tsx
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

function MyComponent() {
  const { daiConnection, connected } = useDaiConnection();

  const sendMessage = () => {
    daiConnection?.postToService(
      "My Service",           // Must match backend service name
      { action: "start" },    // Any JSON-serializable data
      (response) => {
        console.log("Response:", response);
      }
    );
  };

    return (
            <Button onClick={sendMessage}>Send</Button>
    );
}
```

See [MessageInput.tsx](./raw-stream/frontend/src/MessageInput.tsx) for a working frontend example.\
See [main.py](./raw-stream/main.py) custom_service function for a working backend example.

### Styling

Since `@luxonis/common-fe-components` depends on PandaCSS, it is recommended to use PandaCSS directly in your project
as well. It's highly recommended to check out [PandaCSS docs](https://panda-css.com/docs/overview/getting-started) and use the
`css()` function imported from `styled-system/css` like it is done in [App.tsx](./raw-stream/frontend/src/App.tsx).

______________________________________________________________________

# Run the application

On OAK devices, we can run the application in two modes: Peripheral and Standalone.

### Peripheral Mode

In Peripheral mode, the backend application runs on your host machine and connects to the device over the network.
To run the app in this mode you need the dependencies installed as described in the [Install-Dependencies](#declare-and-install-dependencies).

There are two ways to run in Peripheral mode: using Vite's preview server, or using a custom Python server.

#### Vite Preview Server

To run it with Vite's preview server, first build and start frontend in the preview mode with:

```bash
npm run build && npm run preview
```

Then you can run the backend application from another terminal tab with:

```bash
python main.py
```

This will run the example, and you’ll be able to access the frontend by opening the URL shown in terminal (e.g., `http://localhost:4173`).

#### Python Server

Another way of running the application in peripheral mode is by starting the frontend using a Python server that serves the built files.
Example of the server that does that can be found in the [raw-stream/frontend_server.py](./raw-stream/frontend_server.py).

This approach is useful when you want the backend to control both
the device connection and static frontend serving.

In such case you need to first build the frontend with:

```bash
npm run build
```

Then you can run the backend and frontend server with:

```bash
python main.py
```

This will run the example, and you’ll be able to access the frontend by opening the URL shown in terminal (e.g., `http://localhost:8082`).

> **Note:** Make sure that the frontend is built before running the python server and that path to the built files is correctly passed to the server.

### Standalone Mode (RVC4 only)

In Standalone Mode, the application runs entirely on the device.
To run the application in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

Standalone mode requires an `oakapp.toml` file, which defines how
your application is built and executed on the device.

#### Configure oakapp.toml

This file defines app metadata, build steps, and how your frontend is served.

Create an `oakapp.toml` file with the following content:

```toml
# (Required) App Identifier
identifier = "com.luxonis.python_demo"
# (Required) App Entrypoint
entrypoint = ["bash", "-c", "python3 /app/main.py"]

# (Optional) Prepare container commands
# Here is the place where you can install all the dependencies that are needed at run-time
prepare_container = [
    { type = "COPY", source = "requirements.txt", target = "requirements.txt" },
    { type = "RUN", command = "apt-get update" },
    { type = "RUN", command = "apt-get install -y python3-pip" },
    { type = "RUN", command = "pip3 install -r /app/requirements.txt --break-system-packages" },
]

# (Optional) Prepare build dependencies
# Here is the place where you can install all the dependencies that are needed at build-time
prepare_build_container = [
    # Example: npm, gcc, ...
]

# (Optional) Additional commands after all the app files are copied to the container
build_steps = []

# Static Front End path
[static_frontend]
dist_path = "./frontend/dist"

# Frontend Build Steps
[static_frontend.build]
source_path = "./frontend"
steps = ["bash -c 'cd /app/frontend && npm install && npm run build'"]

```

See the [oakapp.toml configuration reference](https://docs.luxonis.com/software-v3/oak-apps/configuration) for all available options.

> ***Note:*** For DepthAI OAK Apps, we recommend our [Base Image](https://docs.luxonis.com/software-v3/oak-apps/base-image/) that includes most of the dependencies you may need.

Complete example of `oakapp.toml` with the Base Image can be found in [here](./open-vocabulary-object-detection/oakapp.toml).

#### Run the App

After the configuration is done, you can connect to your device and run the app by running these commands in the directory with `oakapp.toml`:

```bash
oakctl app run .
```

> **Note:** If you have multiple devices or the device is on a different network, specify the IP: `oakctl connect <DEVICE_IP>` before running

#### Local Frontend Development

When developing the frontend, you can run it locally while the backend runs on the device. This avoids rebuilding and redeploying the entire container for every frontend change, saving significant development time.

1. **In oakapp.toml**, comment out all the frontend-related sections to prevent building and serving the frontend from the device.

   > This prevents the device from serving its own frontend while you use the local one.

2. **Start the backend on the device**

```bash
   oakctl app run .
```

> **Note:** If you have multiple devices or the device is on a different network, specify the IP: `oakctl connect <DEVICE_IP>` before running

**In another terminal:**

3. **Find your device IP:**

```bash
   oakctl list
```

4. **Run the frontend locally:**

> Move to the frontend directory

```bash
   npm run build && npm run preview
```

The terminal will display the local URL (e.g., `http://localhost:4173`).

5. **Connect to the device backend:**

   Open the URL shown in terminal and add the WebSocket URL as a parameter:

```
   http://localhost:4173?ws_url=ws://<DEVICE_IP>:8765
```

Or just open the URL and enter `ws://<DEVICE_IP>:8765` in the connection dialog.

______________________________________________________________________

# What's Next

- Explore the `Streams` component props for advanced layouts and controls
- Review [applications directory](../apps) for more advanced frontend examples
- Deploy your application to [Luxonis Hub](https://hub.luxonis.com) for remote access and device management

______________________________________________________________________

# Known issues

The following issues are known to occur in some environments and
have proven workarounds.

### `vite` running out of memory during build

On some machines, the vite build process may run out of memory, especially for larger projects. If this happens, you can try one of the following solutions.

#### Option 1: Increase Node.js Memory Limit

Increase the available memory for Node.js by adjusting the build command:

```
NODE_OPTIONS=--max-old-space-size=8192 npm run build
```

#### Option 2: Limit parallel file operations in Vite

You can also reduce memory pressure by limiting the number of parallel file operations used by Rollup.
This can be done by updating your [vite.config.ts](./raw-stream/frontend/vite.config.ts) file with maxParallelFileOps option:

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      maxParallelFileOps: 10,
      output: {
        format: "esm",
      },
    },
  },
});
```
