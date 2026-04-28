import { useEffect, useState, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle, XCircle, AlertTriangle, X, Info } from 'lucide-react';

// ─── Toast Context ─────────────────────────────────────────────────────────────
let globalToastFn = null;

export function toast(message, type = 'info') {
  if (globalToastFn) globalToastFn(message, type);
}
toast.success = (msg) => toast(msg, 'success');
toast.error = (msg) => toast(msg, 'error');
toast.warning = (msg) => toast(msg, 'warning');
toast.info = (msg) => toast(msg, 'info');

// ─── Single Toast Item ─────────────────────────────────────────────────────────
const ICONS = {
  success: <CheckCircle size={16} />,
  error: <XCircle size={16} />,
  warning: <AlertTriangle size={16} />,
  info: <Info size={16} />,
};

const COLORS = {
  success: '#22c55e',
  error: '#ef4444',
  warning: '#f59e0b',
  info: '#7c3aed',
};

function ToastItem({ id, message, type, onRemove }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const show = setTimeout(() => setVisible(true), 10);
    const hide = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onRemove(id), 300);
    }, 4000);
    return () => { clearTimeout(show); clearTimeout(hide); };
  }, [id, onRemove]);

  return (
    <div
      onClick={() => { setVisible(false); setTimeout(() => onRemove(id), 300); }}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '12px 14px',
        background: '#111111',
        border: '1px solid #1f1f1f',
        borderLeft: `3px solid ${COLORS[type]}`,
        borderRadius: '8px',
        cursor: 'pointer',
        maxWidth: '360px',
        minWidth: '280px',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateX(0)' : 'translateX(20px)',
        transition: 'all 0.25s ease',
        userSelect: 'none',
      }}
    >
      <span style={{ color: COLORS[type], marginTop: '1px', flexShrink: 0 }}>
        {ICONS[type]}
      </span>
      <span style={{ color: '#e5e5e5', fontSize: '13px', lineHeight: '1.4', flex: 1 }}>
        {message}
      </span>
      <span style={{ color: '#555', flexShrink: 0 }}>
        <X size={14} />
      </span>
    </div>
  );
}

// ─── Toast Container ───────────────────────────────────────────────────────────
export function ToastContainer() {
  const [toasts, setToasts] = useState([]);
  const counterRef = useRef(0);

  const addToast = useCallback((message, type) => {
    const id = ++counterRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    globalToastFn = addToast;
    return () => { globalToastFn = null; };
  }, [addToast]);

  return createPortal(
    <div style={{
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      alignItems: 'flex-end',
    }}>
      {toasts.map((t) => (
        <ToastItem key={t.id} {...t} onRemove={removeToast} />
      ))}
    </div>,
    document.body
  );
}
