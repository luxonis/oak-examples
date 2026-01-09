# Building a Custom Frontend for DepthAI

Build your own React UI to visualize camera streams from OAK devices using the `@luxonis/depthai-viewer-common` library.

## Quick Start

For a quick start you can clone the [raw-stream](./raw-stream) example and edit it to your needs

For a more advanced example with AI inference and WebRTC, see [open-vocabulary-object-detection](./open-vocabulary-object-detection).

______________________________________________________________________

## Building Your Own

### Prepare Your Project

This package is meant to be used inside a React application. We recommend using [Vite](https://vite.dev/guide/) to scaffold your project with the `react-ts` template.

```bash
npm create vite@latest frontend -- --template react-ts
```

### Install Dependencies

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
  "@biomejs/biome": "1.9.4",
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
     "lint": "biome check .",
     "lint:fix": "biome check --write .",
     "preview": "vite preview",
     "styleGen": "panda codegen"
 }
```

See [package.json](./raw-stream/frontend/package.json) for a complete example.

Then install the dependencies:

```bash
npm i
```

### Configure PandaCSS

This library is dependent on our components lib - `@luxonis/common-fe-components`. To use this library you have to use [PandaCSS](https://panda-css.com/).

**Initialize PandaCSS** in your project root:

```bash
npx panda init --postcss
```

**Edit `panda.config.ts`** with the preset from our components lib:

```typescript
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

### Global CSS Setup

Luxonis frontend components rely on PandaCSS layered styles. The default Vite index.css must be replaced.

**Update `index.css`:**

Add this code to an `src/index.css` file imported in the root component of your project:

```css
@layer reset, base, tokens, recipes, utilities;
```

> **Note:** Feel free to remove src/App.css file as we don't need it anymore, and make sure to remove the import from the src/App.tsx file.

### Configure Vite

Your `vite.config.ts` needs the following settings:

#### Relative base path (required for Luxonis Hub)

```typescript
base: "",
```

This makes asset paths relative instead of absolute, which is required when deploying to [Luxonis Hub](https://hub.luxonis.com).

> ⚠️ **Important:** Avoid using paths starting with `/` anywhere in your code (e.g., `/images/logo.png`). Use relative paths instead (e.g., `./images/logo.png` or `images/logo.png`). Absolute paths will break when deployed to Luxonis Hub and cause cryptic errors or blank pages.

#### FoxGlove compatibility

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

> The Vite-generated TypeScript config files may need to be replaced to work with Luxonis packages. In case of build issues, please try replacing them with the following configurations.

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

Use the `Streams` component to display all topics published by your backend:

```tsx
import { Streams } from "@luxonis/depthai-viewer-common";
```

The component automatically renders all streams added via `visualizer.addTopic()` in your Python backend:

```python
# Backend: add a stream topic
visualizer.addTopic("RGB Camera", rgb_output)
```

For more streams customization please check Streams component attributes

### Sending Messages to Backend

You can communicate with your Python backend by registering services and calling them from the frontend.

**Backend** — register a service:

```python
def handle_message(message):
    print("Received:", message)
    return {"status": "ok"}

visualizer.registerService("My Service", handle_message)
```

**Frontend** — call the service:

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
            <Button onClick={handleSendMessage}>Send</Button>
    );
}
```

See [MessageInput.tsx](./raw-stream/frontend/src/MessageInput.tsx) for a working FE example.\
See [main.py](./raw-stream/main.py) custom_service function for a working BE example.

### Styling

Since `@luxonis/common-fe-components` is dependent on PandaCSS it's a good idea to use this package in your project as
well. It's highly recommended to check out [PandaCSS docs](https://panda-css.com/docs/overview/getting-started) and use the
`css()` function imported from `styled-system/css` like it is done in [App.tsx](./raw-stream/frontend/src/App.tsx).

______________________________________________________________________

## Run the Frontend

The FE library automatically connects to `ws://localhost:8765`. If unavailable, a connection dialog will prompt for the URL.

### Peripheral Mode

You need the dependencies installed as described in the [Install-Dependencies](#Install-Dependencies).
Afterward you need to build the frontend in the frontend root directory:

```bash
npm run build
```

Then you can run the backend application with:

```bash
python main.py
```

### Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

#### Local Frontend Development

When developing the frontend, you can run it locally while the backend runs on the device. This avoids rebuilding and redeploying the entire container for every frontend change, saving significant development time.

1. **Start the backend on the device** (as shown above)

#### In another terminal tab

2. **Find your device IP:**

```bash
   oakctl list
```

3. **Run the frontend locally:**

```bash
   cd frontend
   npm run build && npm run preview
```

The terminal will display the local URL (e.g., `http://localhost:4173`).

4. **Connect to the device backend:**

   Open the URL shown in terminal and add the WebSocket URL as a parameter:

```
   http://localhost:4173?ws_url=ws://<DEVICE_IP>:8765
```

Or just open the URL and enter `ws://<DEVICE_IP>:8765` in the connection dialog.

______________________________________________________________________

## Known issues

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
