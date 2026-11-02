"""Main Entry Point for Entry Strategy Matrix Application."""
import sys
import logging
from entrystrategy.config import AppConfig
from entrystrategy.service import EntryStrategyService
from entrystrategy.gui.app import launch_gui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    config = AppConfig()
    service = EntryStrategyService(config)
    try:
        launch_gui(service)
    except KeyboardInterrupt:
        service.stop()
        sys.exit(0)
