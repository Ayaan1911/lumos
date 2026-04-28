import { useState, useEffect, useCallback, useRef } from 'react';
import { ShieldAlert, CheckCircle2, XCircle, Save, RotateCcw } from 'lucide-react';
import { getPolicy, updatePolicy, validatePolicy } from '../api/policy';
import { toast } from '../components/Toast';
import { PageHeader, Button, Spinner } from '../components/Layout';
import Editor from '@monaco-editor/react';

const EDITOR_OPTS = {
  minimap: { enabled: false },
  fontSize: 13,
  fontFamily: "'JetBrains Mono', monospace",
  lineHeight: 20,
  scrollBeyondLastLine: false,
  tabSize: 2,
  wordWrap: 'on',
  renderLineHighlight: 'line',
  lineNumbers: 'on',
  glyphMargin: false,
  folding: true,
  scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
};

export default function PolicyEditor() {
  const [original, setOriginal] = useState('');
  const [yaml, setYaml] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validState, setValidState] = useState(null); // null | { valid, error }
  const [lastUpdated, setLastUpdated] = useState(null);
  const [fingerprint, setFingerprint] = useState(null);
  const editorRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await getPolicy();
      const content = data.yaml_content || '# No policy loaded\n';
      setOriginal(content);
      setYaml(content);
      setFingerprint(data.fingerprint);
      setLastUpdated(new Date());
      setValidState(null);
    } catch (err) {
      toast.error(`Failed to load policy: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await validatePolicy(yaml);
      setValidState(res);
      if (res.valid) {
        toast.success('Policy is valid');
      } else {
        toast.warning(`Policy has errors: ${res.error}`);
      }
    } catch (err) {
      toast.error(`Validation request failed: ${err.message}`);
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    if (validState && !validState.valid) {
      toast.warning('Fix validation errors before saving');
      return;
    }
    setSaving(true);
    try {
      await updatePolicy(yaml);
      setOriginal(yaml);
      setLastUpdated(new Date());
      toast.success('Policy saved and applied (hot-reloaded)');
      setValidState(null);
    } catch (err) {
      toast.error(`Failed to save policy: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setYaml(original);
    setValidState(null);
    if (editorRef.current) {
      editorRef.current.setValue(original);
    }
  };

  const isDirty = yaml !== original;
  const fingerprintLabel = typeof fingerprint === 'string'
    ? fingerprint
    : Object.entries(fingerprint || {})
        .map(([path, value]) => `${path}:${value}`)
        .join(', ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', gap: '0' }}>
      <PageHeader
        title="Policy Editor"
        description="Edit YAML enforcement rules — changes apply in < 1 second without restart"
        action={
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {isDirty && (
              <span style={{ fontSize: '10px', color: '#fbbf24', padding: '4px 9px', background: '#f59e0b15', border: '1px solid #f59e0b45', borderRadius: '999px', fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Unsaved changes
              </span>
            )}
            <Button variant="secondary" onClick={handleReset} disabled={!isDirty}>
              <RotateCcw size={13} /> Reset
            </Button>
            <Button variant="secondary" onClick={handleValidate} loading={validating}>
              <CheckCircle2 size={13} /> Validate
            </Button>
            <Button onClick={handleSave} loading={saving} disabled={!isDirty}>
              <Save size={13} /> Save Policy
            </Button>
          </div>
        }
      />

      {/* ── Warning Banner ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '11px 14px', marginBottom: '14px',
        background: '#f59e0b12', border: '1px solid #f59e0b45',
        borderRadius: '12px', fontSize: '12px', color: '#fbbf24',
        boxShadow: '0 0 18px rgba(245,158,11,0.08)',
      }}>
        <ShieldAlert size={13} />
        Invalid policy will be rejected by the API — always validate before saving. Policy reloads hot in &lt;1s.
      </div>

      {/* ── Validation Result ── */}
      {validState && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '8px',
          padding: '9px 14px', marginBottom: '14px',
          background: validState.valid ? '#22c55e10' : '#ef444410',
          border: `1px solid ${validState.valid ? '#22c55e30' : '#ef444430'}`,
          borderRadius: '12px', fontSize: '12px',
          color: validState.valid ? '#4ade80' : '#fb7185',
        }}>
          {validState.valid
            ? <><CheckCircle2 size={13} style={{ flexShrink: 0, marginTop: '1px' }} /> Policy is syntactically valid and accepted by the engine</>
            : <><XCircle size={13} style={{ flexShrink: 0, marginTop: '1px' }} /> <span><strong>Error:</strong> {validState.error}</span></>
          }
        </div>
      )}

      {/* ── Editor Meta ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        padding: '9px 14px',
        background: '#07070c', border: '1px solid rgba(124,58,237,0.25)',
        borderRadius: '12px 12px 0 0',
        fontSize: '11px', color: '#73738c',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
      }}>
        <span>policies/default.yaml</span>
        {fingerprintLabel && (
          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#06b6d4' }}>
            {fingerprintLabel.length > 32 ? `${fingerprintLabel.slice(0, 32)}...` : fingerprintLabel}
          </span>
        )}
        {lastUpdated && <span style={{ marginLeft: 'auto' }}>Last loaded: {lastUpdated.toLocaleTimeString()}</span>}
      </div>

      {/* ── Monaco Editor ── */}
      <div style={{
        flex: 1, minHeight: 0,
        border: '1px solid rgba(124,58,237,0.25)', borderTop: 'none',
        borderRadius: '0 0 12px 12px',
        overflow: 'hidden',
        boxShadow: '0 18px 44px rgba(0,0,0,0.32)',
      }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Spinner size={28} />
          </div>
        ) : (
          <Editor
            height="100%"
            language="yaml"
            value={yaml}
            onChange={(val) => {
              setYaml(val || '');
              setValidState(null);
            }}
            onMount={(editor) => { editorRef.current = editor; }}
            theme="vs-dark"
            options={EDITOR_OPTS}
          />
        )}
      </div>

      {/* ── Policy Quick Reference ── */}
      <div style={{ marginTop: '14px', padding: '12px 14px', background: '#111118', border: '1px solid rgba(6,182,212,0.18)', borderRadius: '12px', boxShadow: '0 12px 34px rgba(0,0,0,0.22)' }}>
        <div style={{ fontSize: '11px', color: '#06b6d4', marginBottom: '7px', fontWeight: '800', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          Quick Reference
        </div>
        <div style={{ display: 'flex', gap: '32px', fontSize: '11px', color: '#73738c', fontFamily: 'JetBrains Mono, monospace' }}>
          <span><span style={{ color: '#c4b5fd' }}>rules[].action</span>: allow | deny</span>
          <span><span style={{ color: '#c4b5fd' }}>rules[].tool</span>: glob (e.g. "tool.*")</span>
          <span><span style={{ color: '#c4b5fd' }}>rate_limits</span>: window_seconds, max_calls</span>
          <span><span style={{ color: '#c4b5fd' }}>budgets</span>: period (daily|monthly), limit</span>
        </div>
      </div>
    </div>
  );
}
