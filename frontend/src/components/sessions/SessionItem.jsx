import React from "react";
import { ActionIcon, Box, Button, Menu, TextInput } from "@mantine/core";
import { IconDots, IconPencil, IconTrash } from "@tabler/icons-react";

// A single session row in the sidebar: select button, inline rename input
// and the hover "…" menu with rename/delete actions.
const SessionItem = ({
  session,
  isActive,
  isEditing,
  isRenaming,
  draftTitle,
  onDraftTitleChange,
  onCommitRename,
  onCancelRename,
  onSelect,
  onStartRename,
  onDelete,
}) => {
  const [hovered, setHovered] = React.useState(false);
  const [menuOpened, setMenuOpened] = React.useState(false);
  const displayTitle = session.title || "Untitled chat";
  const highlighted = hovered || menuOpened;

  return (
    <Box
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: "relative" }}
    >
      {isEditing ? (
        <TextInput
          value={draftTitle}
          autoFocus
          size="xs"
          radius="md"
          disabled={isRenaming}
          styles={{
            input: {
              minHeight: 42,
              height: 42,
              paddingRight: 34,
              fontSize: 14,
              fontWeight: 600,
              color: "#617170",
              background: "rgba(255, 255, 255, 0.72)",
              border: "1px solid rgba(111, 134, 133, 0.16)",
            },
          }}
          onChange={(event) => onDraftTitleChange(event.currentTarget.value)}
          onClick={(event) => event.stopPropagation()}
          onBlur={() => onCommitRename(session.session_id)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onCommitRename(session.session_id);
            } else if (event.key === "Escape") {
              event.preventDefault();
              onCancelRename();
            }
          }}
        />
      ) : (
        <Button
          variant={isActive ? "filled" : "subtle"}
          color={isActive ? "brand" : "gray"}
          fullWidth
          radius="md"
          styles={{
            root: {
              paddingRight: "34px",
              minHeight: 42,
              justifyContent: "flex-start",
              border:
                isActive
                  ? "1px solid rgba(65, 119, 118, 0.26)"
                  : "1px solid rgba(111, 134, 133, 0.08)",
              background: isActive
                ? "linear-gradient(180deg, rgba(127, 178, 177, 0.34) 0%, rgba(127, 178, 177, 0.22) 100%)"
                : "rgba(255, 255, 255, 0.42)",
              color: "#617170",
              boxShadow: isActive ? "0 6px 18px rgba(65, 119, 118, 0.08)" : "none",
              "&:hover": {
                background: isActive
                  ? "linear-gradient(180deg, rgba(127, 178, 177, 0.4) 0%, rgba(127, 178, 177, 0.28) 100%)"
                  : "rgba(255, 255, 255, 0.72)",
              },
            },
            label: {
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              textAlign: "left",
              width: "100%",
              fontWeight: isActive ? 700 : 600,
              color: "#617170",
            },
          }}
          onClick={() => onSelect(session.session_id)}
        >
          {displayTitle}
        </Button>
      )}
      <Menu
        shadow="md"
        width={150}
        position="bottom-end"
        opened={menuOpened}
        onChange={setMenuOpened}
      >
        <Menu.Target>
          <ActionIcon
            variant="transparent"
            size="sm"
            color="#5f706f"
            onClick={(event) => {
              event.stopPropagation();
            }}
            aria-label={`Session options for ${displayTitle}`}
            style={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
              opacity: highlighted ? 1 : 0,
              pointerEvents: highlighted ? "auto" : "none",
              transition: "opacity 120ms ease",
            }}
            styles={{
              root: {
                "&:hover": {
                  backgroundColor: "#ffffff",
                },
              },
            }}
          >
            <IconDots size={16} />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item
            leftSection={<IconPencil size={14} />}
            onClick={(event) => {
              event.stopPropagation();
              onStartRename(session);
            }}
          >
            Rename
          </Menu.Item>
          <Menu.Item
            color="red"
            leftSection={<IconTrash size={14} />}
            onClick={async (event) => {
              event.stopPropagation();
              const ok = window.confirm("Delete this chat? This cannot be undone.");
              if (!ok) return;
              await onDelete?.(session.session_id);
            }}
          >
            Delete
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
    </Box>
  );
};

export default SessionItem;
