type ParseOptions = {
  decodeValues?: boolean;
  map?: boolean;
};

type ParsedCookie = {
  [key: string]: unknown;
  name: string;
  value: string;
};

function parseNameValuePair(value: string): { name: string; value: string } {
  const separator = value.indexOf("=");
  if (separator < 0) {
    return { name: "", value };
  }
  return {
    name: value.slice(0, separator),
    value: value.slice(separator + 1),
  };
}

export function parseString(value: string, options: ParseOptions = {}): ParsedCookie | null {
  const parts = value.split(";").map((part) => part.trim()).filter(Boolean);
  const first = parts.shift();
  if (!first) {
    return null;
  }

  const parsed = parseNameValuePair(first);
  if (!parsed.name) {
    return null;
  }

  const cookie: ParsedCookie = {
    name: parsed.name,
    value: options.decodeValues === false ? parsed.value : decodeURIComponent(parsed.value),
  };

  for (const part of parts) {
    const [rawKey, ...rawValue] = part.split("=");
    const key = rawKey.trim().toLowerCase();
    const item = rawValue.join("=");

    if (key === "expires") {
      cookie.expires = new Date(item);
    } else if (key === "max-age") {
      cookie.maxAge = Number.parseInt(item, 10);
    } else if (key === "secure") {
      cookie.secure = true;
    } else if (key === "httponly") {
      cookie.httpOnly = true;
    } else if (key === "samesite") {
      cookie.sameSite = item;
    } else if (key === "partitioned") {
      cookie.partitioned = true;
    } else if (key) {
      cookie[key] = item;
    }
  }

  return cookie;
}

export function splitCookiesString(value: string | string[] | undefined | null): string[] {
  if (Array.isArray(value)) {
    return value;
  }
  if (!value) {
    return [];
  }

  const cookies: string[] = [];
  let start = 0;
  let inExpires = false;

  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    const next = value.slice(index, index + 8).toLowerCase();
    if (next === "expires") {
      inExpires = true;
    }
    if (inExpires && char === ";") {
      inExpires = false;
    }
    if (!inExpires && char === ",") {
      const rest = value.slice(index + 1);
      if (/^\s*[^=;,\s]+=/.test(rest)) {
        cookies.push(value.slice(start, index).trim());
        start = index + 1;
      }
    }
  }

  cookies.push(value.slice(start).trim());
  return cookies.filter(Boolean);
}

export function parse(input: unknown, options: ParseOptions = {}): ParsedCookie[] | Record<string, ParsedCookie> {
  let values: string[] = [];

  if (Array.isArray(input)) {
    values = input;
  } else if (typeof input === "string") {
    values = splitCookiesString(input);
  } else if (input && typeof input === "object" && "headers" in input) {
    const headers = (input as { headers?: Record<string, string | string[]> }).headers ?? {};
    const header = headers["set-cookie"] ?? headers["Set-Cookie"];
    values = Array.isArray(header) ? header : splitCookiesString(header);
  }

  const parsed = values
    .map((item) => parseString(item, options))
    .filter((item): item is ParsedCookie => item !== null);

  if (!options.map) {
    return parsed;
  }

  return Object.fromEntries(parsed.map((cookie) => [cookie.name, cookie]));
}

export default parse;
