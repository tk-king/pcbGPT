import { Box, Button, Flex, Loader, Progress, Stack, Text, TextInput } from "@mantine/core";
import { IconCircleCheck, IconCircleX, IconRefresh } from "@tabler/icons-react";
import ModelPicker from "./modelPicker/index.jsx";

const getKicadSymbolValid = (paths) => (
  paths?.kicad_symbol_valid ?? paths?.symbol_path_valid ?? null
);

const getKicadFootprintValid = (paths) => (
  paths?.kicad_footprint_valid ?? paths?.footprint_path_valid ?? null
);

const getKicadModelValid = (paths) => (
  paths?.kicad_model_valid ?? paths?.model_path_valid ?? null
);

const KicadConfigPanel = ({
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
  <Stack gap="md">
    <ModelPicker
      label="Component embedding model"
      value={embeddingModel}
      onChange={onEmbeddingModelChange}
      providers={providers}
      customProvider={customProvider}
      onSaveCustomProvider={onSaveCustomProvider}
      disabled={kicadReindexing}
      styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2 } }}
    />
    <TextInput
      size="xs"
      label="KiCad symbol path"
      placeholder="Leave empty to auto-detect"
      value={kicadSymbolPath}
      onChange={(e) => onSymbolPathChange(e.currentTarget.value)}
      disabled={kicadChecking || kicadReindexing}
      rightSection={getKicadSymbolValid(kicadPaths) === true ? <IconCircleCheck size={16} color="var(--mantine-color-teal-6)" /> : getKicadSymbolValid(kicadPaths) === false ? <IconCircleX size={16} color="var(--mantine-color-red-6)" /> : null}
      styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2, marginBottom: 4 } }}
    />
    <TextInput
      size="xs"
      label="KiCad footprint path"
      placeholder="Leave empty to auto-detect"
      value={kicadFootprintPath}
      onChange={(e) => onFootprintPathChange(e.currentTarget.value)}
      disabled={kicadChecking || kicadReindexing}
      rightSection={getKicadFootprintValid(kicadPaths) === true ? <IconCircleCheck size={16} color="var(--mantine-color-teal-6)" /> : getKicadFootprintValid(kicadPaths) === false ? <IconCircleX size={16} color="var(--mantine-color-red-6)" /> : null}
      styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2, marginBottom: 4 } }}
    />
    <TextInput
      size="xs"
      label="KiCad 3D models path"
      placeholder="Leave empty to auto-detect"
      value={kicadModelPath}
      onChange={(e) => onModelPathChange(e.currentTarget.value)}
      disabled={kicadChecking || kicadReindexing}
      rightSection={getKicadModelValid(kicadPaths) === true ? <IconCircleCheck size={16} color="var(--mantine-color-teal-6)" /> : getKicadModelValid(kicadPaths) === false ? <IconCircleX size={16} color="var(--mantine-color-red-6)" /> : null}
      styles={{ label: { color: "#607070", fontWeight: 700, fontSize: 13, lineHeight: 1.2, marginBottom: 4 } }}
    />
    {reindexProgress && (kicadReindexing || reindexProgress.status === "completed" || reindexProgress.status === "failed") && (
      <Box>
        <Flex justify="space-between" align="center" gap="sm" mb={4}>
          <Text size="xs" c="dimmed">
            {reindexProgress.message || "Reindexing"}
          </Text>
          <Text size="xs" c="dimmed">
            {Math.round(reindexProgress.progress || 0)}%
          </Text>
        </Flex>
        <Progress
          value={reindexProgress.progress || 0}
          size="sm"
          radius="xl"
          color={reindexProgress.status === "failed" ? "red" : "brand"}
          animated={kicadReindexing}
        />
      </Box>
    )}
    {kicadNotice && (
      <Text size="xs" c="teal">
        {kicadNotice}
      </Text>
    )}
    {kicadError && (
      <Text size="xs" c="red">
        {kicadError}
      </Text>
    )}
    <Flex gap="xs" direction={{ base: "column", sm: "row" }}>
      <Button
        size="xs"
        onClick={onCheck}
        disabled={kicadChecking || kicadReindexing}
        fullWidth
      >
        {kicadChecking ? (
          <Flex gap="xs" align="center">
            <Loader size="xs" color="white" />
            Checking…
          </Flex>
        ) : (
          "Check paths"
        )}
      </Button>
      <Button
        size="xs"
        leftSection={kicadReindexing ? <Loader size="xs" /> : <IconRefresh size={14} />}
        onClick={onReindex}
        disabled={kicadChecking || kicadReindexing}
        fullWidth
      >
        {kicadReindexing ? "Reindexing…" : "Reindex"}
      </Button>
    </Flex>
  </Stack>
);

export default KicadConfigPanel;
