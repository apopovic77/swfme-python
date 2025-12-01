import type { Workflow, WorkflowExecuteResponse } from '../types';

interface WorkflowShelfProps {
  workflows: Workflow[];
  loading: boolean;
  error: string | null;
  lastRun: WorkflowExecuteResponse | null;
  selectedWorkflowName: string | null;
  onSelect: (workflow: Workflow) => void;
  onRefresh: () => void;
}

export function WorkflowShelf({
  workflows,
  loading,
  error,
  lastRun,
  selectedWorkflowName,
  onSelect,
  onRefresh,
}: WorkflowShelfProps) {
  return (
    <div className="workflow-shelf">
      <div className="shelf-header">
        <div>
          <p className="eyebrow">Workflow shelf</p>
          <h2>Registered workflows</h2>
          <p className="muted">Trigger orchestrations or inspect their shape.</p>
        </div>
        <button className="ghost" onClick={onRefresh} disabled={loading}>
          {loading ? 'Syncing…' : 'Reload'}
        </button>
      </div>

      {error && <div className="banner warn">⚠️ {error}</div>}

      {lastRun && (
        <div className={`banner ${lastRun.success ? 'ok' : 'warn'}`}>
          <div>
            <p className="eyebrow">Last execution</p>
            <strong>{lastRun.status}</strong>
          </div>
          <div className="banner-meta">
            {lastRun.execution_time_ms !== undefined && (
              <span>{lastRun.execution_time_ms.toFixed(1)} ms</span>
            )}
            {lastRun.error && <span className="pill warn">{lastRun.error}</span>}
          </div>
        </div>
      )}

      {loading ? (
        <div className="card muted">Loading workflows…</div>
      ) : workflows.length === 0 ? (
        <div className="card muted">No workflows registered yet.</div>
      ) : (
        <div className="workflow-grid">
          {workflows.map((workflow) => {
            const inputCount = Object.keys(workflow.input_parameters || {}).length;
            const outputCount = Object.keys(workflow.output_parameters || {}).length;
            const isSelected = selectedWorkflowName === workflow.name;

            return (
              <article
                key={workflow.name}
                className={`workflow-card ${isSelected ? 'workflow-card--selected' : ''}`}
              >
                <div className="workflow-heading">
                  <div>
                    <p className="eyebrow">{workflow.module}</p>
                    <h3>{workflow.name}</h3>
                  </div>
                  <span className={`pill ${workflow.type === 'orchestrated' ? 'ok' : 'neutral'}`}>
                    {workflow.type}
                  </span>
                </div>

                <p className="muted">{workflow.doc || workflow.class}</p>

                <div className="param-row">
                  <span>{inputCount} inputs</span>
                  <span>{outputCount} outputs</span>
                </div>

                {inputCount > 0 && (
                  <div className="param-block">
                    <p className="eyebrow">Inputs</p>
                    <div className="param-list">
                      {Object.entries(workflow.input_parameters).map(([name, param]) => (
                        <span key={name} className="pill neutral">
                          {name}: {param.type}
                          {param.required ? ' • required' : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  className="primary block"
                  onClick={() => onSelect(workflow)}
                  disabled={loading}
                >
                  {isSelected ? 'Loaded' : 'Load workflow'}
                </button>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
