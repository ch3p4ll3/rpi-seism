from queue import Queue
from pathlib import Path

from src.settings import Settings
from src.jobs import Reader, MSeedWriter, WebSocketSender


def main():
    # Define paths and load settings
    data_base_folder = Path(__file__).parent.parent / "data"
    settings = Settings.load_settings()

    # Create queues for communication between jobs
    msed_writer_queue = Queue()
    websocket_queue = Queue()

    # Create and start the Reader job thread (reads from ADC, puts data in the queues)
    reader_job = Reader(settings, [msed_writer_queue, websocket_queue])
    reader_job.start()

    # Create and start the MSeedWriter job thread (writes data to MiniSEED file)
    m_seed_writer_job = MSeedWriter(settings, msed_writer_queue, data_base_folder, 1800)
    m_seed_writer_job.start()

    # Create and start the WebSocketSender job thread (sends data over WebSocket)
    websocket_job = WebSocketSender(websocket_queue)
    websocket_job.start()

    # Gracefully stop all threads
    reader_job.join()
    m_seed_writer_job.stop()
    websocket_job.stop()

    # Wait for all threads to finish
    m_seed_writer_job.join()
    websocket_job.join()

    print("All threads stopped and the main script has finished.")


if __name__ == "__main__":
    main()
