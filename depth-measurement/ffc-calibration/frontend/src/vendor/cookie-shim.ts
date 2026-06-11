type CookieOptions = {
  domain?: string;
  encode?: (value: string) => string;
  expires?: Date;
  httpOnly?: boolean;
  maxAge?: number;
  path?: string;
  sameSite?: boolean | "lax" | "strict" | "none";
  secure?: boolean;
};

export function parse(value: string): Record<string, string> {
  const result: Record<string, string> = {};
  if (!value) {
    return result;
  }

  for (const item of value.split(";")) {
    const index = item.indexOf("=");
    if (index < 0) {
      continue;
    }
    const key = item.slice(0, index).trim();
    const raw = item.slice(index + 1).trim();
    if (!key) {
      continue;
    }
    result[key] = decodeURIComponent(raw);
  }
  return result;
}

export function serialize(name: string, value: string, options: CookieOptions = {}): string {
  const encode = options.encode ?? encodeURIComponent;
  const segments = [`${name}=${encode(value)}`];

  if (options.maxAge !== undefined) {
    segments.push(`Max-Age=${Math.floor(options.maxAge)}`);
  }
  if (options.domain) {
    segments.push(`Domain=${options.domain}`);
  }
  if (options.path) {
    segments.push(`Path=${options.path}`);
  }
  if (options.expires) {
    segments.push(`Expires=${options.expires.toUTCString()}`);
  }
  if (options.httpOnly) {
    segments.push("HttpOnly");
  }
  if (options.secure) {
    segments.push("Secure");
  }
  if (options.sameSite) {
    const sameSite = options.sameSite === true ? "Strict" : options.sameSite;
    segments.push(`SameSite=${sameSite}`);
  }

  return segments.join("; ");
}

export const parseCookie = parse;
export const stringifySetCookie = serialize;
export const stringifyCookie = (value: Record<string, string>) =>
  Object.entries(value)
    .map(([key, item]) => `${key}=${encodeURIComponent(item)}`)
    .join("; ");

export default {
  parse,
  parseCookie,
  serialize,
  stringifyCookie,
  stringifySetCookie,
};
