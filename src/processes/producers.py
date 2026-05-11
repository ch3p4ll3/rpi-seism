import logging
from multiprocessing import Event, Process, Queue
from pathlib import Path

from rpi_seism_common.settings import Settings

from src.logger import configure_worker_logging


class Producers(Process):
    def __init__(
        self,
        settings: Settings,
        data_base_folder: Path,
        shutdown_event: Event,
        trigger_event: Event,
        plot_queue: Queue,
        zmq_addr: str,
        log_queue: Queue,
    ):
        # CRITICAL: Call super constructor
        super().__init__(name="ProducersProcess")
        self.settings = settings
        self.data_base_folder = data_base_folder
        self.shutdown_event = shutdown_event
        self.trigger_event = trigger_event
        self.plot_queue = plot_queue
        self.zmq_addr = zmq_addr
        self.log_queue = log_queue

    def run(self):
        try:
            from src.threads.producers import (
                MSeedWriter,
                TriggerProcessor,
                WebSocketSender,
            )

            configure_worker_logging(self.log_queue)

            self.logger = logging.getLogger(__name__)

            self.logger.info("Starting Producers Process (Reader + Trigger + Writer)")

            jobs = []

            writer_job = MSeedWriter(
                self.settings,
                self.data_base_folder,
                self.shutdown_event,
                self.trigger_event,
                self.plot_queue,
                self.zmq_addr,
            )
            jobs.append(writer_job)

            trigger_job = TriggerProcessor(
                self.settings, self.shutdown_event, self.trigger_event, self.zmq_addr
            )
            jobs.append(trigger_job)

            websocket_job = WebSocketSender(
                self.settings, self.shutdown_event, self.trigger_event, self.zmq_addr
            )
            jobs.append(websocket_job)

            for job in jobs:
                job.start()

            try:
                # Monitor threads while checking for the global shutdown signal
                while not self.shutdown_event.is_set():
                    for job in jobs:
                        job.join(timeout=0.1)
                        if not job.is_alive() and not self.shutdown_event.is_set():
                            self.logger.error(
                                "Manager thread %s died unexpectedly", job.name
                            )
                            self.shutdown_event.set()  # Kill everything if a core thread dies
                            break

            except Exception as e:
                import traceback

                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.logger.error(
                    "Error in Producers process container: %s",
                    error_msg,
                    exc_info=False,
                )
                self.shutdown_event.set()
            finally:
                self.logger.info("Cleaning up Producer threads...")
                for job in jobs:
                    if job.is_alive() and isinstance(job, MSeedWriter):
                        job.join(timeout=30.0)
                    else:
                        job.join(timeout=5.0)
                self.logger.info("Producers process stopped.")
        except Exception as e:
            import traceback

            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.logger.error("Error in Producers process: %s", error_msg)
