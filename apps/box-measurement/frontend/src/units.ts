// The backend reports and accepts distances in millimetres; the UI shows
// centimetres with one decimal, i.e. whole millimetres.
const MM_PER_CM = 10;

export const mmToCm = (mm: number) => mm / MM_PER_CM;

/** Converts to whole millimetres, the resolution of the UI. */
export const cmToMm = (cm: number) => Math.round(cm * MM_PER_CM);

/** Rounds centimetres to one decimal, i.e. to whole millimetres. */
export const roundCmToMm = (cm: number) => mmToCm(cmToMm(cm));
