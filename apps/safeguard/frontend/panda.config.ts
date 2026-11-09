import { pandaPreset } from "@luxonis/common-fe-components";
import { defineConfig } from "@pandacss/dev";

export default defineConfig({
    presets: [pandaPreset],
    preflight: true,
    include: ["./src/**/*.{ts,tsx}"],
    exclude: [],
    jsxFramework: "react",
    outdir: "styled-system",
    forceConsistentTypeExtension: true,
});
