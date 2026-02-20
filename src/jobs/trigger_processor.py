from threading import Thread, Event
from queue import Empty, Queue

from src.settings import Settings
from src.utils.sta_lta import STALTAProperty


class TriggerProcessor(Thread):
    def __init__(
        self,
        settings: Settings,
        data_queue: Queue,
        shutdown_event: Event,
        earthquake_event: Event
    ):
        super().__init__()
        self.data_queue = data_queue
        self.earthquake_event = earthquake_event
        self.shutdown_event = shutdown_event
        self.detector = STALTAProperty(sampling_rate=settings.sampling_rate)

        self.last_trigger = False

    def run(self):
        while not self.shutdown_event.is_set():
            try:
                # We don't want to block forever so we can check shutdown_event
                _, value, _ = self.data_queue.get(timeout=0.5)

                _, triggered = self.detector.process_sample(value)

                if triggered and not self.last_trigger:
                    # Logic: If newly triggered, send a special WS message
                    # or tell MSeedWriter to "mark" the current file.
                    self.earthquake_event.set()
                    self.last_trigger = True

                elif not triggered and self.last_trigger:
                    self.earthquake_event.clear()
                    self.last_trigger = False
                
                self.data_queue.task_done()
            except Empty:
                continue
