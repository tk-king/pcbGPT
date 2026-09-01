import { ActionIcon, Box, Button, Group, Menu, ScrollArea, Text, TextInput, Tooltip } from "@mantine/core";
import { IconAdjustments, IconCheck, IconChevronLeft, IconRefresh } from "@tabler/icons-react";
import { formatUpdatedAt } from "./modelValue.js";

// Dropdown panel listing a provider's models, with search + refresh +
// per-model request-kwargs configuration entry points.
const ProviderModelsView = ({
  activeProvider,
  modelSearch,
  onModelSearchChange,
  filteredModels,
  selectedValue,
  onSelectModel,
  onOpenModelSettings,
  canConfigureModels,
  isRefreshingModels,
  onRefresh,
  error,
  onBack,
}) => (
  <>
    <Box px="xs" py={6}>
      <Group justify="space-between" wrap="nowrap">
        <Button
          variant="subtle"
          size="compact-xs"
          leftSection={<IconChevronLeft size={14} />}
          onClick={onBack}
        >
          {activeProvider?.providerName || "Provider"}
        </Button>
        <Tooltip label="Refresh models from provider">
          <ActionIcon
            variant="subtle"
            size="sm"
            loading={isRefreshingModels}
            onClick={onRefresh}
            aria-label="Refresh provider models"
          >
            <IconRefresh size={14} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Box>
    <Text px="xs" pb={6} size="xs" c="#607070">
      {isRefreshingModels
        ? "Checking provider for new models…"
        : `${activeProvider?.models?.length || 0} models · ${formatUpdatedAt(activeProvider?.updatedAt)}`}
    </Text>
    <Menu.Divider />
    {error ? (
      <Text px="xs" pt={6} size="xs" c="red">{error}</Text>
    ) : null}
    <Box px="xs" py={6}>
      <TextInput
        size="xs"
        placeholder="Search models"
        value={modelSearch}
        onChange={(event) => onModelSearchChange(event.currentTarget.value)}
      />
    </Box>
    <Menu.Divider />
    <ScrollArea.Autosize mah="min(280px, calc(100dvh - 190px))" scrollbarSize={6}>
      {filteredModels.length > 0 ? (
        filteredModels.map((model) => {
          const modelValue = `${activeProvider.providerName}.${model.id}`;
          return (
            <Menu.Item
              key={modelValue}
              onClick={() => onSelectModel(modelValue)}
              rightSection={(
                <Group gap={6} wrap="nowrap">
                  {modelValue === selectedValue ? <IconCheck size={14} /> : null}
                  {canConfigureModels ? (
                    <Tooltip label="Configure request kwargs" position="left">
                      <Box
                        component="span"
                        role="button"
                        tabIndex={0}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          onOpenModelSettings(model);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            event.stopPropagation();
                            onOpenModelSettings(model);
                          }
                        }}
                        style={{ display: "inline-flex", color: "#607070" }}
                      >
                        <IconAdjustments size={14} />
                      </Box>
                    </Tooltip>
                  ) : null}
                </Group>
              )}
            >
              {model.name || model.id}
            </Menu.Item>
          );
        })
      ) : (
        <Box px="xs" py="sm">
          <Text size="xs" c="#607070">No models found.</Text>
        </Box>
      )}
    </ScrollArea.Autosize>
  </>
);

export default ProviderModelsView;
