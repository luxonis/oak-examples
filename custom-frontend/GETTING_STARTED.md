# Building a Custom Frontend for DepthAI

Build your own React UI to visualize camera streams from OAK devices using the `@luxonis/depthai-viewer-common` library.

## Quick Start

For a quick start you can clone the [raw-stream](./raw-stream) example and edit it to your needs

For a more advanced example with AI inference and WebRTC, see [open-vocabulary-object-detection](./open-vocabulary-object-detection).

______________________________________________________________________

## Building Your Own

### Prepare Your Project

This package is meant to be used inside a React application. We recommend using [Vite](https://vite.dev/guide/) to scaffold your project with the `react-ts` template.

### Install Dependencies

Your `package.json` needs the following dependencies and scripts:

**Dependencies:**

```json
"dependencies": {
  "@luxonis/depthai-viewer-common": "^1.6.2",
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router": "^7.5.0"
},
"devDependencies": {
  "@pandacss/dev": "^0.53.0",
  "@vitejs/plugin-react": "^4.3.4",
  "typescript": "~5.7.2",
  "vite": "^6.3.1"
}
```

**Scripts** (required for PandaCSS codegen):

```json
"scripts": {
    "prepare": "panda coden",
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "biome check .",
    "lint:fix": "biome check --write .",
    "preview": "vite preview"
},
```

See [package.json](./raw-stream/frontend/package.json) for a complete example.

After setting up your `package.json`, run:

```bash
npm install
```

### Configure PandaCSS

This library is dependent on our components lib - `@luxonis/common-fe-components`. To use this library you have to
use [PandaCSS](https://panda-css.com/). You also have to import preset from our components lib.
See [panda.config.ts](./raw-stream/frontend/panda.config.ts).

### Configure Vite

Your `vite.config.ts` needs specific settings for [FoxGlove](https://foxglove.dev/) compatibility and ESM workers:

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

### Import Styles

In your application entrypoint, import styles in this order:

```typescript
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/common-fe-components/styles';
import '@luxonis/depthai-pipeline-lib/styles';
```

See [main.tsx](./raw-stream/frontend/src/main.tsx) for a complete example.

### Configure Routing

To access your app via the `luxonis.app` domain, you need to set the `basename` of your `BrowserRouter` to include the base path and app version from the URL.

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

## Usage

The library automatically connects to `ws://localhost:8765`. If unavailable, a connection dialog will prompt for the URL.

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
    
      Send
    
  );
}
```

See [MessageInput.tsx](./raw-stream/frontend/src/MessageInput.tsx) for a working FE example.\
See [main.py](./raw-stream/main.py) custom_service function for a working BE example.

### Styling

Since `@luxonis/common-fe-components` is dependent on PandaCSS it's a good idea to use this package in your project as
well. It's highly recommended to check out [PandaCSS docs](https://panda-css.com/docs/overview/getting-started) and use the
`css()` function imported from `styled-system/css/css.mjs` like it is done in [App.tsx](./raw-stream/frontend/src/App.tsx).

______________________________________________________________________

## Known issues

### `vite` running out of memory during build

Depending on your machine, you might run into `vite` running out of memory during build. To fix this, try increasing the
Node.js memory limit by modifying your build command:

```
NODE_OPTIONS=--max-old-space-size=8192 npm run build
```
