import { useEffect, useRef, useState } from "react";
import WebSocketService from "../api/websocket.js";
import { websocketUrl } from "../api/base.js";

const useWebSocket = ({ onMessage, onReconnect } = {}) => {
  const wsRef = useRef(null);
  const isMountedRef = useRef(false);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  const onReconnectRef = useRef(onReconnect);
  const hasEverConnectedRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onReconnectRef.current = onReconnect;
  }, [onReconnect]);

  useEffect(() => {
    isMountedRef.current = true;
    wsRef.current = new WebSocketService(websocketUrl("/chat"));

    wsRef.current.onMessage((data) => {
      if (typeof onMessageRef.current === "function") {
        onMessageRef.current(data);
      }
    });

    wsRef.current.onOpen(() => {
      if (isMountedRef.current) {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        if (hasEverConnectedRef.current) {
          if (typeof onReconnectRef.current === "function") {
            onReconnectRef.current();
          }
        } else {
          hasEverConnectedRef.current = true;
        }
      }
    });

    const handleDisconnect = () => {
      if (isMountedRef.current) {
        setIsConnected(false);
        const socket = wsRef.current?.ws;
        const isActive =
          socket &&
          (socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING);
        if (!reconnectTimerRef.current && !isActive) {
          const attempt = reconnectAttemptsRef.current + 1;
          reconnectAttemptsRef.current = attempt;
          const delay = Math.min(10000, 500 * attempt);
          reconnectTimerRef.current = setTimeout(() => {
            reconnectTimerRef.current = null;
            if (wsRef.current) {
              const currentSocket = wsRef.current.ws;
              const stillActive =
                currentSocket &&
                (currentSocket.readyState === WebSocket.OPEN ||
                  currentSocket.readyState === WebSocket.CONNECTING);
              if (!stillActive) {
                wsRef.current.connect();
              }
            }
          }, delay);
        }
      }
    };

    wsRef.current.onClose(handleDisconnect);
    wsRef.current.onError(handleDisconnect);

    wsRef.current.connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const sendSocketMessage = (payload) => {
    if (wsRef.current) {
      wsRef.current.sendMessage(payload);
    }
  };

  return { sendSocketMessage, isConnected };
};

export default useWebSocket;
