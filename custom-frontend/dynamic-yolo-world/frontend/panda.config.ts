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
