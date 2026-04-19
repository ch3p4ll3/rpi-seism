import logging
from multiprocessing import Event, Process, Queue
from pathlib import Path

logger = logging.getLogger(__name__)


class Producers(Process):
    def __init__(
        self,
        settings,
        data_base_folder: Path,
        shutdown_event: Event,
        trigger_event: Event,
        plot_queue: Queue,
        zmq_addr: str,
    ):
        # CRITICAL: Call super constructor
        super().__init__(name="ProducersProcess")
        self.settings = settings
        self.data_base_folder = data_base_folder
        self.shutdown_event = shutdown_event
        self.trigger_event = trigger_event
        self.plot_queue = plot_queue
        self.zmq_addr = zmq_addr

    def run(self):
        from src.threads.producers import MSeedWriter, Reader, TriggerProcessor

        logger.info("Starting Producers Process (Reader + Trigger + Writer)")

        reader_job = Reader(self.settings, self.shutdown_event, self.zmq_addr)

        writer_job = MSeedWriter(
            self.settings,
            self.data_base_folder,
            self.shutdown_event,
            self.trigger_event,
            self.plot_queue,
            self.zmq_addr,
        )

        trigger_job = TriggerProcessor(
            self.settings, self.shutdown_event, self.trigger_event, self.zmq_addr
        )

        reader_job.start()
        writer_job.start()
        trigger_job.start()

        try:
            # Monitor threads while checking for the global shutdown signal
            while not self.shutdown_event.is_set():
                # Timeout-based joins to keep the loop responsive
                reader_job.join(timeout=0.1)
                writer_job.join(timeout=0.1)
                trigger_job.join(timeout=0.1)

                # Check for actual crashes
                if not self.shutdown_event.is_set():
                    dead_threads = []

                    if not reader_job.is_alive():
                        dead_threads.append("Reader")
                    if not writer_job.is_alive():
                        dead_threads.append("Writer")
                    if not trigger_job.is_alive():
                        dead_threads.append("Trigger")
                    
                    if dead_threads:
                        logger.error(f"Producer thread(s) died unexpectedly: {', '.join(dead_threads)}")
                        break

        except Exception:
            logger.exception("Error in Producers process container")
            self.shutdown_event.set()
        finally:
            logger.info("Cleaning up Producer threads...")
            reader_job.join(timeout=2.0)
            writer_job.join(timeout=20)
            trigger_job.join(timeout=2.0)
            logger.info("Producers process stopped.")
