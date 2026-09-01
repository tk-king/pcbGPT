import React from "react";
import { Box, Modal, Stack, Tabs } from "@mantine/core";
import { IconCpu, IconSearch, IconServer, IconSettings } from "@tabler/icons-react";
import PartsSearchSection from "./PartsSearchSection.jsx";
import KiCadSettingsSection from "./KiCadSettingsSection.jsx";
import UploadPartModal from "./UploadPartModal.jsx";
import GenerationSettingsSection from "./GenerationSettingsSection.jsx";
import ProviderSettingsSection from "./ProviderSettingsSection.jsx";
import usePartsSearch from "../hooks/usePartsSearch.js";
import useKicadSettings from "../hooks/useKicadSettings.js";

const SearchPartsModal = ({
  opened,
  onClose,
  providers = [],
  customProviderSettings = null,
  onSaveCustomProvider = null,
  onUpdateProvider = null,
  onDeleteProvider = null,
  onRefreshProviderModels = null,
  onSaveModelRequestKwargs = null,
  onPartIndexStatusChange = null,
  initialTab = "parts",
  systemSettings,
  onGenerationModelChange,
  onValidationModelChange,
  onValidationToggle,
  isTurnPending = false,
}) => {
  const [activeTab, setActiveTab] = React.useState(initialTab);
  const [uploadOpened, setUploadOpened] = React.useState(false);
  const [uploadNotice, setUploadNotice] = React.useState(null);

  React.useEffect(() => {
    if (opened) {
      setActiveTab(initialTab);
    }
  }, [initialTab, opened]);

  React.useEffect(() => {
    if (!opened) {
      setUploadOpened(false);
      setUploadNotice(null);
    }
  }, [opened]);

  const partsSearch = usePartsSearch({ opened, onPartIndexStatusChange });
  const kicad = useKicadSettings({
    opened,
    partIndexStatus: partsSearch.partIndexStatus,
    onPartIndexStatusChange,
    onReindexed: partsSearch.bumpReload,
  });

  const handleEmbeddingModelChange = kicad.setEmbeddingModel;

  // Reindex requested from the Parts tab: jump to the KiCad tab so the
  // progress bar is visible, then start the same reindex flow.
  const handleReindexFromParts = React.useCallback(() => {
    setActiveTab("settings");
    kicad.handleReindex();
  }, [kicad]);

  const handleUploadSuccess = React.useCallback(
    (nextPayload) => {
      const firstComponent = nextPayload?.components?.[0] || null;
      setUploadNotice({
        message: nextPayload?.message || "Part uploaded.",
        warnings: Array.isArray(nextPayload?.warnings) ? nextPayload.warnings : [],
      });
      partsSearch.focusOnPart({
        name: firstComponent?.name,
        key: firstComponent?.key,
      });
      partsSearch.refreshPartIndexStatus().catch(() => {});
      partsSearch.bumpReload();
    },
    [partsSearch],
  );

  return (
    <>
      <Modal
        opened={opened}
        onClose={onClose}
        title="Settings"
        centered
        size="80%"
        classNames={{
          content: "parts-modal-content",
          header: "parts-modal-header",
          body: "parts-modal-body",
        }}
        styles={{
          // Inline styles win over any stylesheet ordering, keeping the modal
          // at a fixed height so tab content (e.g. expanding accordions)
          // never resizes it.
          content: {
            height: "min(97vh, 1600px)",
            maxHeight: "min(97vh, 1600px)",
            display: "flex",
            flexDirection: "column",
          },
          body: {
            flex: "1 1 auto",
            minHeight: 0,
            overflow: "hidden",
          },
        }}
      >
        <Box className="parts-modal-shell">
          <Stack gap="md" className="parts-modal-stack" mt="md">
            <Tabs value={activeTab} onChange={setActiveTab} className="parts-tabs-section">
              <Tabs.List>
                <Tabs.Tab value="providers" leftSection={<IconServer size={16} />}>
                  Providers
                </Tabs.Tab>
                <Tabs.Tab value="parts" leftSection={<IconSearch size={16} />}>
                  Parts
                </Tabs.Tab>
                <Tabs.Tab value="generation" leftSection={<IconCpu size={16} />}>
                  Generation Settings
                </Tabs.Tab>
                <Tabs.Tab value="settings" leftSection={<IconSettings size={16} />}>
                  KiCad Settings
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="providers" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
                <ProviderSettingsSection
                  providers={providers}
                  onUpdateProvider={onUpdateProvider}
                  onDeleteProvider={onDeleteProvider}
                  onSaveCustomProvider={onSaveCustomProvider}
                />
              </Tabs.Panel>

              <Tabs.Panel value="parts" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
                <PartsSearchSection
                  partIndexStatus={partsSearch.partIndexStatus}
                  query={partsSearch.query}
                  onQueryChange={partsSearch.setQuery}
                  onUploadClick={() => setUploadOpened(true)}
                  uploadNotice={uploadNotice}
                  debouncedQuery={partsSearch.debouncedQuery}
                  total={partsSearch.total}
                  loading={partsSearch.loading}
                  error={partsSearch.error}
                  results={partsSearch.results}
                  selectedKey={partsSearch.selectedKey}
                  page={partsSearch.page}
                  pageCount={partsSearch.pageCount}
                  onSelect={partsSearch.setSelectedKey}
                  onPreviousPage={() => partsSearch.setPage((current) => Math.max(1, current - 1))}
                  onNextPage={() => partsSearch.setPage((current) => Math.min(partsSearch.pageCount, current + 1))}
                  selectedPart={partsSearch.selectedPart}
                  defaultAccordionValues={partsSearch.defaultAccordionValues}
                  onReindexRequested={handleReindexFromParts}
                />
              </Tabs.Panel>

              <Tabs.Panel value="generation" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
                <GenerationSettingsSection
                  systemSettings={systemSettings}
                  onGenerationModelChange={onGenerationModelChange}
                  onValidationModelChange={onValidationModelChange}
                  onValidationToggle={onValidationToggle}
                  providers={providers}
                  customProviderSettings={customProviderSettings}
                  onSaveCustomProvider={onSaveCustomProvider}
                  onRefreshProviderModels={onRefreshProviderModels}
                  onSaveModelRequestKwargs={onSaveModelRequestKwargs}
                  isTurnPending={isTurnPending}
                />
              </Tabs.Panel>

              <Tabs.Panel value="settings" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
                <KiCadSettingsSection
                  embeddingModel={kicad.embeddingModel}
                  onEmbeddingModelChange={handleEmbeddingModelChange}
                  kicadPaths={kicad.kicadPaths}
                  kicadSymbolPath={kicad.kicadSymbolPath}
                  kicadFootprintPath={kicad.kicadFootprintPath}
                  kicadModelPath={kicad.kicadModelPath}
                  onSymbolPathChange={kicad.onSymbolPathChange}
                  onFootprintPathChange={kicad.onFootprintPathChange}
                  onModelPathChange={kicad.onModelPathChange}
                  kicadChecking={kicad.kicadChecking}
                  kicadReindexing={kicad.kicadReindexing}
                  kicadError={kicad.kicadError}
                  kicadNotice={kicad.kicadNotice}
                  reindexProgress={kicad.reindexProgress}
                  onCheck={kicad.handleCheck}
                  onReindex={kicad.handleReindex}
                  providers={providers}
                  customProvider={customProviderSettings}
                  onSaveCustomProvider={onSaveCustomProvider}
                />
              </Tabs.Panel>
            </Tabs>
          </Stack>
        </Box>
      </Modal>

      <UploadPartModal
        opened={uploadOpened}
        onClose={() => setUploadOpened(false)}
        onUploaded={handleUploadSuccess}
      />
    </>
  );
};

export default SearchPartsModal;
