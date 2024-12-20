# Copyright 2024 Advanced Micro Devices, Inc.
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import pytest
import sys

import shortfin as sf
import shortfin.array as sfnp


@pytest.fixture
def lsys():
    sc = sf.SystemBuilder()
    lsys = sc.create_system()
    yield lsys
    lsys.shutdown()


@pytest.fixture
def fiber(lsys):
    return lsys.create_fiber()


@pytest.fixture
def device(fiber):
    return fiber.device(0)


def test_allocate_host(device):
    h = sfnp.storage.allocate_host(device, 32)
    assert len(h) == 32


def test_allocate_device(device):
    d = sfnp.storage.allocate_device(device, 64)
    assert len(d) == 64


def test_fill1(lsys, device):
    async def main():
        s = sfnp.storage.allocate_host(device, 8)
        s.fill(b"0")
        await device
        assert bytes(s.map(read=True)) == b"00000000"

    lsys.run(main())


def test_fill2(lsys, device):
    async def main():
        s = sfnp.storage.allocate_host(device, 8)
        s.fill(b"01")
        await device
        assert bytes(s.map(read=True)) == b"01010101"

    lsys.run(main())


def test_fill4(lsys, device):
    async def main():
        s = sfnp.storage.allocate_host(device, 8)
        s.fill(b"0123")
        await device
        assert bytes(s.map(read=True)) == b"01230123"

    lsys.run(main())


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows fatal exception: access violation"
)
def test_fill_error(device):
    s = sfnp.storage.allocate_host(device, 8)
    with pytest.raises(RuntimeError):
        s.fill(b"")
    with pytest.raises(RuntimeError):
        s.fill(b"012")
    with pytest.raises(RuntimeError):
        s.fill(b"01234")
    with pytest.raises(RuntimeError):
        s.fill(b"01234567")


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows fatal exception: access violation"
)
@pytest.mark.parametrize(
    "pattern,size",
    [
        (b"", 8),
        (b"012", 8),
        (b"01234", 8),
        (b"01234567", 8),
    ],
)
def test_fill_error(lsys, device, pattern, size):
    async def main():
        src = sfnp.storage.allocate_host(device, size)
        src.fill(pattern)

    with pytest.raises(
        ValueError, match="fill value length is not one of the supported values"
    ):
        lsys.run(main())


def test_map_read(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        src.fill(b"0123")
        await device
        with src.map(read=True) as m:
            assert m.valid
            assert bytes(m) == b"01230123"

    lsys.run(main())


def test_map_read_not_writable(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        src.fill(b"0123")
        await device
        with src.map(read=True) as m:
            mv = memoryview(m)
            assert mv.readonly
            mv[0] = ord(b"9")

    with pytest.raises(TypeError, match="cannot modify"):
        lsys.run(main())


def test_map_write(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        src.fill(b"0123")
        await device
        with src.map(read=True, write=True) as m:
            mv = memoryview(m)
            assert not mv.readonly
            mv[0] = ord(b"9")
        assert bytes(src.map(read=True)) == b"91230123"

    lsys.run(main())


def test_map_discard(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        src.fill(b"0123")
        await device
        with src.map(write=True, discard=True) as m:
            mv = memoryview(m)
            assert not mv.readonly
            for i in range(8):
                mv[i] = ord(b"9") - i
        assert bytes(src.map(read=True)) == b"98765432"

    lsys.run(main())


@pytest.mark.parametrize(
    "alloc_bytes,fill_value,expected_value",
    [
        (8, b"9", b"99999999"),
        (8, b"98", b"98989898"),
        (8, b"9876", b"98769876"),
        (8, b"98765432", b"98765432"),
        (20, b"9876543210", b"98765432109876543210"),
    ],
)
def test_mapping_fill1(lsys, device, alloc_bytes, fill_value, expected_value):
    async def main():
        src = sfnp.storage.allocate_host(device, alloc_bytes)
        with src.map(discard=True) as m:
            m.fill(fill_value)
        assert bytes(src.map(read=True)) == expected_value

    lsys.run(main())


def test_mapping_explicit_close(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        m = src.map(write=True, discard=True)
        assert m.valid
        m.close()
        assert not m.valid

    lsys.run(main())


def test_mapping_context_manager(lsys, device):
    async def main():
        src = sfnp.storage.allocate_host(device, 8)
        with src.map(write=True, discard=True) as m:
            assert m.valid
        assert not m.valid

    lsys.run(main())
