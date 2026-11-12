import { useNavigate, useSearchParams } from "react-router";
import { makeAppLocation, type AppRoute } from "./appRoutes";

export function useAppNavigate() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    return (route: AppRoute) => {
        navigate(makeAppLocation(searchParams, route));
    };
}
