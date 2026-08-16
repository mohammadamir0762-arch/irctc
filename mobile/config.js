// "localhost" only works when the app and the backend run on the exact
// same machine — which is never true for Expo Go on a physical phone
// (the usual free way to test this), and isn't always true for
// emulators/simulators either. So this defaults to your computer's LAN IP.
//
// - Testing with Expo Go on a real phone: keep LAN_IP, and make sure the
//   phone is on the same WiFi network as this computer.
// - Android emulator (on this same machine): use "10.0.2.2" instead.
// - iOS simulator (on this same machine): "localhost" works.
//
// Find your LAN IP with `ipconfig getifaddr en0` (Mac Wi-Fi) — it changes
// when you switch networks, so update this if the app can't reach the API.
const LAN_IP = "172.20.138.169";

export const API_BASE = `http://${LAN_IP}:8000`;
