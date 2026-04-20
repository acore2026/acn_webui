#!/usr/bin/env python3
"""
VideoFrame解析器

用于解析demo_task_initiator_video_production.py发送的结构化视频帧数据
"""

import struct
from dataclasses import dataclass
from typing import Optional


class FrameFlags:
    """帧标志位"""

    KEYFRAME = 0x01
    END_OF_GOP = 0x02
    RECOVERY_POINT = 0x04
    CORRUPTED = 0x08


class FrameType:
    """帧类型"""

    IDR = 0
    P = 1
    B = 2


@dataclass
class VideoFrame:
    """
    结构化视频帧（与acn_sdk中的定义兼容）

    头部格式（52字节）:
    - version (1B): 协议版本
    - flags (1B): 标志位
    - frame_type (1B): 帧类型
    - reserved (1B): 保留
    - timestamp (8B): 发送时间戳
    - pts (8B): 显示时间戳
    - dts (8B): 解码时间戳
    - frame_id (4B): 帧序号
    - gop_id (4B): GOP组号
    - width (4B): 宽度
    - height (4B): 高度
    - fps (4B): 帧率
    - bitrate (4B): 码率
    """

    version: int = 1
    flags: int = 0
    frame_type: int = FrameType.P
    timestamp: int = 0
    pts: int = 0
    dts: int = 0
    frame_id: int = 0
    gop_id: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    bitrate: int = 2000000
    data: bytes = b""

    HEADER_FORMAT = ">BBBBQQQIIIIII"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 52 bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["VideoFrame"]:
        """从二进制解析VideoFrame"""
        if len(data) < cls.HEADER_SIZE:
            return None  # 数据太短，不是VideoFrame格式

        try:
            header = struct.unpack(cls.HEADER_FORMAT, data[: cls.HEADER_SIZE])
            return cls(
                version=header[0],
                flags=header[1],
                frame_type=header[2],
                timestamp=header[4],
                pts=header[5],
                dts=header[6],
                frame_id=header[7],
                gop_id=header[8],
                width=header[9],
                height=header[10],
                fps=header[11],
                bitrate=header[12],
                data=data[cls.HEADER_SIZE :],
            )
        except Exception:
            return None

    def to_bytes(self) -> bytes:
        """序列化为二进制"""
        header = struct.pack(
            self.HEADER_FORMAT,
            self.version,
            self.flags,
            self.frame_type,
            0,  # reserved
            self.timestamp,
            self.pts,
            self.dts,
            self.frame_id,
            self.gop_id,
            self.width,
            self.height,
            self.fps,
            self.bitrate,
        )
        return header + self.data

    def is_keyframe(self) -> bool:
        """判断是否为关键帧"""
        return (
            self.flags & FrameFlags.KEYFRAME
        ) != 0 or self.frame_type == FrameType.IDR

    def get_info(self) -> dict:
        """获取帧信息"""
        return {
            "version": self.version,
            "flags": self.flags,
            "frame_type": self.frame_type,
            "timestamp": self.timestamp,
            "pts": self.pts,
            "dts": self.dts,
            "frame_id": self.frame_id,
            "gop_id": self.gop_id,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "data_size": len(self.data),
            "is_keyframe": self.is_keyframe(),
        }


def try_parse_video_frame(data: bytes) -> Optional[VideoFrame]:
    """
    尝试解析VideoFrame

    Args:
        data: 接收到的payload数据

    Returns:
        如果数据符合VideoFrame格式，返回VideoFrame对象
        如果不符合，返回None
    """
    # 检查数据长度是否足够（至少要有头部）
    if len(data) < VideoFrame.HEADER_SIZE:
        return None

    # 检查头部特征（version应该是1）
    if data[0] != 1:
        return None

    # 尝试解析
    return VideoFrame.from_bytes(data)


def extract_h264_data(data: bytes) -> bytes:
    """
    从payload中提取H264数据

    如果数据是VideoFrame格式，解析并返回纯H264数据
    如果不是VideoFrame格式，直接返回原始数据

    Args:
        data: 接收到的payload数据

    Returns:
        H264视频数据
    """
    video_frame = try_parse_video_frame(data)
    if video_frame:
        return video_frame.data
    return data


# 测试代码
if __name__ == "__main__":
    # 创建一个测试帧
    frame = VideoFrame(
        version=1,
        flags=FrameFlags.KEYFRAME,
        frame_type=FrameType.IDR,
        timestamp=123456789000,
        pts=1000000,
        dts=1000000,
        frame_id=1,
        gop_id=0,
        width=1920,
        height=1080,
        fps=30,
        bitrate=4000000,
        data=b"\x00\x00\x00\x01\x67H264_TEST_DATA",  # 模拟H264数据
    )

    # 序列化
    serialized = frame.to_bytes()
    print(f"序列化后大小: {len(serialized)} 字节")
    print(f"头部大小: {VideoFrame.HEADER_SIZE} 字节")
    print(f"数据大小: {len(frame.data)} 字节")

    # 解析
    parsed = try_parse_video_frame(serialized)
    if parsed:
        print("\n解析成功:")
        print(f"  frame_id: {parsed.frame_id}")
        print(f"  gop_id: {parsed.gop_id}")
        print(f"  width: {parsed.width}")
        print(f"  height: {parsed.height}")
        print(f"  fps: {parsed.fps}")
        print(f"  bitrate: {parsed.bitrate}")
        print(f"  data_len: {len(parsed.data)}")
        print(f"  is_keyframe: {parsed.is_keyframe()}")

        # 提取H264数据
        h264_data = extract_h264_data(serialized)
        print(f"\n提取的H264数据: {h264_data}")
    else:
        print("解析失败")

    # 测试原始H264数据（非VideoFrame格式）
    raw_h264 = b"\x00\x00\x00\x01\x67RAW_H264_DATA"
    extracted = extract_h264_data(raw_h264)
    print(f"\n原始H264数据提取测试:")
    print(f"  输入: {raw_h264}")
    print(f"  输出: {extracted}")
    print(f"  是否相同: {raw_h264 == extracted}")
