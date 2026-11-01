/** One function per backend endpoint (see CODE_OVERVIEW.md → API table). */
import { api, enc } from "./client";

export const authApi = {
  register: (body) => api("/auth/register", { method: "POST", body }),
  login: (body) => api("/auth/login", { method: "POST", body }),
  me: () => api("/auth/me"),
};

export const profilesApi = {
  list: () => api("/profiles"),
  create: (body) => api("/profiles", { method: "POST", body }),
  update: (id, body) => api(`/profiles/${id}`, { method: "PUT", body }),
  remove: (id) => api(`/profiles/${id}`, { method: "DELETE" }),
  skillSuggestions: () => api("/profiles/skills/suggestions"),
};

export const jobsApi = {
  get: (id) => api(`/jobs/${enc(id)}`),
  hrLink: (id) => api(`/jobs/${enc(id)}/hr-search-link`),
  draft: (id, body) => api(`/jobs/${enc(id)}/outreach`, { method: "POST", body }),
};

export const trackerApi = {
  list: () => api("/tracker"),
  track: (body, profileHash) =>
    api(`/tracker${profileHash ? `?profile_hash=${profileHash}` : ""}`, { method: "POST", body }),
  update: (jobId, body) => api(`/tracker/${enc(jobId)}`, { method: "PATCH", body }),
  remove: (jobId) => api(`/tracker/${enc(jobId)}`, { method: "DELETE" }),
};

export const statusApi = {
  status: () => api("/status"),
  models: () => api("/models"),
  checkModels: () => api("/models/check", { method: "POST" }),
  testModel: (model) => api("/models/test", { method: "POST", body: { model } }),
  saveModels: (body) => api("/models", { method: "PUT", body }),
  resetModels: () => api("/models/reset", { method: "POST" }),
};
