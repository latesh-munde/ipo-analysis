const API_BASE_URL = "/api/v1";

export async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, options);

    const result = await response.json();

    if (!response.ok || !result.success) {
        throw new Error(
            result.error?.message ?? "The request failed."
        );
    }

    return result.data;
}