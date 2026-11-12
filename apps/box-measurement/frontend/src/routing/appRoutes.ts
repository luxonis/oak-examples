export const APP_ROUTE_QUERY_PARAM = "path";

export const appRoutes = [
    "/",
    "/calibration",
    "/events",
    "/settings",
] as const;

export type AppRoute = (typeof appRoutes)[number];

const appRouteSet = new Set<string>(appRoutes);

export function isAppRoute(value: string | null | undefined): value is AppRoute {
    return value !== null && value !== undefined && appRouteSet.has(value);
}

export function normalizeAppRoute(
    value: string | null | undefined,
): AppRoute {
    return isAppRoute(value) ? value : "/";
}

export function getAppRouteFromSearchParams(
    searchParams: URLSearchParams,
): AppRoute {
    return normalizeAppRoute(searchParams.get(APP_ROUTE_QUERY_PARAM));
}

export function withAppRoute(
    searchParams: URLSearchParams,
    route: AppRoute,
): URLSearchParams {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set(APP_ROUTE_QUERY_PARAM, route);
    return nextSearchParams;
}

export function makeAppLocation(
    searchParams: URLSearchParams,
    route: AppRoute,
): {
    pathname: "/";
    search: string;
} {
    const nextSearchParams = withAppRoute(searchParams, route);
    return {
        pathname: "/",
        search: `?${nextSearchParams.toString()}`,
    };
}
