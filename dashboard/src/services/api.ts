/**
 * sWFME API Client
 *
 * Service layer for communicating with FastAPI backend
 */

import type {
  Workflow,
  WorkflowExecuteRequest,
  WorkflowExecuteResponse,
  MetricsSummary,
  AggregatedMetrics,
  ProcessEvent,
  HealthResponse,
  WorkflowGraphResponse,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * API Client class for sWFME backend
 */
export class SwfmeApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Health check
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * List all available workflows
   */
  async listWorkflows(): Promise<Workflow[]> {
    const response = await fetch(`${this.baseUrl}/workflows`);
    if (!response.ok) {
      throw new Error(`Failed to list workflows: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Execute a workflow
   */
  async executeWorkflow(
    request: WorkflowExecuteRequest
  ): Promise<WorkflowExecuteResponse> {
    const response = await fetch(`${this.baseUrl}/workflows/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to execute workflow: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get metrics summary
   */
  async getMetricsSummary(): Promise<MetricsSummary> {
    const response = await fetch(`${this.baseUrl}/metrics/summary`);
    if (!response.ok) {
      throw new Error(`Failed to get metrics summary: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get aggregated metrics
   */
  async getAggregatedMetrics(): Promise<AggregatedMetrics[]> {
    const response = await fetch(`${this.baseUrl}/metrics/aggregated`);
    if (!response.ok) {
      throw new Error(`Failed to get aggregated metrics: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get event history
   */
  async getEvents(): Promise<{ events: ProcessEvent[] }> {
    const response = await fetch(`${this.baseUrl}/events`);
    if (!response.ok) {
      throw new Error(`Failed to get events: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Create WebSocket connection for real-time monitoring
   */
  createWebSocket(processId: string = 'all'): WebSocket {
    const wsUrl = this.baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    return new WebSocket(`${wsUrl}/ws/monitor/${processId}`);
  }

  async getWorkflowGraph(name: string): Promise<WorkflowGraphResponse> {
    const response = await fetch(`${this.baseUrl}/workflows/${name}/graph`);
    if (!response.ok) {
      throw new Error(`Failed to load workflow graph: ${response.statusText}`);
    }
    return response.json();
  }
}

// Default API client instance
export const apiClient = new SwfmeApiClient();
