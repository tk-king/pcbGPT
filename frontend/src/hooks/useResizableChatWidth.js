import { useEffect, useRef, useState } from "react";

// Horizontal drag-resize for the chat column inside a grid layout.
// Grid: [sidebar 240px] [chat resizable] [separator 6px] [rest].
const SIDEBAR_WIDTH = 240;
const SEPARATOR_WIDTH = 6;
const MIN_CHAT_WIDTH = 320;
const MIN_RIGHT_PANE_WIDTH = 320;

const useResizableChatWidth = () => {
  const [chatWidthPx, setChatWidthPx] = useState(520);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (event) => {
      if (!containerRef.current) return;
      const { left, width } = containerRef.current.getBoundingClientRect();
      const available = Math.max(0, width - SIDEBAR_WIDTH - SEPARATOR_WIDTH);
      const pointerX = event.clientX - left - SIDEBAR_WIDTH;
      const clampedPx = Math.min(
        available - MIN_RIGHT_PANE_WIDTH,
        Math.max(MIN_CHAT_WIDTH, pointerX),
      );
      setChatWidthPx(clampedPx);
    };

    const stopResizing = () => setIsResizing(false);

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [isResizing]);

  const startResizing = (event) => {
    event.preventDefault();
    setIsResizing(true);
  };

  return { containerRef, chatWidthPx, isResizing, startResizing };
};

export default useResizableChatWidth;
