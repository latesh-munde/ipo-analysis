const API_BASE_URL = "/api/v1";

async function checkBackendHealth() {
    const statusElement = document.querySelector("#api-status");

    try {
        const response = await fetch(`${API_BASE_URL}/health`);

        if (!response.ok) {
            throw new Error("Backend request failed");
        }

        const data = await response.json();
        statusElement.textContent = `Backend status: ${data.status}`;
    } catch {
        statusElement.textContent = "Unable to connect to backend.";
    }
}

checkBackendHealth();