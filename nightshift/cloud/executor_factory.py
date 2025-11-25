"""
Cloud Executor Factory
Creates appropriate cloud executor based on configuration
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class CloudProvider(Enum):
    """Supported cloud providers"""
    LOCAL = "local"
    GCP = "gcp"
    AWS = "aws"
    AZURE = "azure"


@dataclass
class ExecutionResult:
    """Result of cloud task execution"""
    success: bool
    task_id: str
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    token_usage: Optional[int] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class CloudExecutor(ABC):
    """
    Abstract base class for cloud executors

    Each cloud provider implementation should:
    - Provision execution environment
    - Execute NightShift task
    - Store results in cloud storage
    - Update task status
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cloud executor

        Args:
            config: Cloud provider-specific configuration
        """
        self.config = config

    @abstractmethod
    def execute_task(
        self,
        task_id: str,
        description: str,
        allowed_tools: list,
        system_prompt: str
    ) -> ExecutionResult:
        """
        Execute task in cloud environment

        Args:
            task_id: Task identifier
            description: Task description/prompt
            allowed_tools: List of allowed MCP tools
            system_prompt: System prompt for executor

        Returns:
            ExecutionResult with success status and metadata
        """
        pass

    @abstractmethod
    def get_execution_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a running/completed task

        Args:
            task_id: Task identifier

        Returns:
            Status dictionary with state and metadata
        """
        pass

    @abstractmethod
    def cancel_execution(self, task_id: str) -> bool:
        """
        Cancel a running task

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled successfully
        """
        pass


class ExecutorFactory:
    """
    Factory for creating cloud executors
    """

    @staticmethod
    def create_executor(
        provider: CloudProvider,
        config: Dict[str, Any]
    ) -> CloudExecutor:
        """
        Create appropriate cloud executor

        Args:
            provider: Cloud provider type
            config: Provider-specific configuration

        Returns:
            CloudExecutor instance

        Raises:
            ValueError: If provider is not supported
        """
        if provider == CloudProvider.LOCAL:
            from ..core.agent_manager import AgentManager
            # Return local executor (wrapper around AgentManager)
            # This maintains backward compatibility
            raise NotImplementedError("Local executor should use AgentManager directly")

        elif provider == CloudProvider.GCP:
            from .gcp.cloud_run import CloudRunExecutor
            return CloudRunExecutor(config)

        elif provider == CloudProvider.AWS:
            from .aws.lambda_executor import LambdaExecutor
            return LambdaExecutor(config)

        elif provider == CloudProvider.AZURE:
            from .azure.functions import AzureFunctionsExecutor
            return AzureFunctionsExecutor(config)

        else:
            raise ValueError(f"Unsupported cloud provider: {provider}")
