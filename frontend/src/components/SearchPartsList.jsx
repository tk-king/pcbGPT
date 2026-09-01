import React from "react";
import {
  Box,
  Button,
  Divider,
  Flex,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";

const SearchPartsList = ({
  query,
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
}) => (
  <Box className="parts-panel-shell parts-pane">
    <Flex direction="column" className="parts-list-layout" gap="sm">
      <Box>
        <Flex justify="space-between" align="center" gap="sm">
          <Box>
            <Title order={6}>Results</Title>
            <Text size="xs" c="#607070">
              {total.toLocaleString()} parts {query ? `for "${query}"` : "available"}
            </Text>
          </Box>
          {loading ? <Loader size="sm" color="gray" /> : null}
        </Flex>
        <Divider mt="sm" />
      </Box>
      <Box className="parts-scroll-fill">
        <Stack gap="xs">
          {error ? (
            <Text size="sm" c="red">{error}</Text>
          ) : null}
          {!error && results.length === 0 && !loading ? (
            <Text size="sm" c="#607070">No parts found.</Text>
          ) : null}
          {results.map((part) => {
            const isActive = part.key === selectedKey;
            return (
              <button
                key={part.key}
                type="button"
                className={isActive ? "parts-list-item parts-list-item-active" : "parts-list-item"}
                onClick={() => onSelect(part.key)}
              >
                <Text fw={700} size="sm" ta="left">{part.name}</Text>
                <Text size="xs" c="#607070" ta="left">{part.library}</Text>
                <Text size="xs" c="#4d6665" lineClamp={2} ta="left">
                  {part.description || "No description"}
                </Text>
              </button>
            );
          })}
        </Stack>
      </Box>
      <Flex justify="space-between" align="center" gap="sm">
        <Text size="xs" c="#607070">
          Page {page} of {pageCount}
        </Text>
        <Flex gap="xs">
          <Button
            variant="default"
            size="xs"
            onClick={onPreviousPage}
            disabled={page <= 1 || loading}
          >
            Previous
          </Button>
          <Button
            variant="default"
            size="xs"
            onClick={onNextPage}
            disabled={page >= pageCount || loading}
          >
            Next
          </Button>
        </Flex>
      </Flex>
    </Flex>
  </Box>
);

export default SearchPartsList;
