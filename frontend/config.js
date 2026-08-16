// Where the frontend looks for the backend API.
//
// Served from localhost -> talk to the local backend.
// Served from anywhere else (Vercel/Netlify) -> talk to the deployed backend.
//
// AFTER DEPLOYING: replace DEPLOYED_API below with your Render URL, e.g.
//   https://pnr-predictor-api.onrender.com
// then redeploy the frontend. Until it is set, the hosted site will show a
// clear error rather than silently pointing at a machine nobody can reach.
const DEPLOYED_API = "";

const isLocal = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);

window.API_BASE = isLocal ? "http://localhost:8000" : DEPLOYED_API;
window.API_BASE_CONFIGURED = isLocal || Boolean(DEPLOYED_API);
