import { apiRequest } from "./api/api-client.js";

async function checkBackendHealth() {
    const statusElement = document.querySelector("#api-status");

    try {
        const data = await apiRequest("/health");
        statusElement.textContent = `Backend status: ${data.status}`;
    } catch {
        statusElement.textContent = "Unable to connect to backend.";
    }
}

checkBackendHealth();