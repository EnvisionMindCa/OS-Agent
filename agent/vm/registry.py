from __future__ import annotations

from threading import Lock
from ..config import Config, DEFAULT_CONFIG
from .linux_vm import LinuxVM
from ..utils.debug import debug_all


class VMRegistry:
    """Manage Linux VM instances on a per-session basis."""

    _vms: dict[tuple[str, str], LinuxVM] = {}
    _counts: dict[tuple[str, str], int] = {}
    _lock = Lock()

    @classmethod
    def acquire(
        cls, username: str, session: str, *, config: Config = DEFAULT_CONFIG
    ) -> LinuxVM:
        """Return a running VM for ``username`` and ``session`` using ``config``."""

        key = (username, session)
        with cls._lock:
            vm = cls._vms.get(key)
            if vm is None:
                vm = LinuxVM(username, config=config)
                cls._vms[key] = vm
                cls._counts[key] = 0
            cls._counts[key] += 1

        vm.start()
        return vm

    @classmethod
    def release(cls, username: str, session: str) -> None:
        """Release one reference to ``username``/``session`` VM and stop if unused."""

        key = (username, session)
        with cls._lock:
            vm = cls._vms.get(key)
            if vm is None:
                return

            cls._counts[key] -= 1
            if cls._counts[key] <= 0:
                cls._counts[key] = 0
                if not vm.config.persist_vms:
                    vm.stop()
                    del cls._vms[key]
                    del cls._counts[key]

    @classmethod
    def shutdown_all(cls) -> None:
        """Stop and remove all managed VMs."""

        with cls._lock:
            for vm in cls._vms.values():
                if not vm.config.persist_vms:
                    vm.stop()
            cls._vms.clear()
            cls._counts.clear()


__all__ = ["VMRegistry"]

debug_all(globals())
