import queue
import time
from threading import Lock, Thread
from typing import Any, Dict, List, Tuple

import rdflib
from abi import logger
from abi.services.object_storage.ObjectStoragePort import (
    Exceptions as ObjectStorageExceptions,
)
from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from abi.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import (
    TripleStoreService__SecondaryAdaptor__FileBase,
)
from abi.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from abi.utils.Workers import Job, WorkerPool
from rdflib import Graph, Node, URIRef, query


class TripleStoreService__SecondaryAdaptor__ObjectStorage(
    ITripleStorePort, TripleStoreService__SecondaryAdaptor__FileBase
):
    __object_storage_service: ObjectStorageService

    __triples_prefix: str

    __live_graph: Graph

    __lock: Lock

    def __init__(
        self,
        object_storage_service: ObjectStorageService,
        triples_prefix: str = "triples",
    ):
        logger.debug("Initializing TripleStoreService__SecondaryAdaptor__ObjectStorage")
        self.__object_storage_service = object_storage_service
        self.__triples_prefix = triples_prefix

        self.__lock = Lock()

        self.__insert_pool = WorkerPool(num_workers=50)

        self.__live_graph = self.load()

    def load_triples(self, subject_hash: str) -> Graph:
        obj: bytes = self.__object_storage_service.get_object(
            prefix=self.__triples_prefix, key=f"{subject_hash}.ttl"
        )

        content: str = obj.decode("utf-8")

        return Graph().parse(data=str(content), format="turtle")

    def store(self, name: str, triples: Graph):
        serialized_triples = triples.serialize(format="turtle").encode("utf-8")
        self.__object_storage_service.put_object(
            prefix=self.__triples_prefix, key=f"{name}.ttl", content=serialized_triples
        )

    def insert(self, triples: Graph):
        with self.__lock:
            triples_by_subject: Dict[Node, List[Tuple[Node, Node]]] = (
                self.triples_by_subject(triples)
            )

            def __insert(
                subject: URIRef, triples_by_subject: Dict[Node, List[Tuple[Node, Node]]]
            ):
                subject_hash = self.iri_hash(subject)

                try:
                    graph = self.load_triples(subject_hash)
                except ObjectStorageExceptions.ObjectNotFound:
                    graph = Graph()
                    for prefix, namespace in triples.namespaces():
                        graph.bind(prefix, namespace)

                for p, o in triples_by_subject[subject]:
                    graph.add((subject, p, o))

                self.store(subject_hash, graph)

            jobs: List[Job] = [
                Job(
                    queue=None,
                    func=__insert,
                    subject=subject,
                    triples_by_subject=triples_by_subject,
                )
                for subject in triples_by_subject
            ]

            result_queue: queue.Queue[Job] = self.__insert_pool.submit_all(jobs)

            while result_queue.qsize() < result_queue.maxsize:
                logger.debug(f"Inserting {result_queue.qsize()}/{result_queue.maxsize}")
                time.sleep(0.1)

            for prefix, namespace in triples.namespaces():
                self.__live_graph.bind(prefix, namespace)

            self.__live_graph += triples

    def remove(self, triples: Graph):
        with self.__lock:
            triples_by_subject: Dict[Any, List[Tuple[Any, Any]]] = (
                self.triples_by_subject(triples)
            )

            for subject in triples_by_subject:
                subject_hash = self.iri_hash(subject)

                try:
                    graph = self.load_triples(subject_hash)
                    for p, o in triples_by_subject[subject]:
                        graph.add((subject, p, o))

                    self.store(subject_hash, graph)
                except ObjectStorageExceptions.ObjectNotFound:
                    pass

            for prefix, namespace in triples.namespaces():
                self.__live_graph.bind(prefix, namespace)

            self.__live_graph -= triples

    def get_subject_graph(self, subject: str | URIRef) -> Graph:
        subject_hash = (
            self.iri_hash(URIRef(subject))
            if isinstance(subject, str)
            else self.iri_hash(subject)
        )

        try:
            graph = self.load_triples(subject_hash)
            return graph
        except ObjectStorageExceptions.ObjectNotFound:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")

    def load(self) -> Graph:
        with self.__lock:
            logger.debug("Loading triples from object storage")
            triples = Graph()

            # Queue to stream files as they are discovered
            files_queue: queue.Queue[str] = queue.Queue()
            worker_pool = WorkerPool(num_workers=50)
            result_queue: queue.Queue[Job] = queue.Queue()
            job_nbr = 0

            def list_objects_worker(files_queue: queue.Queue):
                try:
                    self.__object_storage_service.list_objects(
                        prefix=self.__triples_prefix, queue=files_queue
                    )
                except ObjectStorageExceptions.ObjectNotFound:
                    pass

            list_object_thread = Thread(
                target=list_objects_worker, args=(files_queue,), daemon=True
            )
            list_object_thread.start()

            # Process files as they are discovered
            while not files_queue.empty() or list_object_thread.is_alive():
                try:
                    file: str = files_queue.get(timeout=1.0)

                    file_hash = file.split("/")[-1].split(".")[0]
                    worker_pool.submit(
                        Job(
                            queue=result_queue,
                            func=self.load_triples,
                            subject_hash=file_hash,
                        )
                    )
                    job_nbr += 1
                except queue.Empty:
                    continue

            # Consume completed jobs.
            completed_jobs = 0
            while completed_jobs < job_nbr:
                logger.debug(f"{completed_jobs}/{job_nbr}")
                try:
                    job = result_queue.get(timeout=1.0)
                    if job.is_completed():
                        result_graph = job.get_result()
                        triples += result_graph

                        for prefix, namespace in result_graph.namespaces():
                            triples.bind(prefix, namespace)

                        completed_jobs += 1
                except queue.Empty:
                    continue

            logger.debug(f"Loaded {len(triples)} triples")

            logger.debug("Joining list objects thread")
            list_object_thread.join()

            logger.debug("Shutting down worker pool")
            worker_pool.shutdown()

            logger.debug("Done")

            return triples

    def get(self) -> Graph:
        return self.__live_graph

    def query(self, query: str) -> query.Result:
        with self.__lock:
            return self.get().query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        with self.__lock:
            return self.get().query(query)

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        pass
