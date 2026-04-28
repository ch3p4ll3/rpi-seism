import logging
from logging import config, handlers

def setup_main_logging(base_path, queue):
    """Called only in main.py. Configures the 'real' destination of logs."""
    log_dir = base_path / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
            "detailed": {"format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": str(log_dir / 'daemon.log'),
                "when": "midnight",
                "interval": 1,
                "backupCount": 7,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
    }

    # Apply the config to the main process
    logging.config.dictConfig(logging_config)
    
    # Get the handlers we just created and give them to the listener
    # This captures everything sent to the queue and routes it through 'console' and 'file'
    root_handlers = logging.getLogger().handlers
    listener = handlers.QueueListener(queue, *root_handlers, respect_handler_level=True)
    listener.start()
    return listener

def configure_worker_logging(queue):
    """Called inside the run() method of each Process."""
    # Workers only need one handler: the QueueHandler
    qh = handlers.QueueHandler(queue)
    root = logging.getLogger()
    
    # Remove any default handlers inherited during spawn/fork
    for h in root.handlers[:]:
        root.removeHandler(h)
        
    root.addHandler(qh)
    root.setLevel(logging.DEBUG)
