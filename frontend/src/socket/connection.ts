import { io, Socket } from "socket.io-client";

// Points at your local Flask-SocketIO backend during development.
// Change this when deploying, but for now this matches app.py running
// on port 5000.
const BACKEND_URL = "http://localhost:5000";

export const socket: Socket = io(BACKEND_URL, {
  autoConnect: false, // we connect explicitly, not immediately on import
});

export function connectSocket(): void {
  if (!socket.connected) {
    socket.connect();
  }
}

export function disconnectSocket(): void {
  if (socket.connected) {
    socket.disconnect();
  }
}

socket.on("connect", () => {
  console.log("Connected to server, socket id:", socket.id);
});

socket.on("disconnect", (reason) => {
  console.log("Disconnected from server:", reason);
});

socket.on("connect_error", (err) => {
  console.error("Connection error:", err.message);
});