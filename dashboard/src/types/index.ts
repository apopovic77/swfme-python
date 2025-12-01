/**
 * sWFME Dashboard - TypeScript Types
 *
 * Type definitions matching the FastAPI backend
 */

export interface Parameter {
  type: string;
  required?: boolean;
  description?: string;
}

export interface Workflow {
  name: string;
  class: string;
  type: 'atomic' | 'orchestrated';
  module: string;
  doc?: string;
  input_parameters: Record<string, Parameter>;
  output_parameters: Record<string, Parameter>;
}

export interface ProcessMetrics {
  process_id: string;
  process_name: string;
  process_class: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  execution_time_ms?: number;
  error?: string;
  is_completed: boolean;
  is_failed: boolean;
}

export interface AggregatedMetrics {
  process_class: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  avg_execution_time_ms?: number;
  min_execution_time_ms?: number;
  max_execution_time_ms?: number;
  last_execution_at?: string;
}

export interface MetricsSummary {
  total_processes: number;
  completed: number;
  failed: number;
  success_rate: number;
  avg_execution_time_ms: number;
  process_classes: number;
}

export interface ProcessEvent {
  type: string;
  process_id: string;
  process_name: string;
  process_class: string;
  timestamp: string;
  status?: string;
  error?: string;
  group_index?: number;
  group_size?: number;
  execution_mode?: 'sequential' | 'parallel';
}

export interface WorkflowExecuteRequest {
  workflow_name: string;
  parameters: Record<string, any>;
}

export interface WorkflowExecuteResponse {
  success: boolean;
  process_id: string;
  status: string;
  execution_time_ms?: number;
  output?: Record<string, any>;
  error?: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  stats: {
    registered_workflows: number;
    total_executions: number;
    event_stats: {
      total_events: number;
      subscriber_count: number;
      event_types: string[];
    };
  };
}
