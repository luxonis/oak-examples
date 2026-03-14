import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { css } from "../styled-system/css/css.mjs";

type Notification = {
    id: number;
    message: string;
    type?: "info" | "success" | "warning" | "error";
    durationMs?: number;
};

type NotificationContextValue = {
    notify: (message: string, options?: { type?: Notification["type"]; durationMs?: number }) => void;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function useNotifications() {
    const ctx = useContext(NotificationContext);
    if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
    return ctx;
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
    const [items, setItems] = useState<Notification[]>([]);
    const idRef = useRef(1);

    const remove = useCallback((id: number) => {
        setItems((prev) => prev.filter((n) => n.id !== id));
    }, []);

    const notify = useCallback<NotificationContextValue["notify"]>((message, options) => {
        const id = idRef.current++;
        const durationMs = options?.durationMs ?? 4500;
        const type = options?.type ?? "info";
        setItems((prev) => [...prev, { id, message, type, durationMs }].slice(-5));
        if (durationMs > 0) {
            window.setTimeout(() => remove(id), durationMs);
        }
    }, [remove]);

    const value = useMemo(() => ({ notify }), [notify]);

    return (
        <NotificationContext.Provider value={value}>
            {children}
            <div className={css({ position: "fixed", bottom: "4", right: "4", display: "flex", flexDirection: "column", gap: "2", zIndex: 1000, pointerEvents: "auto", width: "md", alignItems: "flex-end" })}>
                {items.map((n, idx) => (
                    <Toast key={n.id} notification={n} onClose={() => remove(n.id)} index={idx} />
                ))}
            </div>
        </NotificationContext.Provider>
    );
}

function Toast({ notification, onClose, index }: { notification: Notification; onClose: () => void; index: number }) {
    const { message, type } = notification;
    const colorMap: Record<NonNullable<Notification["type"]>, { bg: string; border: string; text: string }> = {
        info: { bg: "white", border: "blue.400", text: "blue.900" },
        success: { bg: "white", border: "green.400", text: "green.900" },
        warning: { bg: "white", border: "yellow.400", text: "yellow.900" },
        error: { bg: "white", border: "red.400", text: "red.900" },
    };
    const colors = colorMap[type ?? "info"];

    return (
        <div
            className={css({
                backgroundColor: colors.bg,
                border: "1px solid",
                borderColor: colors.border,
                color: colors.text,
                borderRadius: "lg",
                paddingX: "4",
                paddingY: "3",
                width: "60%",
                boxShadow: "xl",
                pointerEvents: "auto",
                transform: "translateY(8px)",
                animation: "slideInUp 180ms ease-out forwards",
                _motionSafe: { animation: "slideInUp 180ms ease-out forwards" },
                wordBreak: "break-word",
                boxSizing: "border-box",
                opacity: 1,
            })}
            style={{ animationDelay: `${index * 30}ms` }}
        >
            <div className={css({ display: "flex", alignItems: "center", gap: "3" })}>
                <span className={css({ fontWeight: "medium" })}>{message}</span>

                {/* Close button */}
                <button
                    className={css({
                        marginLeft: "auto",
                        color: colors.text,
                        fontSize: "lg",
                        fontWeight: "bold",
                        lineHeight: "1",
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        padding: "0 4px",
                        _hover: { opacity: 0.7, transform: "scale(1.1)" },
                        transition: "transform 0.15s ease",
                    })}
                    onClick={onClose}
                >
                    ×
                </button>
            </div>
        </div>
    );
}


// Keyframes for smooth appear (no opacity change to keep background fully opaque)
const styleEl = (typeof document !== 'undefined') ? document.createElement('style') : null;
if (styleEl && !document.getElementById('notif-keyframes')) {
    styleEl.id = 'notif-keyframes';
    styleEl.innerHTML = `
@keyframes slideInUp { from { transform: translateY(8px); } to { transform: translateY(0); } }
@keyframes slideOutDown { from { transform: translateY(0); } to { transform: translateY(8px); } }
`;
    document.head.appendChild(styleEl);
}

