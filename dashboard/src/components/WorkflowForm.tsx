import { useMemo } from 'react';
import type { Workflow } from '../types';

interface WorkflowFormProps {
  workflow: Workflow;
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
}

export function WorkflowForm({ workflow, values, onChange }: WorkflowFormProps) {
  const params = useMemo(() => Object.entries(workflow.input_parameters || {}), [workflow]);

  if (!params.length) return null;

  const handleChange = (key: string, val: string) => {
    const type = workflow.input_parameters[key]?.type;
    let parsed: any = val;
    if (type === 'int') parsed = parseInt(val, 10) || 0;
    else if (type === 'float') parsed = parseFloat(val) || 0;
    else if (type === 'bool' || type === 'boolean') parsed = val === 'true';
    onChange(key, parsed);
  };

  return (
    <div className="workflow-form">
      <p className="eyebrow">Inputs</p>
      <div className="form-grid">
        {params.map(([name, param]) => (
          <label key={name} className="form-row">
            <span>{name}</span>
            <input
              type="text"
              value={values[name] ?? ''}
              placeholder={`${param.type}${param.required ? ' (required)' : ''}`}
              onChange={(e) => handleChange(name, e.target.value)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
