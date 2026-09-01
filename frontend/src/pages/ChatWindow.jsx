import React from "react";
import { Box, Flex, ScrollArea } from "@mantine/core";
import useAutoScroll from "../hooks/useAutoScroll.js";
import { getSetupIssues } from "../utils/setupIssues.js";
import { getActivityState } from "../utils/chatActivity.js";
import usePcbGPTContext from "../hooks/usePcbGPTContext.js";
import ChatMessage from "../components/ChatMessage.jsx";
import ActivityIndicator from "../components/chat/ActivityIndicator.jsx";
import SearchPartsModal from "../components/SearchPartsModal.jsx";
import ChatHeader from "../components/ChatHeader.jsx";
import ChatComposer from "../components/ChatComposer.jsx";
import TaskFlowPanel from "../components/TaskFlowPanel.jsx";

const ChatWindow = () => {
  const {
    events,
    sendMessage,
    cancelChat,
    chatboxInput,
    setChatboxInput,
    metrics,
    context,
    isConnected,
    isTurnPending,
    providers,
    systemSettings,
    updateSystemSetting,
    customProviderSettings,
    saveCustomProvider,
    refreshProviderModels,
    updateProvider,
    deleteProvider,
    saveModelRequestKwargs,
    partIndexStatus,
    partIndexStatusError,
    updatePartIndexStatus,
  } = usePcbGPTContext();

  const activityState = React.useMemo(
    () => getActivityState(events, isConnected, isTurnPending),
    [events, isConnected, isTurnPending],
  );
  const setupIssues = React.useMemo(
    () => getSetupIssues({ systemSettings, partIndexStatus, partIndexStatusError }),
    [partIndexStatus, partIndexStatusError, systemSettings],
  );
  const isSetupComplete = setupIssues.length === 0;
  const [partsModalOpened, setPartsModalOpened] = React.useState(false);
  const [settingsModalInitialTab, setSettingsModalInitialTab] = React.useState("parts");

  const viewportRef = useAutoScroll([events, activityState]);

  const openSettingsModal = React.useCallback((tab = "generation") => {
    setSettingsModalInitialTab(tab);
    setPartsModalOpened(true);
  }, []);
  const handleSend = React.useCallback(() => {
    if (isTurnPending || !isConnected || !isSetupComplete) return;
    sendMessage(chatboxInput);
  }, [chatboxInput, isTurnPending, isConnected, isSetupComplete, sendMessage]);

  const handleStop = React.useCallback(() => {
    cancelChat();
  }, [cancelChat]);

  return (
    <Flex
      direction="column"
      h="100%"
      w="100%"
      style={{
        minHeight: 0,
        overflow: "hidden",
        background:
          "linear-gradient(180deg, rgba(251,252,252,0.9) 0%, rgba(246,249,248,0.88) 100%)",
      }}
    >
      <ChatHeader
        systemSettings={systemSettings}
        metrics={metrics}
        onOpenSettings={() => openSettingsModal("generation")}
      />
      <SearchPartsModal
        opened={partsModalOpened}
        onClose={() => setPartsModalOpened(false)}
        initialTab={settingsModalInitialTab}
        providers={providers}
        customProviderSettings={customProviderSettings}
        onSaveCustomProvider={saveCustomProvider}
        onUpdateProvider={updateProvider}
        onDeleteProvider={deleteProvider}
        onRefreshProviderModels={refreshProviderModels}
        onSaveModelRequestKwargs={saveModelRequestKwargs}
        onPartIndexStatusChange={updatePartIndexStatus}
        systemSettings={systemSettings}
        onGenerationModelChange={(value) => updateSystemSetting("generationModel", value)}
        onValidationModelChange={(value) => updateSystemSetting("validationModel", value)}
        onValidationToggle={(checked) => updateSystemSetting("validationEnabled", checked)}
        isTurnPending={isTurnPending}
      />
      <ScrollArea
        className="app-scroll-area"
        scrollbarSize={6}
        style={{ flexGrow: 1, minHeight: 0 }}
        viewportRef={viewportRef}
        viewportProps={{ style: { height: "100%" } }}
      >
        <Box px="md" pt="md" pb="md" style={{ width: "100%" }}>
          {events &&
            events.map((event) => (
              <ChatMessage event={event} key={event.id} />
            ))}
          <ActivityIndicator state={activityState} />
        </Box>
      </ScrollArea>
      <TaskFlowPanel context={context} />
      <ChatComposer
        chatboxInput={chatboxInput}
        onInputChange={setChatboxInput}
        onSend={handleSend}
        onStop={handleStop}
        isTurnPending={isTurnPending}
        isConnected={isConnected}
        isSetupComplete={isSetupComplete}
        setupIssues={setupIssues}
        onOpenSettings={() => openSettingsModal("generation")}
        onOpenParts={() => openSettingsModal("parts")}
      />
    </Flex>
  );
};

export default ChatWindow;
