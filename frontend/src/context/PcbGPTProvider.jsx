import pcbGPTContext from "./pcbGPTContext.js";
import usePcbGPT from "../hooks/usePcbGPT.jsx";

const { Provider } = pcbGPTContext;

export const PcbGPTProvider = ({ children }) => {
  const pcbGPT = usePcbGPT();

  return (
    <Provider value={pcbGPT}>
      {children}
    </Provider>
  );
};
