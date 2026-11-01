import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";

const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const toast = useCallback((message, tone = "ok") => {
    const id = crypto.randomUUID();
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800);
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div role="status" aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex flex-col items-center gap-2 px-4 sm:bottom-6">
        {toasts.map((t) => (
          <div key={t.id} className="rise-in flex items-center gap-2.5 rounded-full bg-ink-950 px-4 py-2.5 text-sm font-medium text-white shadow-2xl">
            {t.tone === "error" ? (
              <AlertTriangle size={16} className="text-[#ff9a9e]" aria-hidden />
            ) : (
              <CheckCircle2 size={16} className="text-lime-300" aria-hidden />
            )}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
