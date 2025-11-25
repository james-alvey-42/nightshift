"""
Cloud Execution Module
Adapters for running NightShift tasks on cloud platforms
"""

from .executor_factory import ExecutorFactory, CloudExecutor

__all__ = ['ExecutorFactory', 'CloudExecutor']
