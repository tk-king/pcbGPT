import { Box } from "@mantine/core";
import KicadConfigPanel from "./KicadConfigPanel.jsx";

const KiCadSettingsSection = ({
  embeddingModel,
  onEmbeddingModelChange,
  kicadPaths,
  kicadSymbolPath,
  kicadFootprintPath,
  kicadModelPath,
  onSymbolPathChange,
  onFootprintPathChange,
  onModelPathChange,
  kicadChecking,
  kicadReindexing,
  kicadError,
  kicadNotice,
  reindexProgress,
  onCheck,
  onReindex,
  providers,
  customProvider,
  onSaveCustomProvider,
}) => (
  <Box
    style={{
      flex: 1,
      overflowY: "auto",
      padding: "0.75rem 0.125rem 1rem",
    }}
  >
    <KicadConfigPanel
      embeddingModel={embeddingModel}
      onEmbeddingModelChange={onEmbeddingModelChange}
      kicadPaths={kicadPaths}
      kicadSymbolPath={kicadSymbolPath}
      kicadFootprintPath={kicadFootprintPath}
      kicadModelPath={kicadModelPath}
      onSymbolPathChange={onSymbolPathChange}
      onFootprintPathChange={onFootprintPathChange}
      onModelPathChange={onModelPathChange}
      kicadChecking={kicadChecking}
      kicadReindexing={kicadReindexing}
      kicadError={kicadError}
      kicadNotice={kicadNotice}
      reindexProgress={reindexProgress}
      onCheck={onCheck}
      onReindex={onReindex}
      providers={providers}
      customProvider={customProvider}
      onSaveCustomProvider={onSaveCustomProvider}
    />
  </Box>
);

export default KiCadSettingsSection;
