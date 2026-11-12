import {
    Button,
    DashboardIcon,
    Flex,
    GridIcon,
    Header,
    type IconType,
    SettingsIcon,
    VideoIcon,
} from "@luxonis/common-fe-components";
import { useSearchParams } from "react-router";
import {
    CALIBRATION_ATTENTION_COLOR,
    needsCalibrationAttention,
} from "../calibration/calibrationState";
import { useSupportPlaneCalibrationStatus } from "../calibration/useSupportPlaneCalibration";
import {
    getAppRouteFromSearchParams,
    type AppRoute,
} from "../routing/appRoutes";
import { useAppNavigate } from "../routing/useAppNavigate";
import StatusDot from "./StatusDot";

const navItems: {
    label: string;
    to: AppRoute;
    icon: IconType;
}[] = [
    {
        label: "Home",
        to: "/",
        icon: DashboardIcon,
    },
    {
        label: "Calibration",
        to: "/calibration",
        icon: GridIcon,
    },
    {
        label: "Footage",
        to: "/recordings",
        icon: VideoIcon,
    },
    {
        label: "Settings",
        to: "/settings",
        icon: SettingsIcon,
    },
];

function TopNav() {
    const [searchParams] = useSearchParams();
    const currentRoute = getAppRouteFromSearchParams(searchParams);
    const navigate = useAppNavigate();
    const statusQuery = useSupportPlaneCalibrationStatus();
    const calibrationState = statusQuery.data?.state;

    // Calibration status dot visible on the nav bar from all pages. Stays
    // hidden while RESTORING, which resolves without the operator.
    const calibrationDot = needsCalibrationAttention(calibrationState)
        ? CALIBRATION_ATTENTION_COLOR
        : undefined;

    return (
        <nav>
            <Flex
                p="xs"
                gap="sm"
                alignItems="center"
                justifyContent="space-between"
                borderBottom="border.base"
                flexWrap="wrap"
            >
                <Header text="Box Measurement" />
                <Flex gap="xs" flexWrap="wrap">
                    {navItems.map((item) => {
                        const dotColor =
                            item.to === "/calibration"
                                ? calibrationDot
                                : undefined;

                        return (
                            <Flex
                                key={item.to}
                                gap="xs"
                                alignItems="center"
                            >
                                <Button
                                    type="button"
                                    variant={
                                        currentRoute === item.to
                                            ? "filled"
                                            : "ghost"
                                    }
                                    icon={item.icon}
                                    label={item.label}
                                    onClick={() => navigate(item.to)}
                                />
                                {dotColor ? (
                                    <StatusDot color={dotColor} size={8} />
                                ) : null}
                            </Flex>
                        );
                    })}
                </Flex>
            </Flex>
        </nav>
    );
}

export default TopNav;
