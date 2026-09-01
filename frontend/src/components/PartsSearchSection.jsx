import React from "react";
import { Alert, Box, Button, Flex, Text, TextInput } from "@mantine/core";
import { IconCircleCheck, IconSearch, IconUpload, IconAlertTriangle } from "@tabler/icons-react";
import SearchPartsList from "./SearchPartsList.jsx";
import PartDetailsPanel from "./PartDetailsPanel.jsx";

const PartsSearchSection = ({
  partIndexStatus,
  query,
  onQueryChange,
  onUploadClick,
  uploadNotice,
  debouncedQuery,
  total,
  loading,
  error,
  results,
  selectedKey,
  page,
  pageCount,
  onSelect,
  onPreviousPage,
  onNextPage,
  selectedPart,
  defaultAccordionValues,
  onReindexRequested = null,
}) => {
  const chroma = partIndexStatus?.chromadb || null;
  const whoosh = partIndexStatus?.whoosh || null;
  const expectedCount = partIndexStatus?.expected_part_count ?? null;
  const needsReindex = Boolean(partIndexStatus?.needs_reindex);
  const modelMismatch =
    Boolean(partIndexStatus?.embedding_model) && partIndexStatus?.embedding_model_match === false;

  const indexWarnings = [];
  if (modelMismatch && chroma) {
    const builtWith = (chroma.embedding_models || []).join(", ") || "(unknown model)";
    indexWarnings.push(
      `The current embedding index was built with ${builtWith}, but "${partIndexStatus.embedding_model}" is selected.`
    );
  }
  if (chroma && whoosh && expectedCount != null) {
    if ((chroma.count ?? 0) !== expectedCount) {
      indexWarnings.push(
        `ChromaDB holds ${(chroma.count ?? 0).toLocaleString()} of ${expectedCount.toLocaleString()} parts.`
      );
    }
    if (!whoosh.index_exists || (whoosh.count ?? 0) !== expectedCount) {
      indexWarnings.push(
        `Text search index holds ${(whoosh.count ?? 0).toLocaleString()} of ${expectedCount.toLocaleString()} parts${
          whoosh.index_exists ? "" : " (missing)"
        }.`
      );
    }
  }

  return (
  <Box className="parts-search-section">
    <Flex className="parts-toolbar" gap="sm" align="center">
      <TextInput
        value={query}
        onChange={(event) => onQueryChange(event.currentTarget.value)}
        placeholder="Search parts by name, type, or function"
        leftSection={<IconSearch size={16} />}
        size="md"
        className="parts-toolbar-search"
        styles={{
          input: {
            backgroundColor: "rgba(255,255,255,0.88)",
            borderColor: "rgba(111, 134, 133, 0.2)",
          },
        }}
      />
      <Button leftSection={<IconUpload size={16} />} onClick={onUploadClick}>
        Create Part
      </Button>
    </Flex>

    <Flex className="parts-index-counts" gap="sm" align="center" wrap="wrap">
      <Text size="xs" c="dimmed">
        Symbols: {(partIndexStatus?.component_count ?? 0).toLocaleString()}
      </Text>
      <Text size="xs" c="dimmed">
        Footprints: {(partIndexStatus?.footprint_count ?? 0).toLocaleString()}
      </Text>
    </Flex>

    {needsReindex && indexWarnings.length > 0 && (
      <Alert
        color="yellow"
        icon={<IconAlertTriangle size={16} />}
        title="Part index needs attention"
        style={{
          // Never shrink or get overlapped by the parts grid below.
          flex: "0 0 auto",
          position: "relative",
          zIndex: 5,
        }}
      >
        <Flex direction="column" gap={6}>
          {indexWarnings.map((warning) => (
            <Text key={warning} size="sm">
              {warning}
            </Text>
          ))}
          <Text size="xs" c="#6a5b20">
            Search results may be incomplete or computed with the wrong embeddings.
          </Text>
          {onReindexRequested && (
            <Button size="xs" variant="light" color="yellow" onClick={onReindexRequested} w="fit-content">
              Reindex now
            </Button>
          )}
        </Flex>
      </Alert>
    )}

    {uploadNotice ? (
      <Alert
        color={uploadNotice.warnings.length > 0 ? "yellow" : "teal"}
        icon={<IconCircleCheck size={16} />}
      >
        <Text size="sm">{uploadNotice.message}</Text>
        {uploadNotice.warnings.map((warning) => (
          <Text key={warning} size="xs" c="#6a5b20">
            {warning}
          </Text>
        ))}
      </Alert>
    ) : null}

    <Flex
      className="parts-modal-grid"
      align="stretch"
      direction={{ base: "column", md: "row" }}
    >
      <Box
        className="parts-modal-column parts-modal-column-left"
        style={{ flex: "0 0 40%", minHeight: 0 }}
      >
        <SearchPartsList
          query={debouncedQuery}
          total={total}
          loading={loading}
          error={error}
          results={results}
          selectedKey={selectedKey}
          page={Math.min(page, pageCount)}
          pageCount={pageCount}
          onSelect={onSelect}
          onPreviousPage={onPreviousPage}
          onNextPage={onNextPage}
        />
      </Box>

      <Box
        className="parts-modal-column parts-modal-column-right"
        style={{ flex: "1 1 auto", minHeight: 0 }}
      >
        <PartDetailsPanel
          selectedPart={selectedPart}
          defaultAccordionValues={defaultAccordionValues}
        />
      </Box>
    </Flex>
  </Box>
  );
};

export default PartsSearchSection;
