#!/usr/bin/env python3
"""
Test Stream Parsing Logic
"""

import sys
import os

WEBUI_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WEBUI_ROOT)

from moq.encoding import VarInt
from moq.messages import StreamType, SubgroupHeader, SubgroupObject

# Sample data from actual logs (first few bytes of a stream)
# This is what the publisher sends: stream_type + subgroup_header + objects
sample_data = bytes.fromhex(
    "01"  # StreamType.SUBGROUP_HEADER = 0x01
    "00"  # track_alias = 0
    "00"  # group_id = 0
    "00"  # subgroup_id = 0
    "80"  # publisher_priority = 128
)


def test_parse_stream_type():
    """Test parsing stream type"""
    print("Testing stream type parsing...")

    # Test with VarInt 0x01
    data = bytes([0x01])
    stream_type, consumed = VarInt.decode(data, 0)
    print(f"  Stream type: {stream_type} (consumed: {consumed})")
    print(f"  Expected: {StreamType.SUBGROUP_HEADER}")
    print(f"  Match: {stream_type == StreamType.SUBGROUP_HEADER}")


def test_parse_subgroup_header():
    """Test parsing subgroup header"""
    print("\nTesting subgroup header parsing...")

    # Create sample header data
    # Format: track_alias (varint) + group_id (varint) + subgroup_id (varint) + publisher_priority (1 byte)
    header_data = (
        VarInt.encode(0)  # track_alias
        + VarInt.encode(0)  # group_id
        + VarInt.encode(0)  # subgroup_id
        + bytes([128])  # publisher_priority
    )

    print(f"  Header data hex: {header_data.hex()}")
    print(f"  Header data length: {len(header_data)}")

    try:
        header, consumed = SubgroupHeader.decode(header_data, 0)
        print(
            f"  Parsed header: track_alias={header.track_alias}, group_id={header.group_id}"
        )
        print(f"  Consumed: {consumed}")
    except Exception as e:
        print(f"  Error: {e}")


def test_parse_subgroup_object():
    """Test parsing subgroup object"""
    print("\nTesting subgroup object parsing...")

    # Create sample object data
    # Format: object_id (varint) + payload_len (varint) + payload
    payload = b"Hello, World!" * 100  # 1300 bytes
    obj_data = (
        VarInt.encode(0)  # object_id
        + VarInt.encode(len(payload))  # payload_len
        + payload
    )

    print(f"  Object data length: {len(obj_data)}")
    print(f"  Expected payload length: {len(payload)}")

    try:
        obj, consumed = SubgroupObject.decode(obj_data, 0)
        print(
            f"  Parsed object: object_id={obj.object_id}, payload_len={len(obj.payload)}"
        )
        print(f"  Consumed: {consumed}")
    except Exception as e:
        print(f"  Error: {e}")


def test_full_stream():
    """Test parsing a complete stream"""
    print("\nTesting full stream parsing...")

    # Create a complete stream
    stream_data = bytes([StreamType.SUBGROUP_HEADER])  # Stream type

    # Add subgroup header
    header_data = (
        VarInt.encode(0)  # track_alias
        + VarInt.encode(100)  # group_id
        + VarInt.encode(0)  # subgroup_id
        + bytes([128])  # publisher_priority
    )
    stream_data += header_data

    # Add some objects
    for i in range(5):
        payload = b"X" * (100 + i * 50)  # Different sizes
        obj_data = (
            VarInt.encode(i)  # object_id
            + VarInt.encode(len(payload))  # payload_len
            + payload
        )
        stream_data += obj_data

    print(f"  Total stream length: {len(stream_data)}")

    # Parse the stream
    offset = 0

    # Parse stream type
    stream_type, consumed = VarInt.decode(stream_data, offset)
    offset += consumed
    print(f"  Stream type: {stream_type}")

    # Parse header
    header, consumed = SubgroupHeader.decode(stream_data, offset)
    offset += consumed
    print(f"  Header: track_alias={header.track_alias}, group_id={header.group_id}")

    # Parse objects
    obj_count = 0
    while offset < len(stream_data):
        try:
            obj, consumed = SubgroupObject.decode(stream_data, offset)
            offset += consumed
            obj_count += 1
            print(
                f"  Object {obj_count}: id={obj.object_id}, payload={len(obj.payload)} bytes"
            )
        except Exception as e:
            print(f"  Error parsing object at offset {offset}: {e}")
            break

    print(f"  Total objects parsed: {obj_count}")


if __name__ == "__main__":
    test_parse_stream_type()
    test_parse_subgroup_header()
    test_parse_subgroup_object()
    test_full_stream()
