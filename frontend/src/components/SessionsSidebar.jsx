import React from "react";
import { Box, Button, Divider, ScrollArea, Stack, Text } from "@mantine/core";
import usePcbGPTContext from "../hooks/usePcbGPTContext.js";
import SessionItem from "./sessions/SessionItem.jsx";

const SessionsSidebar = () => {
  const {
    sessions,
    sessionId,
    selectSession,
    createNewSession,
    renameSession,
    deleteSession,
  } = usePcbGPTContext();
  const [editingSessionId, setEditingSessionId] = React.useState(null);
  const [draftTitle, setDraftTitle] = React.useState("");
  const [isRenaming, setIsRenaming] = React.useState(false);

  const startRename = React.useCallback((session) => {
    setEditingSessionId(session.session_id);
    setDraftTitle(session.title || "Untitled chat");
  }, []);

  const commitRename = React.useCallback(
    async (targetSessionId) => {
      if (!targetSessionId || isRenaming) return;
      setIsRenaming(true);
      try {
        const ok = await renameSession?.(targetSessionId, draftTitle);
        if (!ok) {
          console.warn("Failed to rename session");
          return;
        }
        setEditingSessionId(null);
        setDraftTitle("");
      } finally {
        setIsRenaming(false);
      }
    },
    [draftTitle, isRenaming, renameSession],
  );

  const cancelRename = React.useCallback(() => {
    setEditingSessionId(null);
    setDraftTitle("");
  }, []);

  return (
    <Box
      style={{
        width: 240,
        borderRight: "1px solid rgba(111, 134, 133, 0.14)",
        background:
          "linear-gradient(180deg, rgba(242, 247, 246, 0.94) 0%, rgba(236, 243, 241, 0.92) 100%)",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      <Box
        px="md"
        py="md"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <Box>
          <Text size="xs" fw={700} c="#62716f" tt="uppercase" style={{ letterSpacing: "0.08em" }}>
            Sessions
          </Text>
          <Text size="sm" c="#7a8887">
            Recent design conversations
          </Text>
        </Box>
        <Button size="sm" w="100%" radius="md" variant="filled" onClick={createNewSession}>
          New chat
        </Button>
      </Box>
      <Divider color="rgba(111, 134, 133, 0.14)" />
      <ScrollArea className="app-scroll-area" style={{ flexGrow: 1, minHeight: 0 }}>
        <Stack p="sm" gap="xs">
          {sessions.length === 0 ? (
            <Text size="sm" color="dimmed" px="xs" py="sm">
              No sessions yet.
            </Text>
          ) : (
            sessions.map((session) => (
              <SessionItem
                key={session.session_id}
                session={session}
                isActive={session.session_id === sessionId}
                isEditing={editingSessionId === session.session_id}
                isRenaming={isRenaming}
                draftTitle={draftTitle}
                onDraftTitleChange={setDraftTitle}
                onCommitRename={commitRename}
                onCancelRename={cancelRename}
                onSelect={selectSession}
                onStartRename={startRename}
                onDelete={deleteSession}
              />
            ))
          )}
        </Stack>
      </ScrollArea>
    </Box>
  );
};

export default SessionsSidebar;
