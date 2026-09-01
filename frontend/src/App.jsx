import { useState } from "react";
import { AppShell, Box, Button, Flex, Group, Loader, SegmentedControl, Text } from "@mantine/core";
import ChatWindow from "./pages/ChatWindow.jsx";
import { PcbGPTProvider } from "./context/PcbGPTProvider.jsx";
import usePcbGPTContext from "./hooks/usePcbGPTContext.js";
import PythonCodeDisplay from "./components/PythonCodeDisplay.jsx";
import SchematicPdfDisplay from "./components/SchematicPdfDisplay.jsx";
import SessionsSidebar from "./components/SessionsSidebar.jsx";
import DownloadButton from "./components/ui/DownloadButton.jsx";
import useResizableChatWidth from "./hooks/useResizableChatWidth.js";
import useProjectSync from "./hooks/useProjectSync.jsx";
import useAutoSave from "./hooks/useAutoSave.jsx";
import { apiUrl } from "./api/base.js";

const ReconnectOverlay = () => (
  <Box
    style={{
      position: "absolute",
      inset: 0,
      backgroundColor: "rgba(246, 247, 249, 0.9)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 10,
    }}
  >
    <Flex direction="column" align="center">
      <Box style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <img src="/logo_no_background.png" alt="pcbGPT Logo" width={48} height={48} />
        <Text fw={700} size="lg">
          pcbGPT
        </Text>
      </Box>
      <Loader size="sm" color="brand" />
      <Text size="sm" color="dimmed">
        Reconnecting…
      </Text>
    </Flex>
  </Box>
);

const RightPaneToolbar = ({
  rightPaneView,
  onRightPaneViewChange,
  netlistHref,
  projectHref,
  sync,
  syncPath,
}) => (
  <Box
    style={{
      borderBottom: "1px solid rgba(111, 134, 133, 0.14)",
      padding: "12px 14px 10px",
      background:
        "linear-gradient(180deg, rgba(249,251,250,0.98) 0%, rgba(244,248,247,0.92) 100%)",
    }}
  >
    <Flex direction="column" gap={6}>
      <Flex align="center" justify="space-between" gap="sm" wrap="wrap">
        <SegmentedControl
          value={rightPaneView}
          onChange={onRightPaneViewChange}
          size="sm"
          radius="md"
          data={[
            { label: "Python Code", value: "code" },
            { label: "Schematic PDF", value: "pdf" },
          ]}
        />
        <Group gap="xs" justify="flex-end" wrap="wrap">
          <DownloadButton href={netlistHref}>Netlist</DownloadButton>
          <DownloadButton href={projectHref}>KiCad Project</DownloadButton>
        </Group>
      </Flex>
      <Flex align="center" gap="sm" wrap="wrap">
        <Group gap="xs" wrap="wrap">
          <Button
            size="xs"
            variant="light"
            onClick={sync.handleSelectAndSync}
            loading={sync.isSyncing}
            disabled={sync.isSyncing}
            style={{ flexShrink: 0 }}
          >
            Sync project
          </Button>
          <Button
            size="xs"
            variant="light"
            onClick={sync.handleSyncClick}
            loading={sync.isSyncing}
            disabled={
              sync.isSyncing ||
              !sync.canSyncActiveSession
            }
            style={{ flexShrink: 0 }}
          >
            Sync
          </Button>
        </Group>
        <Text
          size="xs"
          c="dimmed"
          title={syncPath || "No sync folder selected"}
          style={{
            minWidth: 0,
            flex: 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            color: "#617170",
          }}
        >
          {syncPath ? `Sync Folder: ${syncPath}` : "No sync folder selected"}
        </Text>
      </Flex>
    </Flex>
  </Box>
);

function AppLayout() {
  const [rightPaneView, setRightPaneView] = useState("code");
  const { containerRef, chatWidthPx, isResizing, startResizing } = useResizableChatWidth();

  const { context, sessionId, isConnected, applyContextPatch, appendAssistantMessage } = usePcbGPTContext();
  const activeSessionId = sessionId || context?.session_id;

  const sync = useProjectSync(activeSessionId, applyContextPatch, appendAssistantMessage, context);

  useAutoSave({
    activeSessionId,
    context,
    dirHandleRef: sync.dirHandleRef,
    dirHandleSessionRef: sync.dirHandleSessionRef,
    dirNameRef: sync.dirNameRef,
    handleEpoch: sync.handleEpoch,
    lastSavedVersionRef: sync.lastSavedVersionRef,
    lastSavedBySessionRef: sync.lastSavedBySessionRef,
  });

  const circuit = context?.circuit;
  const pdfBase64 = context?.schematic_pdf_base64 || null;
  const pdfSrc = pdfBase64 ? `data:application/pdf;base64,${pdfBase64}` : null;
  const syncPath =
    context?.sync_display_path ||
    context?.sync_folder_path ||
    (sync.dirHandleSessionRef.current === activeSessionId ? sync.dirNameRef.current : null);
  const hasNetlist = Boolean(circuit);
  const hasProject = Boolean(context?.kicad_project_path);
  const netlistHref =
    activeSessionId && hasNetlist
      ? apiUrl(`/download/netlist/${activeSessionId}`)
      : undefined;
  const projectHref =
    activeSessionId && hasProject
      ? apiUrl(`/download/project/${activeSessionId}`)
      : undefined;

  return (
    <AppShell padding="0">
      <AppShell.Main
        h="100vh"
        bg="transparent"
        style={{ overflow: "hidden", position: "relative" }}
      >
        <Box
          ref={containerRef}
          w="100%"
          h="100%"
          className="app-panel"
          style={{
            display: "grid",
            gridTemplateColumns: `240px ${chatWidthPx}px 6px 1fr`,
            alignItems: "stretch",
            background:
              "linear-gradient(180deg, rgba(252,253,253,0.94) 0%, rgba(246,249,248,0.96) 100%)",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          <SessionsSidebar />
          <Box
            style={{
              minWidth: 260,
              minHeight: 0,
              display: "flex",
              overflow: "hidden",
              height: "100%",
              borderRight: "1px solid rgba(111, 134, 133, 0.14)",
            }}
          >
            <ChatWindow />
          </Box>
          <Box
            role="separator"
            aria-orientation="vertical"
            onMouseDown={startResizing}
            style={{
              width: 6,
              cursor: "col-resize",
              background: isResizing
                ? "linear-gradient(180deg, #6a9f9e 0%, #417776 100%)"
                : "linear-gradient(180deg, rgba(188, 201, 200, 0.45) 0%, rgba(188, 201, 200, 0.18) 100%)",
            }}
          />
          <Box
            style={{
              minWidth: 260,
              minHeight: 0,
              display: "flex",
              overflow: "hidden",
              height: "100%",
              pointerEvents: isResizing ? "none" : "auto",
            }}
          >
            <Flex direction="column" w="100%" h="100%" style={{ minHeight: 0 }}>
              <RightPaneToolbar
                rightPaneView={rightPaneView}
                onRightPaneViewChange={setRightPaneView}
                netlistHref={netlistHref}
                projectHref={projectHref}
                sync={sync}
                syncPath={syncPath}
              />
              <Box style={{ flexGrow: 1, minHeight: 0, overflow: "hidden" }}>
                {rightPaneView === "code" ? (
                  <PythonCodeDisplay circuit={circuit} />
                ) : (
                  <SchematicPdfDisplay pdfSrc={pdfSrc} />
                )}
              </Box>
            </Flex>
          </Box>
        </Box>
        {!isConnected && <ReconnectOverlay />}
      </AppShell.Main>
    </AppShell>
  );
}

function App() {
  return (
    <PcbGPTProvider>
      <AppLayout />
    </PcbGPTProvider>
  );
}

export default App;
