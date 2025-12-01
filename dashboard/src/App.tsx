import { useEffect, useMemo, useState } from 'react';
import 'reactflow/dist/style.css';
import './App.css';
import { apiClient } from './services/api';
import type { HealthResponse, Workflow, WorkflowExecuteResponse } from './types';
import { WorkflowShelf } from './components/WorkflowShelf';
import { LiveFlow } from './components/LiveFlow';
import { WorkflowForm } from './components/WorkflowForm';

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [workflowsError, setWorkflowsError] = useState<string | null>(null);
  const [loadingWorkflows, setLoadingWorkflows] = useState(true);
  const [executingWorkflow, setExecutingWorkflow] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<WorkflowExecuteResponse | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [selectedWorkflowName, setSelectedWorkflowName] = useState<string | null>(null);
  const [inputValues, setInputValues] = useState<Record<string, any>>({});

  useEffect(() => {
    refreshHealth();
    refreshWorkflows();
  }, []);

  const refreshHealth = async () => {
    try {
      const data = await apiClient.health();
      setHealth(data);
      setHealthError(null);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'Backend not reachable');
    }
  };

  const refreshWorkflows = async () => {
    try {
      setLoadingWorkflows(true);
      const data = await apiClient.listWorkflows();
      const orchestrated = data.filter((wf) => wf.type === 'orchestrated');
      setWorkflows(orchestrated);
      if (!selectedWorkflowName && orchestrated.length > 0) {
        setSelectedWorkflowName(orchestrated[0].name);
      }
      setWorkflowsError(null);
    } catch (err) {
      setWorkflowsError(err instanceof Error ? err.message : 'Failed to load workflows');
    } finally {
      setLoadingWorkflows(false);
    }
  };

  const executeWorkflow = async (workflow: Workflow) => {
    try {
      setExecutingWorkflow(workflow.name);
      setWorkflowsError(null);

      const parameters: Record<string, unknown> = {};
      for (const [key, param] of Object.entries(workflow.input_parameters)) {
        const fromForm = inputValues[key];
        if (fromForm !== undefined && fromForm !== '') {
          parameters[key] = fromForm;
          continue;
        }
        if (param.required) {
          if (param.type === 'str' || param.type === 'string') {
            parameters[key] = key === 'filename' ? 'example.csv' : `${key}-sample`;
          } else if (param.type === 'int') {
            parameters[key] = 1;
          } else if (param.type === 'float') {
            parameters[key] = 1.0;
          } else if (param.type === 'bool' || param.type === 'boolean') {
            parameters[key] = true;
          } else {
            parameters[key] = null;
          }
        }
      }

      const result = await apiClient.executeWorkflow({
        workflow_name: workflow.name,
        parameters,
      });

      setLastRun(result);
    } catch (err) {
      setWorkflowsError(err instanceof Error ? err.message : 'Failed to execute workflow');
    } finally {
      setExecutingWorkflow(null);
    }
  };

  const runSelectedWorkflow = async () => {
    if (!selectedWorkflowName) return;
    const workflow = workflows.find((w) => w.name === selectedWorkflowName);
    if (!workflow) return;
    await executeWorkflow(workflow);
  };

  const healthStats = useMemo(() => {
    if (!health) return null;
    return [
      { label: 'Status', value: health.status, tone: health.status === 'healthy' ? 'ok' : 'warn' },
      { label: 'Version', value: health.version },
      { label: 'Workflows', value: health.stats.registered_workflows },
      { label: 'Executions', value: health.stats.total_executions },
    ];
  }, [health]);

  return (
    <div className="page">
      <section className="canvas-area">
        <LiveFlow
          variant="canvas"
          activeWorkflowName={selectedWorkflowName}
          onRun={runSelectedWorkflow}
          isRunning={!!executingWorkflow}
          activeWorkflow={workflows.find((w) => w.name === selectedWorkflowName) || null}
          inputValues={inputValues}
          onInputChange={(key, val) => setInputValues((prev) => ({ ...prev, [key]: val }))}
        />
      </section>

      <div className={`side-overlay ${panelOpen ? 'open' : ''}`}>
        <div className="overlay-content">
          <div className="topbar topbar--panel">
            <div>
              <p className="eyebrow">sWFME · Flow Console</p>
              <h1>React Flow live monitor</h1>
            </div>
            <div className="hero-actions">
              <button className="ghost" onClick={refreshHealth}>
                Refresh health
              </button>
              <button className="ghost" onClick={refreshWorkflows}>
                Sync workflows
              </button>
            </div>
            <div className="topbar-alerts">
              {healthError && <span className="pill warn">API: {healthError}</span>}
              {workflowsError && <span className="pill warn">Workflows: {workflowsError}</span>}
            </div>
          </div>

          <div className="health-card">
            <div className="shelf-header">
              <div>
                <p className="eyebrow">System</p>
                <h2>Health</h2>
              </div>
              <span className={`pill tiny ${health?.status === 'healthy' ? 'ok' : 'warn'}`}>
                {health?.status || '...'}
              </span>
            </div>
            <div className="stat-grid">
              {healthStats ? (
                healthStats.map((stat) => (
                  <div key={stat.label} className="stat-line">
                    <span className="muted">{stat.label}</span>
                    <strong className={stat.tone ? `tone-${stat.tone}` : ''}>{stat.value}</strong>
                  </div>
                ))
              ) : (
                <div className="stat-line">
                  <span className="muted">Status</span>
                  <strong>Loading…</strong>
                </div>
              )}
            </div>
          </div>

          <WorkflowShelf
            workflows={workflows}
            loading={loadingWorkflows}
            error={workflowsError}
            lastRun={lastRun}
            selectedWorkflowName={selectedWorkflowName}
            onSelect={(workflow) => setSelectedWorkflowName(workflow.name)}
            onRefresh={refreshWorkflows}
          />
          {selectedWorkflowName && (
            <WorkflowForm
              workflow={workflows.find((w) => w.name === selectedWorkflowName)!}
              values={inputValues}
              onChange={(key, val) => setInputValues((prev) => ({ ...prev, [key]: val }))}
            />
          )}
          <div className="event-panel">
            <p className="eyebrow">Event stream</p>
            <LiveFlow variant="feed" />
          </div>
        </div>
      </div>

      <button
        className="overlay-toggle"
        onClick={() => setPanelOpen((open) => !open)}
        aria-label="Toggle side panel"
      >
        {panelOpen ? 'Hide panel' : 'Show panel'}
      </button>
    </div>
  );
}

export default App;
