import gc
from pathlib import Path


def render_dayplot_worker(task, settings_dict):
    """
    DISPOSABLE WORKER: This function runs in a fresh process.
    The process is destroyed immediately after this returns.
    """
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    from obspy import read

    try:
        data_path = task["mseed_path"]
        plot_path = task["plot_path"]

        # Load Data
        st = read(str(data_path))

        # Pre-processing
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

        plt.close("all")
        del st, tr
        gc.collect()

        return f"Dayplot updated: {plot_filename.name}"

    except Exception as e:
        return f"Plotting Error for {task.get('mseed_path')}: {e}"
