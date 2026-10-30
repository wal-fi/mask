"""Pure public volume decisions; no Docker, process, filesystem mutations or DB."""

import dataclasses
import runpy
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def module() -> Any:
    return runpy.run_path(str(REPO / "docs/poc/pg16_public_volumes.py"))


@pytest.mark.parametrize("raw", [b"", b"before\n", b"before\r\nother.volume\r\n"])
def test_inventory_is_bounded_immutable_and_exact(module, raw):
    values = module["inventory"](raw)
    assert type(values) is frozenset
    assert values == frozenset(raw.decode().splitlines())


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "before\n",
        b"\xff\n",
        b"before",
        b"before\n\n",
        b"same\nsame\n",
        b"a/b\n",
        b" leading\n",
        b"line\rbreak\n",
        b"x" * 256 + b"\n",
        b"x" * 65537,
        b"".join((str(i) + "\n").encode() for i in range(257)),
    ],
    ids=[
        "none",
        "text",
        "non-ascii",
        "no-lf",
        "empty-line",
        "duplicate",
        "slash",
        "space",
        "cr",
        "long-name",
        "too-many-bytes",
        "too-many-names",
    ],
)
def test_ambiguous_unknown_or_excessive_inventory_is_closed(module, raw):
    with pytest.raises(module["VolumeFault"], match=r"^VOLUME_INVENTORY$"):
        module["inventory"](raw)


def test_new_anonymous_volume_is_recorded_for_own_cid_cleanup_without_start_authority(module):
    name = "a" * 64
    result = module["removal"](frozenset({"existing"}), [{"Type": "volume", "Name": name}])
    assert result.mode is module["Mode"].WITH_V
    assert result.names == (name,) and result.preexisting == ()
    assert not hasattr(result, "start_allowed") and not hasattr(result, "released")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.mode = module["Mode"].PRESERVE_UNCERTAIN


@pytest.mark.parametrize("preexisting", ["named-existing", "a" * 64])
def test_preexisting_named_and_anonymous_volumes_both_prohibit_v(module, preexisting):
    names = [preexisting, "new-anonymous"]
    result = module["removal"](
        frozenset({preexisting}), [{"Type": "volume", "Name": name} for name in names]
    )
    assert result.mode is module["Mode"].PRESERVE_EXISTING
    assert result.preexisting == (preexisting,)
    assert result.names == tuple(sorted(names))


@pytest.mark.parametrize(
    "mounts",
    [
        None,
        {},
        [None],
        [{}],
        [{"Type": "other"}],
        [{"Type": "volume"}],
        [{"Type": "volume", "Name": "bad/private"}],
        [{"Type": "tmpfs"}] * 33,
    ],
)
def test_unknown_inspect_mounts_never_select_v(module, mounts):
    result = module["removal"](frozenset(), mounts)
    assert result.mode is module["Mode"].PRESERVE_UNCERTAIN
    assert result.names == result.preexisting == ()


def test_non_volume_mounts_do_not_invent_volume_ownership_or_profile_acceptance(module):
    result = module["removal"](frozenset(), [{"Type": "tmpfs"}, {"Type": "bind"}])
    assert result.names == ()
    assert not hasattr(result, "profile_accepted")


def test_named_volume_surviving_v_and_unrelated_inventory_change_remain_explicit(module):
    before = frozenset({"existing"})
    unchanged = module["difference"](before, before)
    assert unchanged.added == unchanged.missing == ()
    leftovers = module["difference"](before, frozenset({"new-named"}))
    assert leftovers.added == ("new-named",) and leftovers.missing == ("existing",)
    # These are facts only; even equality does not attest rm success, CID absence or freshness.
    assert not hasattr(unchanged, "released")


@pytest.mark.parametrize("bad", [set(), (), None, frozenset({False}), frozenset({"bad/name"})])
def test_inventory_collections_are_closed_types_and_names(module, bad):
    with pytest.raises(module["VolumeFault"]):
        module["difference"](frozenset(), bad)
    with pytest.raises(module["VolumeFault"]):
        module["removal"](bad, [])
