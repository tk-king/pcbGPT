import React from "react";
import {
  Accordion,
  Badge,
  Box,
  Flex,
  Paper,
  Stack,
  Text,
  Title,
} from "@mantine/core";

const DetailRow = ({ label, value }) => (
  <Box>
    <Text size="xs" fw={700} c="#607070" tt="uppercase" style={{ letterSpacing: "0.08em" }}>
      {label}
    </Text>
    <Text size="sm" c="#1e2a2a">
      {value || "—"}
    </Text>
  </Box>
);

const PartDetailsPanel = ({ selectedPart, defaultAccordionValues }) => (
  <Box className="parts-panel-shell parts-pane parts-detail-pane">
    {selectedPart ? (
      <Box className="parts-scroll-fill">
        <Stack gap="md">
          <Flex justify="space-between" align="flex-start" gap="md" wrap="wrap">
            <Box>
              <Title order={4}>{selectedPart.name}</Title>
              <Text size="sm" c="#607070">{selectedPart.library}</Text>
            </Box>
            <Flex gap="xs" wrap="wrap">
              <Badge variant="light" color="gray">{selectedPart.pin_count} pins</Badge>
              <Badge variant="light" color="teal">{selectedPart.footprint_count} footprints</Badge>
            </Flex>
          </Flex>

          <DetailRow label="Description" value={selectedPart.description} />

          <Box className="parts-detail-grid">
            <Box className="parts-detail-cell">
              <DetailRow label="Keywords" value={selectedPart.keywords || "—"} />
            </Box>
            <Box className="parts-detail-cell">
              <DetailRow label="Footprint Filters" value={selectedPart.fp_filters} />
            </Box>
            <Box className="parts-detail-cell">
              <DetailRow label="Default Footprint" value={selectedPart.default_footprint} />
            </Box>
            <Box className="parts-detail-cell">
              <DetailRow label="Extends" value={selectedPart.extends} />
            </Box>
            <Box className="parts-detail-cell parts-detail-cell-wide">
              <DetailRow label="Datasheet" value={selectedPart.datasheet} />
            </Box>
          </Box>

          <Accordion
            key={selectedPart.key}
            multiple
            defaultValue={defaultAccordionValues}
            className="parts-accordion"
          >
            <Accordion.Item value="footprints">
              <Accordion.Control>
                Footprints ({selectedPart.footprints?.length || 0})
              </Accordion.Control>
              <Accordion.Panel>
                <Box className="parts-footprint-grid">
                  {(selectedPart.footprints || []).length > 0 ? (
                    selectedPart.footprints.map((footprint) => (
                      <Box key={footprint} className="parts-footprint-item">
                        {footprint}
                      </Box>
                    ))
                  ) : (
                    <Text size="sm" c="#607070">No footprints loaded.</Text>
                  )}
                </Box>
              </Accordion.Panel>
            </Accordion.Item>

            <Accordion.Item value="pins">
              <Accordion.Control>
                Pins ({selectedPart.pins?.length || 0})
              </Accordion.Control>
              <Accordion.Panel>
                <Box className="parts-pin-grid">
                  {(selectedPart.pins || []).map((pin) => (
                    <Paper
                      key={`${selectedPart.key}:${pin.pin_number}`}
                      withBorder
                      radius="md"
                      p="xs"
                      className="parts-pin-card"
                    >
                      <Flex align="baseline" gap="xs" wrap="nowrap">
                        <Text fw={700} size="sm" className="parts-pin-number">
                          {pin.pin_number}
                        </Text>
                        <Text size="sm" c="#4d6665" className="parts-pin-name">
                          {pin.pin_name || pin.pin_display_name || "Unnamed"}
                        </Text>
                      </Flex>
                    </Paper>
                  ))}
                </Box>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </Stack>
      </Box>
    ) : (
      <Flex className="parts-empty-state" align="center" justify="center">
        <Text size="sm" c="#607070">Select a part to inspect its properties.</Text>
      </Flex>
    )}
  </Box>
);

export default PartDetailsPanel;
