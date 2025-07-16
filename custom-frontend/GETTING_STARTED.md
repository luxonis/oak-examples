## Get started with your own custom Front-End

### Prepare your project

This package is meant to be used inside a React application.
We highly recommend using [Vite](https://vite.dev/guide/) to scaffold your project using `react-ts` template.

### Install dependencies

To use `@luxonis/depthai-viewer-common` library simply install it using `npm install @luxonis/depthai-viewer-common` (or
any other package manager you prefer).

This library is dependent on our components lib - `@luxonis/common-fe-components`. To use this library you have to
use [PandaCSS](https://panda-css.com/). You also have to import preset from our components lib.
See [panda.config.ts](./panda.config.ts).

### Update `window.d.ts`

Visualizer lib requires `__basepath` window variable to be defined.
If you're using TypeScript edit your `window.d.ts` file like this:

```
declare global {
    interface Window {
        __basePath: string;
    }
}

export {};
```

### Edit `vite.config.ts`

To use this lib, you also have to edit `vite.config.ts` for everything to work properly:

- For [FoxGlove](https://foxglove.dev/) to work, we have to define globals like this:

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

Example vite.config.ts can be found in [this repository](./vite.config.ts).

### Import library styles

In your application entrypoint (e.g. `main.tsx`) import the following styles:

```
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/common-fe-components/styles';
import '@luxonis/depthai-pipeline-lib/styles';
```

### Insert @luxonis/depthai-viewer-common component

To use streams from our library, best aprpoach is to use `<DepthAIEntrypoint />` component (see [App.tsx](./src/App.tsx)
for example usage)

## Usage

`@luxonis/depthai-viewer-common` expects to be running on the device directly. This means that it will automatically try
to connect to `ws://localhost:8765`.
If this URL isn't available, you will have to enter a connection URL manually.

### Styling

Since `@luxonis/common-fe-components` if dependent on PandaCSS it's a good idea to use this package in your project as
well.
It's highly recommended to check out [PandaCSS docs](https://panda-css.com/docs/overview/getting-started).

TLDR: use `css()` function imported from `styled-system/css/css.mjs` like we do in [App.tsx](./src/App.tsx).

## Known issues

### `vite` running out of memory during build

Depending on your machine, you might run into `vite` running out of memory during build. To fix this, try increasing the
Node.js memory limit by modifying your build command:

```
NODE_OPTIONS=--max-old-space-size=8192 npm run build
```
