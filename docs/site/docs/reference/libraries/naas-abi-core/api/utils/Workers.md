# Workers

## What it is
A small threaded worker pool utility for running Python callables asynchronously via `Job` objects, tracking status, and optionally collecting completed jobs via a results `Queue`.

## Public API

- `JobStatus (Enum)`
  - `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `RESULT_FETCHED`

- `class Job`
  - `Job(queue: Optional[Queue], func: Callable, *args, **kwargs)`
    - Creates a unit of work with a UUID `id`, status tracking, and optional completion-queue push.
  - `execute()`
    - Runs the callable, sets status, captures result or exception, signals completion, and pushes itself to `queue` if set.
  - `wait(timeout: Optional[float] = None) -> bool`
    - Blocks until completion (or timeout). Returns `True` if completed.
  - `is_completed() -> bool`
    - Returns `True` if status is `COMPLETED` or `FAILED`.
  - `get_result()`
    - Marks status as `RESULT_FETCHED`, re-raises captured exception if any, otherwise returns the result.

- `class WorkerPool`
  - `WorkerPool(num_workers: int)`
    - Starts `num_workers` daemon threads consuming jobs from an internal queue.
  - `submit(job: Job)`
    - Enqueues a single job for execution.
  - `submit_all(jobs: List[Job]) -> Queue[Job]`
    - Enqueues multiple jobs; assigns a shared results queue to jobs whose `job.queue` is `None`. Returns that queue.
  - `shutdown()`
    - Signals workers to stop and joins their threads.

## Configuration/Dependencies
- Uses standard library: `threading`, `queue`, `uuid`, `enum`, `typing`.
- Logs failures and shutdown debug messages via `naas_abi_core.logger`.

## Usage

```python
from queue import Empty
from naas_abi_core.utils.Workers import Job, WorkerPool

def add(a, b):
    return a + b

pool = WorkerPool(num_workers=2)

# Submit multiple jobs and collect them from the returned results queue
jobs = [Job(None, add, i, i) for i in range(3)]
results_q = pool.submit_all(jobs)

completed = []
while len(completed) < len(jobs):
    try:
        job = results_q.get(timeout=2)
        completed.append((job.id, job.get_result()))
    except Empty:
        break

print(completed)

pool.shutdown()
```

## Caveats
- Worker threads are daemon threads; call `shutdown()` to join them cleanly.
- `submit_all()` only assigns the returned results queue to jobs where `job.queue is None`; jobs constructed with an existing `queue` will push completion to that queue instead.
- `Job.get_result()` updates status to `RESULT_FETCHED` even if the job later raises its captured exception.
