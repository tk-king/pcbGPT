import { memo } from "react";
import { Box } from "@mantine/core";
import UserMessage from "./messages/UserMessage";
import LLMResponse from "./messages/LLMResponse";
import ToolCallMessage from "./messages/ToolCallMessage";
import ErrorMessage from "./messages/ErrorMessage";
import InfoMessage from "./messages/InfoMessage";

const ChatMessage = memo(({ event }) => {
  let messageContent;

  switch (event.type) {
    case "user":
      messageContent = <UserMessage event={event} />;
      break;
    case "text":
      messageContent = <LLMResponse event={event} />;
      break;
    case "tool_call":
    case "tool":
      messageContent = <ToolCallMessage event={event} />;
      break;
    case "error":
      messageContent = <ErrorMessage message={event.message ?? "Request failed."} />;
      break;
    case "info":
      messageContent = <InfoMessage info={event.info ?? ""} />;
      break;
    default:
      messageContent = undefined;
  }

  return <Box pb="sm">{messageContent}</Box>;
});

export default ChatMessage;
