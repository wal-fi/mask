"""Independent root QA over public owner ports and deterministic author fakes."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from tests import test_oracle9_w1_port_ownership as t


out = []
with pytest.MonkeyPatch.context() as mp:
    core = t.ht.core.__wrapped__(mp)

    h = t.Harness(core)
    h.pump.gateway_emit_guard = False
    proc, handle = h.spawn_gateway()
    h.pump.gateway_auto_respond = False
    handle.retain_buffer_on_write = True
    handle.defer_write_resume_dt = 1.0 + t.DT
    slot = h.b_ns.OperationSlot("write")
    deadline = h.pump.t + 1.0
    proc.begin_write_into(slot, t.PACKET, deadline)
    h.owner.clock().poll((slot,), deadline + 2 * t.DT)
    rec = h.first_of("WRITE")
    out.append({"case": "late_write_handoff", "deadline": deadline,
                "protocol_at": rec.protocol_at, "protocol": rec.protocol.name,
                "delivery": slot.op.outcome().delivery.name,
                "matches_contract": slot.op.outcome().delivery is h.r_ns.Delivery.UNKNOWN})

    h = t.Harness(core)
    h.pump.gateway_emit_guard = False
    proc, handle = h.spawn_gateway()
    slot = h.b_ns.OperationSlot("read")
    deadline = h.pump.t + 1.0
    proc.begin_read_into(slot, 64, deadline)
    h.pump.schedule_at(deadline + t.DT, lambda: handle.events.data(1, b"late"))
    h.owner.clock().poll((slot,), deadline + 2 * t.DT)
    outcome = slot.op.outcome()
    second = h.b_ns.OperationSlot("read")
    proc.begin_read_into(second, 64, h.pump.t + 1.0)
    retained = second.op.done() and second.op.outcome().data == b"late"
    out.append({"case": "late_read_data", "ok": outcome.ok,
                "data_bytes": len(outcome.data), "late_bytes_retained": retained,
                "old_outcome_identity_preserved": slot.op.outcome() is outcome,
                "matches_contract": outcome.ok is False and retained
                and slot.op.outcome() is outcome})

    h = t.Harness(core)
    h.pump.gateway_emit_guard = False
    proc, handle = h.spawn_gateway()
    slot = h.b_ns.OperationSlot("read")
    deadline = h.pump.t + 1.0
    proc.begin_read_into(slot, 64, deadline)
    h.pump.schedule_at(deadline + t.DT, lambda: handle.events.pipe_lost(1, False))
    h.owner.clock().poll((slot,), deadline + 2 * t.DT)
    outcome = slot.op.outcome()
    out.append({"case": "late_read_eof", "ok": outcome.ok,
                "data_bytes": len(outcome.data), "matches_contract": outcome.ok is False})

    h = t.Harness(core)
    h.pump.gateway_emit_guard = False
    proc, handle = h.spawn_gateway()
    h.pump.gateway_auto_respond = False
    slot = h.b_ns.OperationSlot("write")
    deadline = h.pump.t + 1.0
    h.pump.on_direct_write = lambda pump, _handle, _data: setattr(pump, "t", deadline + t.DT)
    proc.begin_write_into(slot, t.PACKET, deadline)
    rec = h.first_of("WRITE")
    out.append({"case": "synchronous_write_crosses_deadline", "deadline": deadline,
                "protocol_at": rec.protocol_at, "protocol": rec.protocol.name,
                "delivery": slot.op.outcome().delivery.name,
                "matches_contract": slot.op.outcome().delivery is h.r_ns.Delivery.UNKNOWN})

result = {"source_sha256": hashlib.sha256(Path("docs/poc/oracle9_w1_port_ownership.py").read_bytes()).hexdigest(),
          "probes": out, "passed": sum(item["matches_contract"] for item in out),
          "failed": sum(not item["matches_contract"] for item in out)}
Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
