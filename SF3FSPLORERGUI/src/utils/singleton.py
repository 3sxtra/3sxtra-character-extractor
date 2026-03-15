"""Module for Singleton pattern implementation."""

import threading


class Singleton:
    """
    Thread-safe Singleton base class/mixin.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """__new__ implementation for instantiation-based access"""
        _ = args
        _ = kwargs
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        """Get singleton instance (compatibility for factory usage)"""
        # Note: If cls() calls __new__ (pure python), it returns _instance.
        # If cls() calls QObject.__new__, it returns new instance.
        # So we must maintain manual caching here for QObject compatibility.
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
