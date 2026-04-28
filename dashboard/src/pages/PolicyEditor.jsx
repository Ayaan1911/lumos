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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', gap: '0' }}>
      <PageHeader
        title="Policy Editor"
        description="Edit YAML enforcement rules — changes apply in < 1 second without restart"
        action={
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {isDirty && (
              <span style={{ fontSize: '11px', color: '#f59e0b', padding: '2px 8px', background: '#f59e0b15', border: '1px solid #f59e0b30', borderRadius: '4px' }}>
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
        padding: '9px 14px', marginBottom: '14px',
        background: '#f59e0b10', border: '1px solid #f59e0b30',
        borderRadius: '6px', fontSize: '12px', color: '#f59e0b',
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
          borderRadius: '6px', fontSize: '12px',
          color: validState.valid ? '#22c55e' : '#ef4444',
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
        padding: '7px 14px',
        background: '#0d0d0d', border: '1px solid #1a1a1a',
        borderRadius: '6px 6px 0 0',
        fontSize: '11px', color: '#444',
      }}>
        <span>policies/default.yaml</span>
        {fingerprint && <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>sha256:{fingerprint.slice(0, 16)}…</span>}
        {lastUpdated && <span style={{ marginLeft: 'auto' }}>Last loaded: {lastUpdated.toLocaleTimeString()}</span>}
      </div>

      {/* ── Monaco Editor ── */}
      <div style={{
        flex: 1, minHeight: 0,
        border: '1px solid #1a1a1a', borderTop: 'none',
        borderRadius: '0 0 6px 6px',
        overflow: 'hidden',
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
      <div style={{ marginTop: '14px', padding: '10px 14px', background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: '6px' }}>
        <div style={{ fontSize: '11px', color: '#444', marginBottom: '6px', fontWeight: '600', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          Quick Reference
        </div>
        <div style={{ display: 'flex', gap: '32px', fontSize: '11px', color: '#555', fontFamily: 'JetBrains Mono, monospace' }}>
          <span><span style={{ color: '#7c3aed' }}>rules[].action</span>: allow | deny</span>
          <span><span style={{ color: '#7c3aed' }}>rules[].tool</span>: glob (e.g. "tool.*")</span>
          <span><span style={{ color: '#7c3aed' }}>rate_limits</span>: window_seconds, max_calls</span>
          <span><span style={{ color: '#7c3aed' }}>budgets</span>: period (daily|monthly), limit</span>
        </div>
      </div>
    </div>
  );
}
