import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import {
    APP_ROUTE_QUERY_PARAM,
    getAppRouteFromSearchParams,
    makeAppLocation,
    type AppRoute,
} from "./appRoutes";

type ParamRouterProps = {
    routes: Record<AppRoute, ReactNode>;
};

function ParamRouter({ routes }: ParamRouterProps) {
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const activeRoute = getAppRouteFromSearchParams(searchParams);
    const pathParams = searchParams.getAll(APP_ROUTE_QUERY_PARAM);
    const hasNormalizedPathParam =
        pathParams.length === 1 && pathParams[0] === activeRoute;

    if (location.pathname !== "/" || !hasNormalizedPathParam) {
        return (
            <Navigate
                replace
                to={makeAppLocation(searchParams, activeRoute)}
            />
        );
    }

    return routes[activeRoute];
}

export default ParamRouter;
