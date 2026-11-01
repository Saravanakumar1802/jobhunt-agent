/** Same URL the backend builds — kept client-side so the link works instantly. */
export function hrSearchUrl(company = "") {
  const keywords = `${company} recruiter OR "talent acquisition" OR HR`;
  return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(keywords)}`;
}
