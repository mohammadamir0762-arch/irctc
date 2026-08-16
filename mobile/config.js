// Points at the deployed backend, so the app works on any phone, on any
// network, without your laptop running anything.
//
// The free Render instance sleeps after ~15 minutes idle; the first request
// after that takes up to a minute to wake it. The app shows a message rather
// than just spinning.
const DEPLOYED_API = "https://pnr-predictor-api.onrender.com";

// For developing against a backend on your own machine, set USE_LOCAL to true
// and put your computer's LAN IP below (`ipconfig getifaddr en0` on Mac —
// it changes when you switch networks). The phone must be on the same WiFi,
// and the backend must be started with `--host 0.0.0.0`.
const USE_LOCAL = false;
const LAN_IP = "172.20.138.169";

export const API_BASE = USE_LOCAL ? `http://${LAN_IP}:8000` : DEPLOYED_API;
