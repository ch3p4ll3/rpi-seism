import time
from datetime import UTC, datetime, timedelta
from logging import getLogger
from threading import Event, Thread

from obspy import read_events
from rpi_seism_common.settings import Settings

logger = getLogger(__name__)


class AutomaticBookmarkCreator(Thread):
    def __init__(
        self, settings: Settings, shutdown_event: Event, earthquake_event: Event
    ):
        super().__init__()
        self.earthquake_event = earthquake_event
        self.shutdown_event = shutdown_event
        self.settings = settings

        self.last_trigger = False
        self.events: list[datetime] = []

    def run(self):
        logger.info("Trigger Processor (ObsPy Recursive STA/LTA) started.")

        while not self.shutdown_event.is_set():
            try:
                if self.earthquake_event.is_set() and not self.last_trigger:
                    self.last_trigger = True
                    self.events.append(datetime.now(UTC))

                elif not self.earthquake_event.is_set() and self.last_trigger:
                    self.last_trigger = False

                self._request_events()

                time.sleep(0.5)
            except Exception:
                logger.exception("Error in Trigger Processor loop")

        logger.info("Trigger Processor stopped.")

    def _request_events(self):
        now = datetime.now(UTC)

        self.events = [i for i in self.events if now - i <= timedelta(minutes=30)]

        for i in self.events:
            start = i - timedelta(minutes=5)
            end = i + timedelta(minutes=5)

            start = start.replace(tzinfo=None).isoformat()
            end = end.replace(tzinfo=None).isoformat()

            url = f"https://webservices.ingv.it/fdsnws/event/1/query?starttime={start}&endtime={end}&lat={self.settings.station.latitude}&lon={self.settings.station.longitude}&orderby=time&format=xml&includeallorigins=false&includeallmagnitudes=false&includearrivals=false"
            self._manage_events(url)

    def _manage_events(self, url: str):
        events = read_events(url)

        for event in events:
            origin = event.preferred_origin()
            magnitude = event.preferred_magnitude()
            event_descriptions = (
                event.event_descriptions[0] if event.event_descriptions else None
            )

            if origin is None:
                continue

            bookmark_start = origin.time - 20
            bookmark_end = origin.time + 40
