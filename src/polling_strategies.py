"""
Polling Strategy Pattern Implementation

This module implements the Strategy pattern for different polling approaches,
allowing for flexible polling behavior configuration and future extensibility.
"""

import time
import math
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class PollingStrategyType(str, Enum):
    """Available polling strategy types."""
    FIXED_INTERVAL = "fixed_interval"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    ADAPTIVE = "adaptive"
    SCHEDULED_WINDOWS = "scheduled_windows"
    BURST_THEN_BACKOFF = "burst_then_backoff"


@dataclass
class PollingContext:
    """Context information provided to polling strategies."""
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_polls: int = 0
    queue_depth: int = 0
    last_poll_duration: float = 0.0
    last_poll_time: Optional[datetime] = None
    average_processing_time: float = 0.0
    system_load: float = 0.0
    error_rate: float = 0.0


@dataclass
class PollingDecision:
    """Decision made by a polling strategy."""
    should_poll: bool
    wait_time_seconds: float
    reason: str
    metadata: Dict[str, Any]


class PollingStrategy(ABC):
    """Abstract base class for polling strategies."""
    
    @abstractmethod
    def get_strategy_type(self) -> PollingStrategyType:
        """Get the strategy type identifier."""
        pass
    
    @abstractmethod
    def decide_next_poll(self, context: PollingContext) -> PollingDecision:
        """
        Decide when the next poll should occur.
        
        Args:
            context: Current polling context with metrics and state
            
        Returns:
            PollingDecision with timing and reasoning
        """
        pass
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure the strategy with parameters.
        
        Args:
            config: Strategy-specific configuration parameters
        """
        pass
    
    @abstractmethod
    def get_configuration(self) -> Dict[str, Any]:
        """Get current strategy configuration."""
        pass
    
    def reset_state(self) -> None:
        """Reset any internal state (optional override)."""
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy-specific metrics (optional override)."""
        return {}


class FixedIntervalStrategy(PollingStrategy):
    """Fixed interval polling strategy - polls at regular intervals."""
    
    def __init__(self, interval_minutes: int = 1):
        self.interval_minutes = max(1, interval_minutes)
        self.interval_seconds = self.interval_minutes * 60
        logger.info(f"🕒 FixedIntervalStrategy initialized with {self.interval_minutes} minute interval")
    
    def get_strategy_type(self) -> PollingStrategyType:
        return PollingStrategyType.FIXED_INTERVAL
    
    def decide_next_poll(self, context: PollingContext) -> PollingDecision:
        return PollingDecision(
            should_poll=True,
            wait_time_seconds=self.interval_seconds,
            reason=f"Fixed interval of {self.interval_minutes} minutes",
            metadata={
                "interval_minutes": self.interval_minutes,
                "interval_seconds": self.interval_seconds
            }
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        if "interval_minutes" in config:
            self.interval_minutes = max(1, int(config["interval_minutes"]))
            self.interval_seconds = self.interval_minutes * 60
            logger.info(f"🔧 FixedIntervalStrategy reconfigured to {self.interval_minutes} minutes")
    
    def get_configuration(self) -> Dict[str, Any]:
        return {
            "interval_minutes": self.interval_minutes,
            "interval_seconds": self.interval_seconds
        }


class ExponentialBackoffStrategy(PollingStrategy):
    """Exponential backoff strategy - increases delay after failures."""
    
    def __init__(self, base_interval_minutes: int = 1, max_interval_minutes: int = 60, 
                 backoff_multiplier: float = 2.0, reset_after_success: bool = True):
        self.base_interval_minutes = max(1, base_interval_minutes)
        self.max_interval_minutes = max(base_interval_minutes, max_interval_minutes)
        self.backoff_multiplier = max(1.1, backoff_multiplier)
        self.reset_after_success = reset_after_success
        self.current_interval_minutes = self.base_interval_minutes
        
        logger.info(f"📈 ExponentialBackoffStrategy initialized: base={self.base_interval_minutes}min, "
                   f"max={self.max_interval_minutes}min, multiplier={self.backoff_multiplier}")
    
    def get_strategy_type(self) -> PollingStrategyType:
        return PollingStrategyType.EXPONENTIAL_BACKOFF
    
    def decide_next_poll(self, context: PollingContext) -> PollingDecision:
        # Adjust interval based on recent failures
        if context.consecutive_failures > 0:
            # Calculate exponential backoff
            self.current_interval_minutes = min(
                self.base_interval_minutes * (self.backoff_multiplier ** context.consecutive_failures),
                self.max_interval_minutes
            )
        elif context.consecutive_successes > 0 and self.reset_after_success:
            # Reset to base interval after success
            self.current_interval_minutes = self.base_interval_minutes
        
        wait_seconds = self.current_interval_minutes * 60
        
        return PollingDecision(
            should_poll=True,
            wait_time_seconds=wait_seconds,
            reason=f"Exponential backoff: {self.current_interval_minutes:.1f} minutes "
                   f"(failures: {context.consecutive_failures})",
            metadata={
                "current_interval_minutes": self.current_interval_minutes,
                "consecutive_failures": context.consecutive_failures,
                "backoff_level": context.consecutive_failures
            }
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        if "base_interval_minutes" in config:
            self.base_interval_minutes = max(1, int(config["base_interval_minutes"]))
        if "max_interval_minutes" in config:
            self.max_interval_minutes = max(self.base_interval_minutes, int(config["max_interval_minutes"]))
        if "backoff_multiplier" in config:
            self.backoff_multiplier = max(1.1, float(config["backoff_multiplier"]))
        if "reset_after_success" in config:
            self.reset_after_success = bool(config["reset_after_success"])
        
        self.current_interval_minutes = self.base_interval_minutes
        logger.info(f"🔧 ExponentialBackoffStrategy reconfigured")
    
    def get_configuration(self) -> Dict[str, Any]:
        return {
            "base_interval_minutes": self.base_interval_minutes,
            "max_interval_minutes": self.max_interval_minutes,
            "backoff_multiplier": self.backoff_multiplier,
            "reset_after_success": self.reset_after_success,
            "current_interval_minutes": self.current_interval_minutes
        }
    
    def reset_state(self) -> None:
        self.current_interval_minutes = self.base_interval_minutes


class AdaptiveStrategy(PollingStrategy):
    """Adaptive strategy - adjusts polling based on queue depth and system load."""
    
    def __init__(self, base_interval_minutes: int = 5, min_interval_minutes: int = 1, 
                 max_interval_minutes: int = 60, queue_threshold: int = 5,
                 load_threshold: float = 0.8):
        self.base_interval_minutes = max(1, base_interval_minutes)
        self.min_interval_minutes = max(1, min_interval_minutes)
        self.max_interval_minutes = max(base_interval_minutes, max_interval_minutes)
        self.queue_threshold = max(1, queue_threshold)
        self.load_threshold = max(0.1, min(1.0, load_threshold))
        
        logger.info(f"🎯 AdaptiveStrategy initialized: base={self.base_interval_minutes}min, "
                   f"range={self.min_interval_minutes}-{self.max_interval_minutes}min")
    
    def get_strategy_type(self) -> PollingStrategyType:
        return PollingStrategyType.ADAPTIVE
    
    def decide_next_poll(self, context: PollingContext) -> PollingDecision:
        # Start with base interval
        interval_minutes = self.base_interval_minutes
        adjustment_reasons = []
        
        # Adjust based on queue depth
        if context.queue_depth > self.queue_threshold:
            # High queue depth - poll more frequently
            queue_factor = min(2.0, context.queue_depth / self.queue_threshold)
            interval_minutes = interval_minutes / queue_factor
            adjustment_reasons.append(f"high queue depth ({context.queue_depth})")
        elif context.queue_depth == 0:
            # Empty queue - poll less frequently
            interval_minutes = interval_minutes * 1.5
            adjustment_reasons.append("empty queue")
        
        # Adjust based on system load
        if context.system_load > self.load_threshold:
            # High system load - poll less frequently
            load_factor = 1.0 + (context.system_load - self.load_threshold)
            interval_minutes = interval_minutes * load_factor
            adjustment_reasons.append(f"high system load ({context.system_load:.2f})")
        
        # Adjust based on error rate
        if context.error_rate > 0.1:  # 10% error rate
            error_factor = 1.0 + context.error_rate
            interval_minutes = interval_minutes * error_factor
            adjustment_reasons.append(f"high error rate ({context.error_rate:.2f})")
        
        # Apply bounds
        interval_minutes = max(self.min_interval_minutes, 
                              min(self.max_interval_minutes, interval_minutes))
        
        wait_seconds = interval_minutes * 60
        reason = f"Adaptive polling: {interval_minutes:.1f} minutes"
        if adjustment_reasons:
            reason += f" (adjusted for: {', '.join(adjustment_reasons)})"
        
        return PollingDecision(
            should_poll=True,
            wait_time_seconds=wait_seconds,
            reason=reason,
            metadata={
                "calculated_interval_minutes": interval_minutes,
                "queue_depth": context.queue_depth,
                "system_load": context.system_load,
                "error_rate": context.error_rate,
                "adjustments": adjustment_reasons
            }
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        if "base_interval_minutes" in config:
            self.base_interval_minutes = max(1, int(config["base_interval_minutes"]))
        if "min_interval_minutes" in config:
            self.min_interval_minutes = max(1, int(config["min_interval_minutes"]))
        if "max_interval_minutes" in config:
            self.max_interval_minutes = max(self.base_interval_minutes, int(config["max_interval_minutes"]))
        if "queue_threshold" in config:
            self.queue_threshold = max(1, int(config["queue_threshold"]))
        if "load_threshold" in config:
            self.load_threshold = max(0.1, min(1.0, float(config["load_threshold"])))
        
        logger.info(f"🔧 AdaptiveStrategy reconfigured")
    
    def get_configuration(self) -> Dict[str, Any]:
        return {
            "base_interval_minutes": self.base_interval_minutes,
            "min_interval_minutes": self.min_interval_minutes,
            "max_interval_minutes": self.max_interval_minutes,
            "queue_threshold": self.queue_threshold,
            "load_threshold": self.load_threshold
        }


class ScheduledWindowsStrategy(PollingStrategy):
    """Scheduled windows strategy - polls only during specified time windows."""
    
    def __init__(self, windows: Optional[List[Dict[str, Any]]] = None, 
                 interval_minutes: int = 5, timezone_offset: int = 0):
        # Default to business hours if no windows specified
        self.windows = windows or [
            {"start_hour": 9, "end_hour": 17, "days": [0, 1, 2, 3, 4]},  # Mon-Fri 9-5
            {"start_hour": 10, "end_hour": 14, "days": [5, 6]}  # Weekend reduced hours
        ]
        self.interval_minutes = max(1, interval_minutes)
        self.timezone_offset = timezone_offset
        
        logger.info(f"🕐 ScheduledWindowsStrategy initialized with {len(self.windows)} windows")
    
    def get_strategy_type(self) -> PollingStrategyType:
        return PollingStrategyType.SCHEDULED_WINDOWS
    
    def decide_next_poll(self, context: PollingContext) -> PollingDecision:
        now = datetime.now()
        current_hour = now.hour
        current_weekday = now.weekday()
        
        # Check if we're in an active window
        in_window = False
        active_window = None
        
        for window in self.windows:
            if (current_weekday in window["days"] and 
                window["start_hour"] <= current_hour < window["end_hour"]):
                in_window = True
                active_window = window
                break
        
        if in_window:
            return PollingDecision(
                should_poll=True,
                wait_time_seconds=self.interval_minutes * 60,
                reason=f"Active window: {active_window['start_hour']:02d}:00-{active_window['end_hour']:02d}:00",
                metadata={
                    "in_window": True,
                    "active_window": active_window,
                    "interval_minutes": self.interval_minutes
                }
            )
        else:
            # Find next available window
            wait_until = self._find_next_window(now)
            wait_seconds = (wait_until - now).total_seconds()
            
            return PollingDecision(
                should_poll=False,
                wait_time_seconds=max(60, wait_seconds),  # At least 1 minute
                reason=f"Outside polling window, next at {wait_until.strftime('%H:%M')}",
                metadata={
                    "in_window": False,
                    "next_window": wait_until.isoformat(),
                    "wait_until": wait_until
                }
            )
    
    def _find_next_window(self, current_time: datetime) -> datetime:
        """Find the next available polling window."""
        # Check today's remaining windows
        current_hour = current_time.hour
        current_weekday = current_time.weekday()
        
        for window in self.windows:
            if (current_weekday in window["days"] and 
                window["start_hour"] > current_hour):
                return current_time.replace(
                    hour=window["start_hour"], 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
        
        # Check next 7 days
        for day_offset in range(1, 8):
            check_date = current_time + timedelta(days=day_offset)
            check_weekday = check_date.weekday()
            
            for window in self.windows:
                if check_weekday in window["days"]:
                    return check_date.replace(
                        hour=window["start_hour"],
                        minute=0,
                        second=0,
                        microsecond=0
                    )
        
        # Fallback: tomorrow at first window
        tomorrow = current_time + timedelta(days=1)
        first_window = min(self.windows, key=lambda w: w["start_hour"])
        return tomorrow.replace(
            hour=first_window["start_hour"],
            minute=0,
            second=0,
            microsecond=0
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        if "windows" in config:
            self.windows = config["windows"]
        if "interval_minutes" in config:
            self.interval_minutes = max(1, int(config["interval_minutes"]))
        if "timezone_offset" in config:
            self.timezone_offset = int(config["timezone_offset"])
        
        logger.info(f"🔧 ScheduledWindowsStrategy reconfigured with {len(self.windows)} windows")
    
    def get_configuration(self) -> Dict[str, Any]:
        return {
            "windows": self.windows,
            "interval_minutes": self.interval_minutes,
            "timezone_offset": self.timezone_offset
        }


class PollingStrategyFactory:
    """Factory for creating polling strategy instances."""
    
    _strategies = {
        PollingStrategyType.FIXED_INTERVAL: FixedIntervalStrategy,
        PollingStrategyType.EXPONENTIAL_BACKOFF: ExponentialBackoffStrategy,
        PollingStrategyType.ADAPTIVE: AdaptiveStrategy,
        PollingStrategyType.SCHEDULED_WINDOWS: ScheduledWindowsStrategy,
    }
    
    @classmethod
    def create_strategy(cls, strategy_type: PollingStrategyType, 
                       config: Optional[Dict[str, Any]] = None) -> PollingStrategy:
        """
        Create a polling strategy instance.
        
        Args:
            strategy_type: Type of strategy to create
            config: Optional configuration for the strategy
            
        Returns:
            Configured polling strategy instance
            
        Raises:
            ValueError: If strategy type is not supported
        """
        if strategy_type not in cls._strategies:
            available = list(cls._strategies.keys())
            raise ValueError(f"Unsupported strategy type: {strategy_type}. Available: {available}")
        
        strategy_class = cls._strategies[strategy_type]
        strategy = strategy_class()
        
        if config:
            strategy.configure(config)
        
        logger.info(f"🏭 Created polling strategy: {strategy_type.value}")
        return strategy
    
    @classmethod
    def get_available_strategies(cls) -> List[PollingStrategyType]:
        """Get list of available strategy types."""
        return list(cls._strategies.keys())
    
    @classmethod
    def register_strategy(cls, strategy_type: PollingStrategyType, 
                         strategy_class: type) -> None:
        """
        Register a new strategy type.
        
        Args:
            strategy_type: Strategy type identifier
            strategy_class: Strategy implementation class
        """
        cls._strategies[strategy_type] = strategy_class
        logger.info(f"📝 Registered new polling strategy: {strategy_type.value}")


# Default strategy configuration
DEFAULT_STRATEGY_CONFIGS = {
    PollingStrategyType.FIXED_INTERVAL: {
        "interval_minutes": 1
    },
    PollingStrategyType.EXPONENTIAL_BACKOFF: {
        "base_interval_minutes": 1,
        "max_interval_minutes": 60,
        "backoff_multiplier": 2.0,
        "reset_after_success": True
    },
    PollingStrategyType.ADAPTIVE: {
        "base_interval_minutes": 5,
        "min_interval_minutes": 1,
        "max_interval_minutes": 60,
        "queue_threshold": 5,
        "load_threshold": 0.8
    },
    PollingStrategyType.SCHEDULED_WINDOWS: {
        "windows": [
            {"start_hour": 9, "end_hour": 17, "days": [0, 1, 2, 3, 4]},
            {"start_hour": 10, "end_hour": 14, "days": [5, 6]}
        ],
        "interval_minutes": 5,
        "timezone_offset": 0
    }
}