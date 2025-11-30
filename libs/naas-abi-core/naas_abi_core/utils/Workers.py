import uuid
from enum import Enum
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Callable, List, Optional

from naas_abi_core import logger


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RESULT_FETCHED = "result_fetched"


class Job:
    def __init__(self, queue: Optional[Queue], func: Callable, *args, **kwargs):
        self.id = str(uuid.uuid4())
        self.queue = queue
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status = JobStatus.PENDING
        self.result = None
        self.error = None
        self._completion_event = Event()
        self._lock = Lock()  # For thread-safe status updates

    def execute(self):
        """Execute the job - called by worker thread"""
        with self._lock:
            self.status = JobStatus.RUNNING

        try:
            self.result = self.func(*self.args, **self.kwargs)
            with self._lock:
                self.status = JobStatus.COMPLETED
        except Exception as e:
            self.error = e
            import traceback

            logger.error(f"Job {self.id} failed: {e}\n{traceback.format_exc()}")
            with self._lock:
                self.status = JobStatus.FAILED
        finally:
            self._completion_event.set()
            if self.queue:
                self.queue.put(self)

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for the job to complete"""
        return self._completion_event.wait(timeout)

    def is_completed(self) -> bool:
        """Check if the job is completed (successfully or with failure)"""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED)

    def get_result(self):
        """Get the job result, raising any error that occurred"""
        with self._lock:
            self.status = JobStatus.RESULT_FETCHED

        if self.error:
            raise self.error

        return self.result


class WorkerPool:
    def __init__(self, num_workers: int):
        self.job_queue: Queue[Job] = Queue()
        self.workers: List[Thread] = []
        self.shutdown_event = Event()

        # Start worker threads
        for _ in range(num_workers):
            worker = Thread(target=self._worker_loop)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        while not self.shutdown_event.is_set():
            try:
                # Get job from queue with timeout to check shutdown periodically
                job = self.job_queue.get(timeout=1.0)
                job.execute()
                self.job_queue.task_done()
            except Empty:
                continue

    def submit(self, job: Job):
        """Submit a job to the worker pool"""
        self.job_queue.put(job)

    def submit_all(self, jobs: List[Job]) -> Queue[Job]:
        """Submit multiple jobs to the worker pool"""
        queue: Queue[Job] = Queue(maxsize=len(jobs))

        for job in jobs:
            if job.queue is None:
                job.queue = queue
            self.submit(job)

        return queue

    def shutdown(self):
        """Shutdown the worker pool"""
        logger.debug("Shutting down worker pool")
        self.shutdown_event.set()
        for worker in self.workers:
            worker.join()
