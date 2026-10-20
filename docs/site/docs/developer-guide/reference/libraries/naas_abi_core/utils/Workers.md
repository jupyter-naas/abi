# Workers

## What it is
A small threading-based worker pool for running callable jobs asynchronously, tracking job status, and optionally collecting completed jobs via a result queue.

## Public API

- `JobStatus (Enum)`
  - `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `RESULT_FETCHED`

- `class Job`
  - `Job(queue: Optional[Queue], func: Callable, *args, **kwargs)`: wraps a callable and its arguments; assigns a UUID `id`.
  - `execute()`: runs the callable; updates status; captures exceptions; signals completion; optionally enqueues itself into `queue`.
  - `wait(timeout: Optional[float] = None) -> bool`: blocks until completion (or timeout).
  - `is_completed() -> bool`: `True` if status is `COMPLETED` or `FAILED`.
  - `get_result()`: marks status as `RESULT_FETCHED`; returns result or re-raises captured error.

- `class WorkerPool`
  - `WorkerPool(num_workers: int)`: starts `num_workers` daemon threads consuming an internal job queue.
  - `submit(job: Job)`: enqueue a single job for execution.
  - `submit_all(jobs: List[Job]) -> Queue[Job]`: enqueue multiple jobs; returns a `Queue` that receives each job after it finishes. If a job’s `queue` is `None`, it is set to this returned queue.
  - `shutdown()`: signals workers to stop and joins threads.

## Configuration/Dependencies
- Uses standard library: `threading`, `queue`, `uuid`, `enum`, `typing`.
- Logs failures and shutdown via `naas_abi_core.logger`.

## Usage

### Submit one job and wait for its result
```python
from naas_abi_core.utils.Workers import Job, WorkerPool

def add(a, b):
    return a + b

pool = WorkerPool(num_workers=2)
job = Job(queue=None, func=add, a=2, b=3)

pool.submit(job)
job.wait()               # blocks until done
print(job.get_result())  # 5

pool.shutdown()
```

### Submit multiple jobs and collect completions via the returned queue
```python
from queue import Empty
from naas_abi_core.utils.Workers import Job, WorkerPool

def square(x): 
    return x * x

pool = WorkerPool(num_workers=2)
jobs = [Job(queue=None, func=square, x=i) for i in range(3)]

done_q = pool.submit_all(jobs)

completed = []
while len(completed) < len(jobs):
    try:
        j = done_q.get(timeout=2)
        completed.append((j.id, j.get_result()))
    except Empty:
        break

print(completed)
pool.shutdown()
```

## Caveats
- Worker threads are daemon threads; call `shutdown()` to stop cleanly.
- `shutdown()` may block up to ~1 second per worker due to the `get(timeout=1.0)` loop.
- `Job.get_result()` sets status to `RESULT_FETCHED` even if the job is still running; callers should `wait()`/ensure completion before retrieving results.
