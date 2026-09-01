import { useEffect, useRef } from "react";
// Keeps a scrollable viewport pinned to its bottom while content changes.
const useAutoScroll = (dependencies) => {
  const viewportRef = useRef(null);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollTo({
      top: viewport.scrollHeight,
      behavior: "smooth",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  return viewportRef;
};

export default useAutoScroll;
