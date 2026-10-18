export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue | readonly QueryValue[]>;

/** Arrays repeat the key (`status=A&status=B`, as django-filter expects); empty values are dropped. */
export function toSearchParams(params: object = {}): URLSearchParams {
  const search = new URLSearchParams();
  for (const [key, raw] of Object.entries(params as QueryParams)) {
    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value === undefined || value === null || value === "") continue;
      search.append(key, String(value));
    }
  }
  return search;
}

export function withQuery(path: string, params?: object): string {
  const query = toSearchParams(params).toString();
  return query ? `${path}?${query}` : path;
}

/** "collections/12/void" style path without leading/trailing slashes. */
export function trimPath(path: string): string {
  return path.replace(/^\/+|\/+$/g, "");
}
