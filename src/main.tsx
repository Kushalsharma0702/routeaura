/**
 * Main entry point for the Escapade Central application
 * This file initializes the React app and mounts it to the DOM
 */
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// Get the root element from index.html and render our app
createRoot(document.getElementById("root")!).render(<App />);
