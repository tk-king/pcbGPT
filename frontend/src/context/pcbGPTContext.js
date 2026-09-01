import { createContext } from "react";

// Holds the value returned by usePcbGPT for the whole app.
const pcbGPTContext = createContext(null);

export default pcbGPTContext;
