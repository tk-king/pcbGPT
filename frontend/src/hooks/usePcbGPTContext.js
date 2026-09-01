import { useContext } from "react";
import pcbGPTContext from "../context/pcbGPTContext.js";

const usePcbGPTContext = () => {
  const context = useContext(pcbGPTContext);

  if (!context) {
    throw new Error("usePcbGPTContext must be used within a PcbGPTProvider");
  }

  return context;
};

export default usePcbGPTContext;
