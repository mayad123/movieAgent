/**
 * CineMind app config. Override in production (e.g. set window.CINEMIND_API_BASE before loading app.js).
 */
window.CINEMIND_CONFIG = window.CINEMIND_CONFIG || {
    apiBase: window.CINEMIND_API_BASE || 'http://localhost:8000',
    // Sub-context hub latency controls (Phase 1)
    hubAutoQueryTimeoutMs: 12000,
    hubAutoMaxAttempts: 2,
    hubAutoRetryDelayMs: 500,
    hubAutoBackfillDelayMs: 1000,
    hubMinInitialRenderMovies: 10
};
