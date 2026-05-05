import logging
import time
from multiprocessing import Event, Process, Queue
from os import getpid

import serial
import zmq
from rpi_seism_common.settings import Settings

from src.logger import configure_worker_logging
from src.structs.sample import Sample
from src.utils.soh_tracker import SOHTracker


class OnaviReader(Process):
    """
    Process that continuously reads from the RS-422 serial port,
    processes incoming packets, and distributes data to queues.
    """

    def __init__(
        self,
        settings: Settings,
        shutdown_event: Event,
        zmq_endpoint: str,
        log_queue: Queue,
    ):
        super().__init__(name="ReaderProcess")
        self.port = settings.jobs_settings.reader.port
        self.settings = settings
        self.zmq_endpoint = zmq_endpoint
        self.shutdown_event = shutdown_event
        self.log_queue = log_queue
        self.soh_tracker = SOHTracker()

        self.queue_len = (
            self.settings.mcu.sampling_rate * len(self.settings.channels) * 60
        ) * 5  # 5 minutes of data at 100 Hz for 3 channels

        self.baudrate = settings.jobs_settings.reader.baudrate
        self.connection_timeout = 2.0
        self.last_heartbeat = 0
        self.last_soh_update = 0
        self.last_packet_time = 0

        self.channels = self.__map_channels()

    def run(self):
        configure_worker_logging(self.log_queue)

        self.logger = logging.getLogger(__name__)

        self.logger.info("Reader started. PID: %d", getpid())
        # Initialize ZeroMQ
        context = zmq.Context()
        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.set(zmq.SNDHWM, self.queue_len)
        self.pub_socket.bind(self.zmq_endpoint)

        interval = 1.0 / self.settings.mcu.sampling_rate

        # 1. Initialize if this is the very first run
        if self.last_packet_time == 0:
            self.last_packet_time = time.perf_counter()

        try:
            with serial.Serial(self.port, self.baudrate, timeout=0.1) as ser:
                self.logger.info(
                    "Connected to Onavi-B seismic sensor on %s at %d",
                    self.port,
                    self.baudrate,
                )

                while not self.shutdown_event.is_set():
                    now = time.perf_counter()

                    if now - self.last_packet_time >= interval:
                        # 2. Perform the work
                        sample = self.read(ser)
                        self._process_packet(sample)
                        self.soh_tracker.record_success()

                        # 3. Increment by fixed interval to prevent drift
                        self.last_packet_time += interval

                        # 4. CATCH-UP GUARD:
                        # If we are still behind (e.g., processing took too long),
                        # reset the clock to 'now' so we don't loop infinitely.
                        if now - self.last_packet_time > interval:
                            self.last_packet_time = now

                    if time.time() - self.last_soh_update > 5.0:
                        soh_stats = self.soh_tracker.get_snapshot()
                        # Send on a specific ZMQ topic or a different socket
                        self.pub_socket.send_pyobj({"type": "SOH", "data": soh_stats})
                        self.last_soh_update = time.time()

                    time.sleep(
                        0.0001
                    )  # Sleep briefly to yield control and prevent 100% CPU

        except Exception:
            self.logger.exception("Onavi Reader exception")
        finally:
            self.soh_tracker.set_disconnected()
            self.logger.info("Onavi Reader stopped.")
            self.shutdown_event.set()
            self.pub_socket.close()
            context.term()

    def _read_raw(self, ser):
        ser.write(b"\x2a")
        return ser.read(9)

    def read(self, ser) -> Sample:
        incoming = self._read_raw(ser)
    
        # 1. Validate packet length and headers (0x23 is '#')
        if len(incoming) < 9 or incoming[0] != 0x23 or incoming[1] != 0x23:
            # If headers are wrong, the buffer is out of sync.
            ser.reset_input_buffer() 
            return None 

        # 16-bit Reconstruction (Big Endian)
        # Using (MSB << 8) | LSB is the standard, cleanest way.
        x_raw = (incoming[2] << 8) | incoming[3]
        y_raw = (incoming[4] << 8) | incoming[5]
        z_raw = (incoming[6] << 8) | incoming[7]

        # Correct Scaling Constants
        # (5 / 65536) = 7.62939453125e-05
        SCALE = 7.629394531250e-05
        EARTH_G = 9.78033

        # Calculate g values and convert to m/s^2
        # Formula: (Raw - Offset) * Scale * Gravity
        x = (x_raw - 32768.0) * SCALE * EARTH_G
        y = (y_raw - 32768.0) * SCALE * EARTH_G
        z = (z_raw - 32768.0) * SCALE * EARTH_G

        # Note: Documentation says Z offset is different (+1g at 45874)
        # If you want Z to be 0 when sitting flat, use 45874 instead of 32768:
        # z = (z_raw - 45874.0) * SCALE * EARTH_G

        return Sample(header_1=0xAA, header_2=0xBB, ch0=z_raw, ch1=x_raw, ch2=y_raw, crc=0)

    def _process_packet(self, data: Sample):
        timestamp = time.time()
        packet = data.to_dict(timestamp, self.channels)

        self.pub_socket.send_pyobj(packet)

    def __map_channels(self):
        return {i.adc_channel: i for i in self.settings.channels}
