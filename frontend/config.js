// Where the frontend looks for the backend API.
//
// Served from localhost -> talk to the local backend.
// Served from anywhere else (Vercel/Netlify) -> talk to the deployed backend.
//
// Backend on Render's free tier sleeps after 15 minutes idle, so the first
// request after a quiet period takes ~1 minute to wake it. The UI shows a
// waking-up message rather than looking frozen.
const DEPLOYED_API = "https://pnr-predictor-api.onrender.com";

const isLocal = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);

window.API_BASE = isLocal ? "http://localhost:8000" : DEPLOYED_API;
window.API_BASE_CONFIGURED = isLocal || Boolean(DEPLOYED_API);
