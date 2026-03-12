class StationXMLEpochError(Exception):
    """
    Raised when instrument settings have changed but start_date has not been
    updated. A new start_date is required to open a new response epoch.
    """
    pass
