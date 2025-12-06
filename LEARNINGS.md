# sWFME Learnings & Best Practices

**Real-world insights from building production systems with Process-Oriented Programming**

Based on experience from CodePilot API and other production projects.

---

## Table of Contents

1. [OOP meets Process-Oriented Programming](#oop-meets-process-oriented-programming)
2. [Architecture Patterns That Work](#architecture-patterns-that-work)
3. [When to Use What](#when-to-use-what)
4. [Common Pitfalls & Solutions](#common-pitfalls--solutions)
5. [Real-World Example: CodePilot Pipeline](#real-world-example-codepilot-pipeline)
6. [Testing Strategies](#testing-strategies)
7. [Production Checklist](#production-checklist)

---

## OOP meets Process-Oriented Programming

### The Core Insight

**Traditional OOP** encapsulates state and behavior in objects. **Process-Oriented Programming** makes workflows explicit and observable. The magic happens when you combine both:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Architecture Layers                          │
├─────────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                            │
│    └── Routes call Services                                     │
├─────────────────────────────────────────────────────────────────┤
│  Service Layer (Traditional OOP)                                │
│    └── Business logic, external integrations                    │
│    └── GitService, ClaudeService, StorageService                │
├─────────────────────────────────────────────────────────────────┤
│  Process Layer (sWFME)                                          │
│    └── Orchestrated workflows using Services                    │
│    └── AgentExecutionPipeline, DataPipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  Domain Layer (OOP)                                             │
│    └── Entities, Value Objects, Enums                           │
│    └── Project, ChangeRequest, User                             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principle: Services for Capabilities, Processes for Workflows

```python
# ❌ DON'T: Put workflow logic in services
class GitService:
    def process_change_request(self, cr):
        self.clone()
        self.create_branch()
        self.commit()
        self.push()
        self.create_pr()  # Too much responsibility!

# ✅ DO: Services provide capabilities, Processes orchestrate
class GitService:
    """Provides git operations - single responsibility."""
    async def clone(self, url, path, token): ...
    async def create_branch(self, repo, name): ...
    async def commit(self, repo, message): ...
    async def push(self, repo, branch, token): ...

class AgentExecutionPipeline(OrchestratedProcess):
    """Orchestrates the workflow - uses services."""
    def __init__(self, git_service, claude_service, ...):
        self._git_service = git_service
        self._claude_service = claude_service

    async def after_children_executed(self):
        # Workflow is VISIBLE and TRACEABLE
        await ProcessEnsureRepoCloned(self._git_service, ...).execute()
        await ProcessCreateBranch(self._git_service, ...).execute()
        await ProcessExecuteClaude(self._claude_service, ...).execute()
        await ProcessCommitChanges(self._git_service, ...).execute()
```

---

## Architecture Patterns That Work

### Pattern 1: Attribute-Based I/O (Recommended)

Instead of using the parameter system for everything, use typed attributes for clarity:

```python
class ProcessEnsureRepoCloned(AtomarProcess):
    """
    Input:
        - project (Project): Project entity
        - github_token (str): GitHub token

    Output:
        - repo (Repo): GitPython Repo object
        - was_cloned (bool): True if fresh clone
        - local_path (Path): Path to cloned repo
    """

    def __init__(self, git_service: GitService, project: Project, github_token: str):
        super().__init__(name=f"EnsureRepoCloned-{project.id}")

        # Dependency injection
        self._git_service = git_service

        # Typed inputs as attributes
        self.input_project = project
        self.input_github_token = github_token

        # Typed outputs as attributes (initialized to None/defaults)
        self.output_repo: Optional[Repo] = None
        self.output_was_cloned: bool = False
        self.output_local_path: Optional[Path] = None

    def define_parameters(self) -> None:
        """Skip parameter system - using attributes."""
        pass

    async def execute_impl(self) -> None:
        # Use inputs, set outputs
        self.output_repo = await self._git_service.clone(...)
        self.output_was_cloned = True
        self.output_local_path = Path(...)
```

**Why this works better:**
- Type hints provide IDE support
- Clear naming convention: `input_*`, `output_*`
- No runtime parameter validation overhead
- Easier to test and mock

### Pattern 2: Dependency Injection via Constructor

Pass services to processes, don't create them inside:

```python
# ❌ DON'T: Create services inside process
class ProcessSendEmail(AtomarProcess):
    async def execute_impl(self):
        email_service = EmailService()  # Hard to test!
        await email_service.send(...)

# ✅ DO: Inject services
class ProcessSendEmail(AtomarProcess):
    def __init__(self, email_service: EmailService, recipient: str, body: str):
        super().__init__(name="SendEmail")
        self._email_service = email_service
        self.input_recipient = recipient
        self.input_body = body

    async def execute_impl(self):
        await self._email_service.send(self.input_recipient, self.input_body)
```

### Pattern 3: The "After Children" Hook Pattern

For complex pipelines where later steps depend on earlier outputs:

```python
class AgentExecutionPipeline(OrchestratedProcess):

    def orchestrate(self) -> None:
        """Add only the FIRST step that doesn't depend on anything."""
        self._ensure_cloned = ProcessEnsureRepoCloned(...)
        self.add_child(self._ensure_cloned, SEQUENTIAL)

    async def after_children_executed(self) -> None:
        """Continue with steps that need outputs from orchestrate()."""
        # Now we have access to first step's outputs
        repo = self._ensure_cloned.output_repo
        local_path = self._ensure_cloned.output_local_path

        # Continue the pipeline manually
        sync_process = ProcessSyncRepo(repo=repo, ...)
        await sync_process.execute()

        branch_process = ProcessCreateBranch(repo=repo, ...)
        await branch_process.execute()

        # ... more steps
```

**Why:** The `orchestrate()` method runs BEFORE execution. You can't access outputs there. Use `after_children_executed()` for dynamic pipelines.

### Pattern 4: Error Handling with Graceful Degradation

```python
async def after_children_executed(self) -> None:
    # Step that might fail
    push_success = False
    push_error = None

    try:
        push_process = ProcessPushBranch(...)
        await push_process.execute()
        push_success = push_process.output_success
    except Exception as e:
        push_error = str(e)
        self.logger.error(f"Push failed: {e}")

    if not push_success:
        await self._add_event("PUSH_FAILED", f"Push failed: {push_error}")
        # Don't raise - continue with what we can do
    else:
        # Only create PR if push succeeded
        pr_process = ProcessCreatePR(...)
        await pr_process.execute()
```

### Pattern 5: Process Naming Convention

```python
# Atomic processes: ProcessVerbNoun
ProcessEnsureRepoCloned
ProcessCreateBranch
ProcessCommitChanges
ProcessSendEmail
ProcessValidateInput

# Orchestrated processes: NounPipeline or NounWorkflow
AgentExecutionPipeline
DataProcessingPipeline
OrderFulfillmentWorkflow
UserOnboardingWorkflow
```

---

## When to Use What

### Use Atomic Process When:
- Single, focused operation
- One clear input → output transformation
- No child processes needed
- Examples: Clone repo, send email, make API call, validate data

### Use Orchestrated Process When:
- Multiple steps in sequence/parallel
- Steps depend on each other's outputs
- Need visibility into workflow progress
- Examples: Full pipeline, multi-step workflow, data processing chain

### Keep in Traditional OOP (Services) When:
- Stateless utilities (encryption, validation helpers)
- External API wrappers (GitHub API, Storage API)
- Reusable across many processes
- No workflow semantics needed

```python
# Service: Stateless capability
class CryptoService:
    def encrypt(self, data: str) -> str: ...
    def decrypt(self, data: str) -> str: ...

# Process: Workflow step using service
class ProcessEncryptSecrets(AtomarProcess):
    def __init__(self, crypto_service: CryptoService, secrets: dict):
        self._crypto = crypto_service
        self.input_secrets = secrets
        self.output_encrypted: dict = {}

    async def execute_impl(self):
        for key, value in self.input_secrets.items():
            self.output_encrypted[key] = self._crypto.encrypt(value)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Mixing Concerns

```python
# ❌ BAD: Process does too much
class ProcessHandleChangeRequest(AtomarProcess):
    async def execute_impl(self):
        # This is actually an orchestrated workflow!
        repo = self.clone_repo()
        self.create_branch()
        self.run_claude()
        self.commit()
        self.push()
        self.create_pr()
```

**Solution:** If you're calling multiple distinct operations, it's an OrchestratedProcess.

### Pitfall 2: Accessing Outputs Too Early

```python
# ❌ BAD: Accessing output in orchestrate()
def orchestrate(self):
    step1 = ProcessLoadData()
    self.add_child(step1)

    # ERROR: step1 hasn't executed yet!
    step2 = ProcessTransform(data=step1.output_data)
    self.add_child(step2)
```

**Solution:** Use `after_children_executed()` or parameter connections.

### Pitfall 3: God Processes

```python
# ❌ BAD: One process that does everything
class ProcessDoEverything(AtomarProcess):
    async def execute_impl(self):
        # 500 lines of code...
```

**Solution:** Each process should have ONE clear responsibility. If it's getting big, split it.

### Pitfall 4: Not Using Logging

```python
# ❌ BAD: Silent execution
async def execute_impl(self):
    result = do_something()
    return result

# ✅ GOOD: Observable execution
async def execute_impl(self):
    self.logger.info(f"Starting with input: {self.input_data}")
    result = do_something()
    self.logger.info(f"Completed with output: {result}")
    self.output_result = result
```

---

## Real-World Example: CodePilot Pipeline

The CodePilot API uses sWFME for its Change Request processing pipeline:

```
AgentExecutionPipeline
├── ProcessEnsureRepoCloned      (Clone or open cached repo)
├── ProcessInitProjectContext    (Create CLAUDE.md if needed)
├── ProcessSyncRepo              (Git fetch + reset to origin/main)
├── ProcessInjectLearnings       (Load context from learnings.md)
├── ProcessCreateBranch          (Create feature branch)
├── ProcessExecuteClaude         (Run Claude CLI)
├── ProcessUpdateLearnings       (Save learnings from execution)
├── ProcessCommitChanges         (Git add + commit)
├── ProcessPushBranch            (Git push)
├── ProcessCreatePR              (GitHub API: create PR)
├── ProcessMergePR               (GitHub API: merge PR)
└── ProcessUpdateCRStatus        (Update database status)
```

**Key Design Decisions:**

1. **Each step is isolated** - Can test ProcessCreateBranch without full pipeline
2. **Services are injected** - GitService, ClaudeService, GitHubService
3. **Attribute-based I/O** - Clear typing, easy to debug
4. **Graceful degradation** - Push failure doesn't crash everything
5. **Event logging** - Every step emits events for UI tracking

### Directory Structure

```
app/
├── processes/
│   ├── __init__.py
│   ├── atomic/
│   │   ├── __init__.py
│   │   ├── ensure_repo_cloned.py
│   │   ├── create_branch.py
│   │   ├── commit_changes.py
│   │   ├── push_branch.py
│   │   ├── create_pr.py
│   │   ├── merge_pr.py
│   │   ├── execute_claude.py
│   │   └── ...
│   └── orchestrated/
│       ├── __init__.py
│       └── agent_execution_pipeline.py
├── services/
│   ├── git_service.py
│   ├── github_service.py
│   ├── claude_service.py
│   └── storage_service.py
└── domain/
    ├── project.py
    ├── change_request.py
    └── user.py
```

---

## Testing Strategies

### Unit Test Atomic Processes

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

async def test_process_create_branch():
    # Arrange
    mock_git_service = MagicMock()
    mock_git_service.create_branch = AsyncMock()
    mock_repo = MagicMock()

    process = ProcessCreateBranch(
        git_service=mock_git_service,
        repo=mock_repo,
        branch_name="feature/test",
    )

    # Act
    await process.execute()

    # Assert
    mock_git_service.create_branch.assert_called_once_with(
        mock_repo, "feature/test"
    )
    assert process.output_success is True
```

### Integration Test Orchestrated Processes

```python
async def test_pipeline_end_to_end():
    # Use real services with test fixtures
    git_service = GitService(projects_base=tmp_path)
    github_service = GitHubService()  # With test token

    pipeline = AgentExecutionPipeline(
        git_service=git_service,
        github_service=github_service,
        project=test_project,
        change_request=test_cr,
    )

    await pipeline.execute()

    assert pipeline.output_success is True
    assert pipeline.output_pr_url is not None
```

### Mock Services, Not Processes

```python
# ❌ DON'T: Mock the process
mock_process = MagicMock(spec=ProcessCreateBranch)

# ✅ DO: Mock the service the process uses
mock_git_service = MagicMock()
mock_git_service.create_branch = AsyncMock(return_value=True)

process = ProcessCreateBranch(git_service=mock_git_service, ...)
await process.execute()
```

---

## Production Checklist

### Before Deploying a New Process:

- [ ] **Single Responsibility**: Does this process do ONE thing?
- [ ] **Clear I/O**: Are inputs and outputs documented and typed?
- [ ] **Logging**: Does it log start, completion, and errors?
- [ ] **Error Handling**: Does it handle failures gracefully?
- [ ] **Testable**: Can you unit test it with mocked services?
- [ ] **Named Properly**: Does the name describe what it does?

### Before Deploying a Pipeline:

- [ ] **All steps defined**: Is the workflow complete?
- [ ] **Dependencies clear**: Are step dependencies explicit?
- [ ] **Graceful degradation**: What happens if step N fails?
- [ ] **Events emitted**: Can the UI track progress?
- [ ] **Idempotent**: Can it be retried safely?
- [ ] **Integration tested**: Does the full flow work?

### Monitoring in Production:

- [ ] **Metrics enabled**: Are you collecting execution times?
- [ ] **Alerts configured**: Do you know when processes fail?
- [ ] **Logs searchable**: Can you trace a specific execution?
- [ ] **Dashboard available**: Can ops see process status?

---

## Quick Reference

### Process Template

```python
"""Process description - what it does."""
from __future__ import annotations

from typing import Optional
from swfme.core.process import AtomarProcess

from app.services.my_service import MyService


class ProcessDoSomething(AtomarProcess):
    """One-line description.

    Input:
        - input_name (Type): Description

    Output:
        - output_name (Type): Description
    """

    def __init__(
        self,
        my_service: MyService,
        some_input: str,
    ):
        super().__init__(name="DoSomething")
        self._my_service = my_service
        self.input_some_input = some_input

        # Outputs
        self.output_result: Optional[str] = None

    def define_parameters(self) -> None:
        """Using attribute-based I/O."""
        pass

    async def execute_impl(self) -> None:
        """Execute the process."""
        self.logger.info(f"Starting with input: {self.input_some_input}")

        result = await self._my_service.do_something(self.input_some_input)

        self.output_result = result
        self.logger.info(f"Completed with output: {self.output_result}")
```

### Pipeline Template

```python
"""Pipeline description."""
from swfme.core.process import OrchestratedProcess, SEQUENTIAL

from app.processes.atomic import ProcessStepOne, ProcessStepTwo


class MyPipeline(OrchestratedProcess):
    """Pipeline that does X, Y, Z.

    Steps:
        1. StepOne - Description
        2. StepTwo - Description

    Input:
        - input_data: Description

    Output:
        - output_result: Description
    """

    def __init__(self, service: Service, input_data: str):
        super().__init__(name="MyPipeline")
        self._service = service
        self.input_data = input_data
        self.output_result: Optional[str] = None

    def define_parameters(self) -> None:
        pass

    def orchestrate(self) -> None:
        self._step_one = ProcessStepOne(
            service=self._service,
            data=self.input_data,
        )
        self.add_child(self._step_one, SEQUENTIAL)

    async def after_children_executed(self) -> None:
        step_one_output = self._step_one.output_result

        step_two = ProcessStepTwo(
            service=self._service,
            data=step_one_output,
        )
        await step_two.execute()

        self.output_result = step_two.output_result
```

---

## Summary

1. **Services provide capabilities, Processes orchestrate workflows**
2. **Use attribute-based I/O for clarity and type safety**
3. **Inject dependencies via constructor**
4. **Use `after_children_executed()` for dynamic pipelines**
5. **Each process = one responsibility**
6. **Log everything, handle errors gracefully**
7. **Test services in isolation, test pipelines end-to-end**

---

**Happy Process-Oriented Programming! 🚀**

*Based on real-world experience from CodePilot API and other production systems.*
