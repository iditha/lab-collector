"""Runs a collection in a background thread, so the window stays responsive.

The worker lives in its own QThread. It talks to the window only through signals:
Qt delivers each signal to the window's thread, so the window's widgets are only
ever touched from the window's own thread (Qt requires this).
"""

import logging
import threading

from PySide6.QtCore import QObject, Signal, Slot

from labcollector.config_models import AppConfig
from labcollector.records import Run
from labcollector.services.collection_service import CollectionService

log = logging.getLogger(__name__)


class CollectionWorker(QObject):
    progress = Signal(int, int, str)  # files done, total files, message
    finished = Signal(object)  # the saved Collection
    failed = Signal(str)  # an error message, if the collection couldn't even be saved

    def __init__(self, service: CollectionService, run: Run, config: AppConfig):
        super().__init__()
        self._service = service
        self._run = run
        self._config = config
        self._cancel = threading.Event()  # thread-safe flag: set by the window, read here

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            collection = self._service.collect(
                self._run,
                self._config,
                progress=self.progress.emit,
                should_cancel=self._cancel.is_set,
            )
        except Exception as error:  # e.g. the database can't be written
            log.exception("Collection failed")
            self.failed.emit(str(error))
            return
        self.finished.emit(collection)
