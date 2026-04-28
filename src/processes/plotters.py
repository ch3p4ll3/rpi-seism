import logging
import time
from multiprocessing import Event, Pool, Process, Queue
from os import getpid
from queue import Empty

from src.utils.dayplot_render import render_dayplot_worker


class Plotters(Process):
    def __init__(
        self,
        settings,  # This is the Settings object
        plot_queue: Queue,
        shutdown_event: Event,
        log_queue: Queue,
    ):
        super().__init__(name="PlottersProcess")
        # Extract settings to a serializable dict for the pool workers
        self.settings_dict = {
            "enabled": settings.jobs_settings.dayplot.enabled,
            "low_cutoff": settings.jobs_settings.dayplot.low_cutoff,
            "high_cutoff": settings.jobs_settings.dayplot.high_cutoff,
            "shutdown_timeout": 10.0,  # 10s grace period for writer to finish
        }
        self.plot_queue = plot_queue
        self.shutdown_event = shutdown_event
        self.log_queue = log_queue

    def run(self):
        if not self.settings_dict["enabled"]:
            return

        from src.logger import configure_worker_logging

        configure_worker_logging(self.log_queue)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Plotters Manager started. PID: %d", getpid())

        # processes=1: Do one plot at a time to save RAM
        # maxtasksperchild=1: KILL the process after 1 task to prevent OOM
        with Pool(processes=1, maxtasksperchild=1) as pool:
            drain_start_time = None
            writer_finished = False

            while True:
                try:
                    # Check for a task (1s timeout to keep loop responsive)
                    try:
                        task = self.plot_queue.get(timeout=1.0)
                    except Empty:
                        task = "EMPTY"

                    # Handle Writer Shutdown Sentinel (None)
                    if task is None:
                        self.logger.info(
                            "Writer finished signal received. Draining for 10s..."
                        )
                        writer_finished = True
                        drain_start_time = time.time()
                        continue

                    # Handle actual plot tasks
                    if isinstance(task, dict):
                        pool.apply_async(
                            render_dayplot_worker,
                            args=(task, self.settings_dict),
                            callback=self.logger.info,  # Logs the success string from worker
                        )

                    # Case A: Writer sent 'None', wait 10s for final data to clear
                    if writer_finished:
                        if (
                            time.time() - drain_start_time
                            > self.settings_dict["shutdown_timeout"]
                        ):
                            self.logger.info("Grace period complete. Closing Pool.")
                            break

                    # Case B: Global shutdown event (Ctrl+C), fallback timer
                    elif self.shutdown_event.is_set():
                        if drain_start_time is None:
                            drain_start_time = time.time()
                            self.logger.warning(
                                "Global shutdown. Waiting 10s for writer cleanup..."
                            )

                        if (
                            time.time() - drain_start_time
                            > self.settings_dict["shutdown_timeout"]
                        ):
                            self.logger.info("Safety timeout reached. Force closing.")
                            break

                except Exception:
                    self.logger.exception("Error in Plotters manager loop")

            # Finalize the pool
            pool.close()
            pool.join()

        self.logger.info("Plotters process stopped.")
