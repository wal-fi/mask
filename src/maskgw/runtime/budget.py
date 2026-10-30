"""B2-B1: isolated logical credits, NOT an allocator or OS containment.

No operational caller imports this module. All costs and cleanup facts come
from a trusted caller; they are not measurements or IPC claims. The caller
must serialize EVERY access with one external coordinator lock. This core
has no lock, callback, I/O, process, registry or connection.

Mutations prepare a bounded immutable image and publish it once. Failed
publication restores the old image; failed restoration quarantines all
remaining credits permanently. Fault tests cover those modeled boundaries,
not arbitrary interpreter failure or real OOM recovery.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import wraps
from typing import Final, NoReturn, ParamSpec, TypeVar

_MAX_NUMBER: Final = (1 << 63) - 1
# Construction bounds for this isolated model, not operational settings/defaults.
_MAX_SLOTS: Final = 4096
_MAX_DATASOURCES: Final = 1024
_P = ParamSpec("_P")
_T = TypeVar("_T")


class BudgetFailure(StrEnum):
    INVALID = "INVALID"
    CAPACITY = "CAPACITY"
    STATE = "STATE"
    CLOSED = "CLOSED"
    FAULT = "FAULT"


class BudgetError(ValueError):
    """Fixed category/message, no internal input value or exception chain.

    Python may attach a caller's already-active exception as suppressed context.
    """

    def __init__(self, category: BudgetFailure) -> None:
        super().__init__("reserva logica recusada")
        self.category = category


def _refuse(category: BudgetFailure) -> NoReturn:
    raise BudgetError(category) from None


def _guard(method: Callable[_P, _T]) -> Callable[_P, _T]:
    @wraps(method)
    def guarded(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        try:
            return method(*args, **kwargs)
        except BudgetError:
            raise
        except Exception:
            failure = BudgetFailure.FAULT
        # Outside the except: never keep an original exception as __context__.
        _refuse(failure)

    return guarded


def _number(value: object, *, minimum: int = 1, maximum: int = _MAX_NUMBER) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        _refuse(BudgetFailure.INVALID)


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    total_bytes: int
    base_bytes: int
    headroom_bytes: int
    entries: int
    sessions: int
    workers: int
    candidates: int
    generations: int
    auxiliaries: int

    def __post_init__(self) -> None:
        for value in (self.total_bytes, self.base_bytes, self.headroom_bytes):
            _number(value)
        for value in (
            self.entries,
            self.sessions,
            self.workers,
            self.candidates,
            self.generations,
            self.auxiliaries,
        ):
            _number(value, maximum=_MAX_SLOTS)
        if self.base_bytes + self.headroom_bytes > self.total_bytes or any(
            value > self.entries
            for value in (
                self.sessions,
                self.workers,
                self.candidates,
                self.generations,
                self.auxiliaries,
            )
        ):
            _refuse(BudgetFailure.INVALID)


@dataclass(frozen=True, slots=True)
class DatasourceCapacity:
    sessions: int
    candidates: int

    def __post_init__(self) -> None:
        _number(self.sessions, maximum=_MAX_SLOTS)
        _number(self.candidates, maximum=_MAX_SLOTS)


@dataclass(frozen=True, slots=True)
class CleanupConfirmation:
    """Trusted MODEL facts only; never an assertion accepted from a worker."""

    processes: bool
    threads: bool
    pipes: bool
    handles: bool
    output: bool

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.processes,
                self.threads,
                self.pipes,
                self.handles,
                self.output,
            )
        ):
            _refuse(BudgetFailure.INVALID)

    @property
    def complete(self) -> bool:
        return all((self.processes, self.threads, self.pipes, self.handles, self.output))


class ReservationKind(StrEnum):
    SESSION = "SESSION"
    CANDIDATE = "CANDIDATE"
    GENERATION = "GENERATION"
    AUXILIARY = "AUXILIARY"


class ReservationState(StrEnum):
    RESERVED = "RESERVED"
    LIVE = "LIVE"
    DRAINING = "DRAINING"
    HELD = "HELD"


class ReleaseOutcome(StrEnum):
    RELEASED = "RELEASED"
    HELD = "HELD"
    ALREADY_RELEASED = "ALREADY_RELEASED"

    def __bool__(self) -> NoReturn:
        raise TypeError("compare o estado de liberacao explicitamente")


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class BudgetToken:
    """Internal instance/slot/epoch identity, not an authentication boundary."""

    _owner: object
    _slot: int
    _epoch: int

    def __repr__(self) -> str:
        return "BudgetToken(<private>)"


class OutputReleaseOutcome(StrEnum):
    CLEARED = "CLEARED"
    HELD = "HELD"
    ALREADY_CLEARED = "ALREADY_CLEARED"

    def __bool__(self) -> NoReturn:
        raise TypeError("compare o estado do pin explicitamente")


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class BudgetOutputToken:
    """Internal pin identity, not a session token or authentication boundary."""

    _session: BudgetToken
    _epoch: int
    frame_bytes: int
    overhead_bytes: int

    def __repr__(self) -> str:
        return "BudgetOutputToken(<private>)"


@dataclass(frozen=True, slots=True)
class ReservationView:
    kind: ReservationKind
    state: ReservationState
    datasource: int | None
    generation_slot: int | None = None
    generation_epoch: int = 0
    worker_bytes: int = 0
    parent_bytes: int = 0
    shared_bytes: int = 0
    output_epoch: int = 0
    output_pinned: bool = False
    output_frame_bytes: int = 0
    output_overhead_bytes: int = 0


@dataclass(frozen=True, slots=True)
class _Slot:
    epoch: int = 0
    entry: ReservationView | None = None


@dataclass(frozen=True, slots=True)
class _Image:
    slots: tuple[_Slot, ...]
    closing: bool = False
    closed: bool = False


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    """Bounded numeric/enum metadata, never policy, alias or secret."""

    base_bytes: int
    headroom_bytes: int
    worker_bytes: int
    parent_bytes: int
    quarantined_bytes: int
    reserved_bytes: int
    available_bytes: int
    sessions: int
    candidates: int
    generations: int
    auxiliaries: int
    closing: bool
    closed: bool
    failed: bool
    epochs: tuple[int, ...]
    entries: tuple[ReservationView | None, ...]
    quarantined_entries: tuple[tuple[ReservationView | None, ...], ...]


class BudgetLedger:
    """Pure bounded state machine; all access requires caller serialization.

    Datasources are fixed internal ordinals, not client-controlled strings.
    Empty slots retain only their last epoch, never tokens or event history.
    Credits are logical: releasing them does NOT prove OS commit was returned.
    """

    __slots__ = ("_datasources", "_failure", "_image", "_limits", "_owner")

    @_guard
    def __init__(
        self,
        limits: BudgetLimits,
        datasources: tuple[DatasourceCapacity, ...],
    ) -> None:
        if type(limits) is not BudgetLimits or type(datasources) is not tuple:
            _refuse(BudgetFailure.INVALID)
        if not 1 <= len(datasources) <= _MAX_DATASOURCES or any(
            type(item) is not DatasourceCapacity for item in datasources
        ):
            _refuse(BudgetFailure.INVALID)
        self._limits = limits
        self._datasources = datasources
        self._owner = object()
        # One publication records terminal failure AND both possible owners.
        self._failure: tuple[_Image, _Image] | None = None
        self._image = _Image(tuple(_Slot() for _ in range(limits.entries)))

    def __repr__(self) -> str:
        return "BudgetLedger(<logical-only>)"

    def _usable(self, *, admission: bool = False) -> None:
        if self._failure is not None:
            _refuse(BudgetFailure.FAULT)
        if self._image.closed or (admission and self._image.closing):
            _refuse(BudgetFailure.CLOSED)

    def _datasource(self, datasource: int) -> None:
        _number(datasource, minimum=0, maximum=len(self._datasources) - 1)

    def _locate(self, token: BudgetToken, *, empty: bool = False) -> _Slot:
        if type(token) is not BudgetToken or token._owner is not self._owner:
            _refuse(BudgetFailure.INVALID)
        _number(token._slot, minimum=0, maximum=len(self._image.slots) - 1)
        _number(token._epoch)
        slot = self._image.slots[token._slot]
        if token._epoch != slot.epoch or (slot.entry is None and not empty):
            _refuse(BudgetFailure.STATE)
        return slot

    def _entry(self, token: BudgetToken) -> ReservationView:
        slot = self._locate(token)
        assert slot.entry is not None  # noqa: S101 - established by _locate
        return slot.entry

    @staticmethod
    def _validate_output(row: ReservationView) -> None:
        _number(row.output_epoch, minimum=0)
        _number(row.output_frame_bytes, minimum=0)
        _number(row.output_overhead_bytes, minimum=0)
        if type(row.output_pinned) is not bool:
            _refuse(BudgetFailure.INVALID)
        if row.kind is not ReservationKind.SESSION and (
            row.output_epoch
            or row.output_pinned
            or row.output_frame_bytes
            or row.output_overhead_bytes
        ):
            _refuse(BudgetFailure.STATE)
        if row.output_pinned:
            _number(row.output_frame_bytes)
            _number(row.output_overhead_bytes)
            if row.output_epoch == 0:
                _refuse(BudgetFailure.STATE)
            if 2 * row.output_frame_bytes + row.output_overhead_bytes > row.parent_bytes:
                _refuse(BudgetFailure.CAPACITY)
        elif row.output_frame_bytes or row.output_overhead_bytes:
            _refuse(BudgetFailure.STATE)

    def _validate(self, image: _Image) -> None:
        counts = dict.fromkeys(ReservationKind, 0)
        sessions_by_ds = [0] * len(self._datasources)
        candidates_by_ds = [0] * len(self._datasources)
        used = self._limits.base_bytes + self._limits.headroom_bytes
        for slot in image.slots:
            row = slot.entry
            if row is None:
                continue
            self._validate_output(row)
            used += row.worker_bytes + row.parent_bytes + row.shared_bytes
            counts[row.kind] += 1
            if row.kind is ReservationKind.SESSION:
                assert row.datasource is not None  # noqa: S101 - internal minted entry
                sessions_by_ds[row.datasource] += 1
            elif row.kind is ReservationKind.CANDIDATE:
                assert row.datasource is not None  # noqa: S101 - internal minted entry
                candidates_by_ds[row.datasource] += 1
        if (
            used > self._limits.total_bytes
            or counts[ReservationKind.SESSION] > min(self._limits.sessions, self._limits.workers)
            or counts[ReservationKind.CANDIDATE] > self._limits.candidates
            or counts[ReservationKind.GENERATION] > self._limits.generations
            or counts[ReservationKind.AUXILIARY] > self._limits.auxiliaries
        ):
            _refuse(BudgetFailure.CAPACITY)
        for index, capacity in enumerate(self._datasources):
            if (
                sessions_by_ds[index] > capacity.sessions
                or candidates_by_ds[index] > capacity.candidates
            ):
                _refuse(BudgetFailure.CAPACITY)

    def _write_image(self, image: _Image) -> None:
        self._image = image

    def _restore_image(self, image: _Image) -> None:
        self._image = image

    def _commit(self, image: _Image) -> None:
        self._validate(image)
        old = self._image
        fallback = (old, image)  # Prepare BEFORE publication, not under a failed rollback.
        failed = False
        try:
            self._write_image(image)
        except Exception:
            failed = True
            try:
                self._restore_image(old)
            except Exception:
                # No capacity can be returned or admitted after uncertain rollback.
                self._failure = fallback  # Atomic fail-closed marker AND both possible owners.
        if failed:
            _refuse(BudgetFailure.FAULT)

    def _replace(self, token: BudgetToken, entry: ReservationView | None) -> None:
        self._locate(token)
        slots = list(self._image.slots)
        slots[token._slot] = _Slot(token._epoch, entry)
        self._commit(replace(self._image, slots=tuple(slots)))

    def _reserve(self, entry: ReservationView) -> BudgetToken:
        for index, slot in enumerate(self._image.slots):
            if slot.entry is None and slot.epoch < _MAX_NUMBER:
                token = BudgetToken(self._owner, index, slot.epoch + 1)
                slots = list(self._image.slots)
                slots[index] = _Slot(token._epoch, entry)
                self._commit(replace(self._image, slots=tuple(slots)))
                return token
        _refuse(BudgetFailure.CAPACITY)

    @_guard
    def reserve_candidate(self, datasource: int, *, shared_bytes: int) -> BudgetToken:
        self._usable(admission=True)
        self._datasource(datasource)
        _number(shared_bytes)
        return self._reserve(
            ReservationView(
                ReservationKind.CANDIDATE,
                ReservationState.RESERVED,
                datasource,
                shared_bytes=shared_bytes,
            )
        )

    @_guard
    def reserve_auxiliary(self, *, shared_bytes: int) -> BudgetToken:
        self._usable(admission=True)
        _number(shared_bytes)
        return self._reserve(
            ReservationView(
                ReservationKind.AUXILIARY,
                ReservationState.RESERVED,
                None,
                shared_bytes=shared_bytes,
            )
        )

    @_guard
    def publish(self, candidate: BudgetToken, *, replacing: BudgetToken | None = None) -> None:
        """Transfer existing credits; prior reservation may publish while closing."""
        self._usable()
        row = self._entry(candidate)
        if row.kind is not ReservationKind.CANDIDATE or row.state not in (
            ReservationState.RESERVED,
            ReservationState.LIVE,
        ):
            _refuse(BudgetFailure.STATE)
        slots = list(self._image.slots)
        if replacing is not None:
            old = self._entry(replacing)
            if (
                old.kind is not ReservationKind.GENERATION
                or old.datasource != row.datasource
                or old.state is not ReservationState.LIVE
            ):
                _refuse(BudgetFailure.STATE)
            slots[replacing._slot] = _Slot(
                replacing._epoch,
                replace(old, state=ReservationState.DRAINING),
            )
        if any(
            slot.entry is not None
            and slot.entry.kind is ReservationKind.GENERATION
            and slot.entry.datasource == row.datasource
            and slot.entry.state is ReservationState.LIVE
            for slot in slots
        ):
            _refuse(BudgetFailure.STATE)
        slots[candidate._slot] = _Slot(
            candidate._epoch,
            replace(
                row,
                kind=ReservationKind.GENERATION,
                state=ReservationState.LIVE,
            ),
        )
        self._commit(replace(self._image, slots=tuple(slots)))

    @_guard
    def reserve_session(
        self,
        generation: BudgetToken,
        *,
        worker_bytes: int,
        parent_bytes: int,
    ) -> BudgetToken:
        self._usable(admission=True)
        row = self._entry(generation)
        if row.kind is not ReservationKind.GENERATION or row.state is not ReservationState.LIVE:
            _refuse(BudgetFailure.STATE)
        _number(worker_bytes)
        _number(parent_bytes)
        return self._reserve(
            ReservationView(
                ReservationKind.SESSION,
                ReservationState.RESERVED,
                row.datasource,
                generation._slot,
                generation._epoch,
                worker_bytes,
                parent_bytes,
            )
        )

    @_guard
    def mark_live(self, token: BudgetToken) -> None:
        """Recheck shutdown before modeled work; not an actual ResumeThread."""
        self._usable(admission=True)
        row = self._entry(token)
        if row.state is not ReservationState.RESERVED:
            _refuse(BudgetFailure.STATE)
        self._replace(token, replace(row, state=ReservationState.LIVE))

    @_guard
    def adopt_session(self, token: BudgetToken) -> None:
        """Private owner claims ONLY a reserved session, once, before OS spawn.

        Same caller lock as all ledger access; not an OS quota/resume proof.
        The trusted admitting caller binds this token to its runtime generation.
        """
        self._usable(admission=True)
        row = self._entry(token)
        if row.kind is not ReservationKind.SESSION or row.state is not ReservationState.RESERVED:
            _refuse(BudgetFailure.STATE)
        self._replace(token, replace(row, state=ReservationState.LIVE))

    @_guard
    def begin_drain(self, token: BudgetToken) -> None:
        """Retiring a generation never changes its admitted sessions."""
        self._usable()
        row = self._entry(token)
        if row.state not in (ReservationState.DRAINING, ReservationState.HELD):
            self._replace(token, replace(row, state=ReservationState.DRAINING))

    @_guard
    def begin_output(
        self,
        session: BudgetToken,
        *,
        frame_bytes: int,
        overhead_bytes: int,
    ) -> BudgetOutputToken:
        """Pin existing P credits before any result allocation; does not add capacity."""
        self._usable(admission=True)
        _number(frame_bytes)
        _number(overhead_bytes)
        _number(2 * frame_bytes + overhead_bytes)
        row = self._entry(session)
        if (
            row.kind is not ReservationKind.SESSION
            or row.state is not ReservationState.LIVE
            or row.output_pinned
        ):
            _refuse(BudgetFailure.STATE)
        if 2 * frame_bytes + overhead_bytes > row.parent_bytes or row.output_epoch == _MAX_NUMBER:
            _refuse(BudgetFailure.CAPACITY)
        pin = BudgetOutputToken(session, row.output_epoch + 1, frame_bytes, overhead_bytes)
        self._replace(
            session,
            replace(
                row,
                output_epoch=pin._epoch,
                output_pinned=True,
                output_frame_bytes=frame_bytes,
                output_overhead_bytes=overhead_bytes,
            ),
        )
        return pin

    @_guard
    def end_output(
        self,
        pin: BudgetOutputToken,
        *,
        discarded: bool,
        drain: bool = False,
    ) -> OutputReleaseOutcome:
        """Clear only this pin, atomically with optional drain; never free session credits."""
        self._usable()
        if (
            type(pin) is not BudgetOutputToken
            or type(discarded) is not bool
            or type(drain) is not bool
        ):
            _refuse(BudgetFailure.INVALID)
        _number(pin._epoch)
        _number(pin.frame_bytes)
        _number(pin.overhead_bytes)
        row = self._entry(pin._session)
        if row.kind is not ReservationKind.SESSION or row.output_epoch != pin._epoch:
            _refuse(BudgetFailure.STATE)
        if not row.output_pinned:
            return OutputReleaseOutcome.ALREADY_CLEARED
        if (row.output_frame_bytes, row.output_overhead_bytes) != (
            pin.frame_bytes,
            pin.overhead_bytes,
        ):
            _refuse(BudgetFailure.STATE)
        state = row.state
        if drain and state is not ReservationState.HELD:
            state = ReservationState.DRAINING
        if not discarded:
            if state is not row.state:
                self._replace(pin._session, replace(row, state=state))
            return OutputReleaseOutcome.HELD
        self._replace(
            pin._session,
            replace(
                row,
                state=state,
                output_pinned=False,
                output_frame_bytes=0,
                output_overhead_bytes=0,
            ),
        )
        return OutputReleaseOutcome.CLEARED

    @_guard
    def retain(self, token: BudgetToken) -> None:
        self._usable()
        row = self._entry(token)
        if row.state is not ReservationState.HELD:
            self._replace(token, replace(row, state=ReservationState.HELD))

    @_guard
    def release(self, token: BudgetToken, confirmation: CleanupConfirmation) -> ReleaseOutcome:
        """Explicitly distinguish retained credits, new release and idempotent release."""
        if self._failure is not None:
            _refuse(BudgetFailure.FAULT)
        if type(confirmation) is not CleanupConfirmation:
            _refuse(BudgetFailure.INVALID)
        slot = self._locate(token, empty=True)
        if slot.entry is None:
            return ReleaseOutcome.ALREADY_RELEASED
        row = slot.entry
        if row.state not in (ReservationState.DRAINING, ReservationState.HELD):
            _refuse(BudgetFailure.STATE)
        referenced = row.kind is ReservationKind.GENERATION and any(
            item.entry is not None
            and item.entry.kind is ReservationKind.SESSION
            and item.entry.generation_slot == token._slot
            and item.entry.generation_epoch == token._epoch
            for item in self._image.slots
        )
        if not confirmation.complete or referenced or row.output_pinned:
            if row.state is not ReservationState.HELD:
                self._replace(token, replace(row, state=ReservationState.HELD))
            return ReleaseOutcome.HELD
        self._replace(token, None)
        return ReleaseOutcome.RELEASED

    @_guard
    def begin_shutdown(self) -> None:
        if self._failure is not None:
            _refuse(BudgetFailure.FAULT)
        if not self._image.closing:
            self._commit(replace(self._image, closing=True))

    @_guard
    def finish_shutdown(self) -> None:
        if self._failure is not None:
            _refuse(BudgetFailure.FAULT)
        if not self._image.closing:
            _refuse(BudgetFailure.STATE)
        if any(slot.entry is not None for slot in self._image.slots):
            _refuse(BudgetFailure.CAPACITY)
        if not self._image.closed:
            self._commit(replace(self._image, closed=True))

    @property
    @_guard
    def status(self) -> BudgetStatus:
        rows = tuple(slot.entry for slot in self._image.slots)
        entries = tuple(row for row in rows if row is not None)
        base = self._limits.base_bytes + sum(row.shared_bytes for row in entries)
        worker = sum(row.worker_bytes for row in entries)
        parent = sum(row.parent_bytes for row in entries)
        reserved = base + self._limits.headroom_bytes + worker + parent
        failed = self._failure is not None
        quarantine = self._limits.total_bytes - reserved if failed else 0
        return BudgetStatus(
            base,
            self._limits.headroom_bytes,
            worker,
            parent,
            quarantine,
            reserved + quarantine,
            self._limits.total_bytes - reserved - quarantine,
            sum(row.kind is ReservationKind.SESSION for row in entries),
            sum(row.kind is ReservationKind.CANDIDATE for row in entries),
            sum(row.kind is ReservationKind.GENERATION for row in entries),
            sum(row.kind is ReservationKind.AUXILIARY for row in entries),
            self._image.closing,
            self._image.closed,
            failed,
            tuple(slot.epoch for slot in self._image.slots),
            rows,
            tuple(
                tuple(slot.entry for slot in image.slots)
                for image in (() if self._failure is None else self._failure)
            ),
        )
