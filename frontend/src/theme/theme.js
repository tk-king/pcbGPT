// Shared Mantine theme for pcbGPT.
// Consumed by <MantineProvider> in main.jsx.

export const FONT_FAMILY =
  '"Avenir Next", Inter, "Segoe UI", system-ui, -apple-system, sans-serif';

const pcbGptTheme = {
  primaryColor: "brand",
  defaultRadius: "md",
  fontFamily: FONT_FAMILY,
  headings: {
    fontFamily: FONT_FAMILY,
  },
  colors: {
    brand: [
      "#edf3f3",
      "#d7e6e6",
      "#c1d9d9",
      "#abcccc",
      "#95bfbf",
      "#7fb2b1",
      "#6a9f9e",
      "#568b8a",
      "#417776",
      "#316b6a",
    ],
  },
};

export default pcbGptTheme;
