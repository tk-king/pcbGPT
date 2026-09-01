import { render } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import pcbGptTheme from "../theme/theme.js";

// Renders UI wrapped in the app's MantineProvider so Mantine components
// work outside of <App />.
export function renderUi(ui, options = {}) {
  return render(<MantineProvider theme={pcbGptTheme}>{ui}</MantineProvider>, options);
}

export * from "@testing-library/react";
