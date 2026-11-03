"""Session state persistence for 'Continue where you left off' functionality."""
import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger("EntryStrategy.Persistence")

_file_lock = threading.Lock()
DEFAULT_STATE_FILENAME = "user_state.json"


def get_default_state_path() -> Path:
    """Returns absolute path to the session state JSON file."""
    # Place in the project root directory
    base_dir = Path(__file__).resolve().parent.parent.parent
    return base_dir / DEFAULT_STATE_FILENAME


def save_session_state(state: Dict[str, Any], filepath: Optional[Union[str, Path]] = None) -> bool:
    """Atomically saves the session state to a JSON file.
    
    Uses a temporary file and atomic replace to prevent corrupt files if
    the application terminates during a write operation.
    """
    target_path = Path(filepath) if filepath else get_default_state_path()
    tmp_path = target_path.with_suffix(".tmp")
    
    with _file_lock:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic replace
            os.replace(tmp_path, target_path)
            logger.debug(f"Saved session state successfully to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save session state to {target_path}: {e}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            return False


def load_session_state(filepath: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """Loads session state from JSON file. Returns None if file does not exist or is invalid."""
    target_path = Path(filepath) if filepath else get_default_state_path()
    
    with _file_lock:
        if not target_path.exists():
            return None
        
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                logger.info(f"Loaded session state successfully from {target_path}")
                return data
            logger.warning(f"Session state in {target_path} is not a valid dictionary.")
            return None
        except Exception as e:
            logger.error(f"Failed to load session state from {target_path}: {e}")
            return None


def clear_session_state(filepath: Optional[Union[str, Path]] = None) -> bool:
    """Removes the session state file."""
    target_path = Path(filepath) if filepath else get_default_state_path()
    with _file_lock:
        try:
            if target_path.exists():
                target_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to remove session state file {target_path}: {e}")
            return False
