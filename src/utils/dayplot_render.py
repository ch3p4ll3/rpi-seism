def render_dayplot_worker(task, settings_dict, log_queue):
    """
    DISPOSABLE WORKER: This function runs in a fresh process.
    We pass log_queue to allow the worker to log messages safely.
    """
    # Setup Logging for this specific worker process
    import logging

    from src.logger import configure_worker_logging

    configure_worker_logging(log_queue)
    logger = logging.getLogger(__name__)

    # Local Imports to keep process startup light
    import matplotlib

    matplotlib.use("Agg")
    import gc
    from pathlib import Path

    import matplotlib.pyplot as plt
    from obspy import read

    try:
        data_path = task["mseed_path"]
        plot_path = task["plot_path"]

        logger.debug(f"Starting render for {Path(data_path).name}")

        # Processing Logic
        st = read(str(data_path))
        st.detrend("linear")
        st.taper(max_percentage=0.05)
        st.filter(
            "bandpass",
            freqmin=settings_dict["low_cutoff"],
            freqmax=settings_dict["high_cutoff"],
        )

        plot_filename = Path(plot_path).with_suffix(".png")
        tr = st[0]

        # Generate Plot
        st.plot(
            type="dayplot",
            color=["black", "red", "blue", "green"],
            title=f"Helicorder: {tr.id} | {tr.stats.starttime.strftime('%Y-%j')}",
            size=(1600, 1200),
            dpi=200,
            outfile=str(plot_filename),
            show=False,
        )

        # Cleanup
        plt.close("all")
        del st, tr
        gc.collect()

        # Log success from inside the worker
        logger.info(f"Dayplot updated: {plot_filename.name}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate plot for {task.get('mseed_path')}: {e}")
        return False
