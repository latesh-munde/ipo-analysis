const API_BASE_URL = "/api/v1";

export class ApiError extends Error {
    constructor(message, status, code = "REQUEST_FAILED") {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.code = code;
    }
}

export async function apiRequest(path, options = {}) {
    let response;
    try {
        response = await fetch(`${API_BASE_URL}${path}`, options);
    } catch {
        throw new ApiError(
            "Could not reach the local API. Check that the backend is running and try again.",
            0,
            "API_UNAVAILABLE",
        );
    }

    let result;
    try {
        result = await response.json();
    } catch {
        throw new ApiError(
            "The server returned an unreadable response. Check the backend logs.",
            response.status,
            "INVALID_RESPONSE",
        );
    }

    if (!response.ok || !result.success) {
        throw new ApiError(
            result.error?.message ?? "The request failed.",
            response.status,
            result.error?.code ?? "REQUEST_FAILED",
        );
    }

    return result.data;
}
