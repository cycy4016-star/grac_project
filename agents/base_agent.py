"""
Base class for all GRaC agents.
Provides common functionality like logging, sector management, error handling.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from config.settings import settings
from utils.logger import get_logger, log_execution_event
from utils.file_handler import file_handler
from utils.sector_manager import sector_manager


class BaseAgent(ABC):
    """
    Abstract base class for all agents in GRaC.
    
    Each agent extends this and implements:
    - execute(): The main job the agent does
    - validate_input(): Input validation
    - format_output(): Output formatting
    """
    
    def __init__(self, name: str, sector: Optional[str] = None):
        """
        Initialize agent.
        
        Args:
            name: Agent name (e.g., "IngestorAgent", "ParserAgent")
            sector: Active sector (defaults to settings.ACTIVE_SECTOR)
        """
        self.name = name
        self.sector = sector or settings.ACTIVE_SECTOR
        self.logger = self._setup_logger()
        self.start_time = None
        self.execution_log = {}
        
        # Verify sector exists
        self._verify_sector()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup structured JSON logging for this agent via utils.logger."""
        return get_logger(self.name)
    
    def _verify_sector(self) -> None:
        """Verify the sector is valid and ensure its directory tree exists."""
        sector_manager.validate_sector(self.sector)

        # Ensure the full directory tree exists for this sector
        sector_manager._ensure_sector_dirs(self.sector)
        self.logger.info(f"Agent initialized for sector: {self.sector}")
    
    def switch_sector(self, new_sector: str) -> None:
        """
        Switch agent to a different sector.
        (MVP mode only - single sector at a time)
        """
        if settings.ENABLE_MULTI_SECTOR:
            self.logger.warning("Cannot switch sector in multi-sector mode")
            return

        self.logger.info(f"Switching sector from {self.sector} to {new_sector}")
        self.sector = new_sector
        self._verify_sector()
        sector_manager.switch_sector(new_sector)
    
    def get_sector_path(self, subfolder: str = "") -> Path:
        """
        Get path to current sector's directory.
        
        Args:
            subfolder: Optional subfolder (raw, parsed, chunks)
        
        Returns:
            Path to sector directory
        """
        base_path = settings.get_sector_laws_path(self.sector)
        if subfolder:
            return base_path / subfolder
        return base_path
    
    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input before processing.
        
        Must be implemented by subclass.
        
        Returns:
            True if input is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def execute(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Main execution method.
        
        Must be implemented by subclass.
        
        Returns:
            Dictionary with results
        """
        pass
    
    @abstractmethod
    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format result for downstream agents.
        
        Must be implemented by subclass.
        
        Returns:
            Formatted output
        """
        pass
    
    def describe_capabilities(self) -> Dict[str, Any]:
        """
        Return a description of what this agent can do.
        
        Agents should override this to provide their specific capabilities.
        
        Returns:
            Dictionary with name and description of capabilities
        """
        return {
            "name": self.name,
            "sector": self.sector,
            "description": self.__doc__.strip() if self.__doc__ else "",
            "input_type": "dict",
        }

    def run(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Main entry point. Orchestrates validation, execution, logging.
        
        Args:
            input_data: Input to process
            **kwargs: Additional arguments
        
        Returns:
            Formatted output
        """
        try:
            self.start_time = datetime.now()
            self.logger.info(f"Starting execution with input: {input_data}")
            
            # Step 1: Validate
            if not self.validate_input(input_data):
                error = f"Invalid input: {input_data}"
                self.logger.error(error)
                return self._error_output(error)
            
            self.logger.info("Input validation passed")
            
            # Step 2: Execute
            result = self.execute(input_data, **kwargs)
            
            # Step 3: Format
            output = self.format_output(result)
            
            # Step 4: Log execution
            self._log_execution(input_data, output, "success")
            self.logger.info(f"Execution completed successfully")
            
            return output
        
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return self._error_output(error_msg)
    
    def _error_output(self, error: str) -> Dict[str, Any]:
        """Generate standardized error output."""
        return {
            "status": "error",
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "agent": self.name
        }
    
    def _log_execution(
        self,
        input_data: Any,
        output: Dict[str, Any],
        status: str
    ) -> None:
        """Log execution details via utils.logger.log_execution_event."""
        duration = (
            (datetime.now() - self.start_time).total_seconds()
            if self.start_time else None
        )
        self.execution_log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "sector": self.sector,
            "status": status,
            "duration_seconds": duration,
            "input_type": type(input_data).__name__,
            "output_keys": list(output.keys()) if isinstance(output, dict) else None,
        }
        log_execution_event(
            agent_name=self.name,
            event="execution_complete",
            sector=self.sector,
            status=status,
            duration_seconds=duration,
            extra={
                "input_type": type(input_data).__name__,
                "output_keys": self.execution_log["output_keys"],
            },
        )

    def _save_checkpoint(self, checkpoint_name: str, data: Dict[str, Any]) -> None:
        """Save intermediate results for debugging via utils.file_handler."""
        checkpoint_path = (
            settings.CACHE_DIR / self.name.lower() / f"{checkpoint_name}.json"
        )
        file_handler.write_json(checkpoint_path, data)
        self.logger.debug(f"Checkpoint saved: {checkpoint_path}")


class MultiSectorAgent(BaseAgent):
    """
    Extended agent class for multi-sector support (future).
    
    Allows agents to work with multiple sectors simultaneously
    when ENABLE_MULTI_SECTOR is True.
    """
    
    def __init__(self, name: str, sectors: Optional[List[str]] = None):
        """
        Initialize multi-sector agent.
        
        Args:
            name: Agent name
            sectors: List of sectors to work with (defaults to active sectors)
        """
        self.sectors = sectors or settings.get_active_sectors()
        super().__init__(name, sector=self.sectors[0])  # Primary sector
        
        self.logger.info(f"Multi-sector agent initialized for sectors: {self.sectors}")
    
    def get_all_sector_paths(self, subfolder: str = "") -> List[Path]:
        """Get paths for all active sectors."""
        paths = []
        for sector in self.sectors:
            base_path = settings.get_sector_laws_path(sector)
            if subfolder:
                path = base_path / subfolder
            else:
                path = base_path
            paths.append(path)
        return paths


# TODO: Implement remaining functionality
# - Metric tracking
# - Performance monitoring
# - Agent communication protocol
# - Result caching
# - Dependency injection
