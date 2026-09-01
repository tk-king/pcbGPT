import { Box, Stack, Switch } from "@mantine/core";
import ModelPicker from "./modelPicker/index.jsx";

const GenerationSettingsSection = ({
  systemSettings,
  onGenerationModelChange,
  onValidationModelChange,
  onValidationToggle,
  providers,
  customProviderSettings,
  onSaveCustomProvider,
  onRefreshProviderModels,
  onSaveModelRequestKwargs,
  isTurnPending,
}) => (
  <Box
    style={{
      flex: 1,
      overflowY: "auto",
      padding: "0.75rem 0.125rem 1rem",
    }}
  >
    <Stack gap="md">
      <ModelPicker
        label="Generation Model"
        providers={providers}
        value={systemSettings.generationModel}
        onChange={onGenerationModelChange}
        customProvider={customProviderSettings}
        onSaveCustomProvider={onSaveCustomProvider}
        onRefreshProviderModels={onRefreshProviderModels}
        onSaveModelRequestKwargs={onSaveModelRequestKwargs}
        disabled={isTurnPending}
        styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2 } }}
      />
      <Switch
        label="Validation"
        size="sm"
        checked={systemSettings.validationEnabled}
        onChange={(event) => onValidationToggle(event.currentTarget.checked)}
        disabled={isTurnPending}
        styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13 } }}
      />
      <ModelPicker
        label="Validation Model"
        providers={providers}
        value={systemSettings.validationModel}
        onChange={onValidationModelChange}
        customProvider={customProviderSettings}
        onSaveCustomProvider={onSaveCustomProvider}
        onRefreshProviderModels={onRefreshProviderModels}
        onSaveModelRequestKwargs={onSaveModelRequestKwargs}
        disabled={isTurnPending || !systemSettings.validationEnabled}
        styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2 } }}
      />
    </Stack>
  </Box>
);

export default GenerationSettingsSection;
