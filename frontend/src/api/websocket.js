// WebSocket transport for the chat stream.
// Moved from the former top-level src/api.js.

class WebSocketService {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.onMessageCallback = null;
    this.onOpenCallback = null;
    this.onCloseCallback = null;
    this.onErrorCallback = null;
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.currentThreadId = null;

    this.ws.onopen = () => {
      if (this.onOpenCallback) {
        this.onOpenCallback();
      }
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (this.onMessageCallback) {
        this.onMessageCallback(data);
      }
    };

    this.ws.onclose = (event) => {
      if (this.onCloseCallback) {
        this.onCloseCallback(event);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      if (this.onErrorCallback) {
        this.onErrorCallback(error);
      }
    };
  }

  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("WebSocket is not open. Message not sent:", message);
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
    this.currentThreadId = null;
  }

  getCurrentThreadId() {
    return this.currentThreadId;
  }

  onMessage(callback) {
    this.onMessageCallback = callback;
  }

  onOpen(callback) {
    this.onOpenCallback = callback;
  }

  onClose(callback) {
    this.onCloseCallback = callback;
  }

  onError(callback) {
    this.onErrorCallback = callback;
  }
}

export default WebSocketService;
