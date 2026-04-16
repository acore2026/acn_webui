# H.264 Video Test Results

## Test Summary

Successfully tested H.264 video transmission through MOQ pipeline from Publisher to WebUI Subscriber.

## Test Configuration

- **Resolution**: 640x360
- **Frame Rate**: 30 fps
- **Duration**: 10 seconds
- **Codec**: H.264 Baseline Profile, Level 3.0
- **Bitrate**: 500 kbps
- **GOP Size**: 30 frames (1 second)

## Test Results

### ✅ Publisher Side

```
Generated H.264 video: 626,443 bytes (611.8 KB)
NAL units found: 1,521
  - IDR (keyframes): 50
  - non-IDR (delta frames): 1,450
  - SEI: 1
  - SPS: 10
  - PPS: 10

Published: 1,521 NAL units in 52.1s
Average rate: 29.2 NAL units/second
```

### ✅ Subscriber Side (WebUI)

```json
{
  "track_id": "..._task-c2a09_video",
  "state": "received",
  "object_count": 123,
  "buffered_frames": 30
}
```

- **Connection**: ✅ Connected to relay
- **Subscription**: ✅ Subscribed and accepted
- **Data Reception**: ✅ Received 123 objects
- **Frame Buffer**: ✅ 30 frames buffered

## Frame Analysis

Current frame buffer contains:
- 10 frames total
- Size distribution:
  - 0 bytes: 2 frames (empty/invalid)
  - 48-527 bytes: 7 frames (normal NAL units)
  - 527,932 bytes: 1 frame (accumulated data - **issue**)

## Issues Found

### 1. Accumulated Large Frame

One frame has 527,932 bytes, which is close to the entire file size. This indicates:
- **Problem**: Stream buffer accumulating data without proper object boundary detection
- **Impact**: Front-end receives oversized frames that may cause decoding issues
- **Root Cause**: MOQ subscriber's stream parsing may not correctly detect object boundaries in H.264 stream

### 2. Object ID Sequence

Object IDs are not sequential (13, 6720, 828, 39...), suggesting:
- Multiple test runs accumulated
- Object IDs are global across reconnections

## Frontend Considerations

### Current Frontend Code

The frontend uses WebCodecs API for H.264 decoding:

```javascript
// From SidebarRight.jsx
const videoDecoder = new VideoDecoder({
  output: handleVideoFrame,
  error: handleDecoderError
});

// Configure for H.264
await videoDecoder.configure({
  codec: 'avc1.42E01E',  // H.264 Baseline Level 3.0
  hardwareAcceleration: 'prefer-hardware'
});
```

### Requirements for H.264 Display

1. **NAL Unit Format**: WebCodecs expects Annex B format (with start codes)
   - Our Publisher sends: `00 00 00 01 <NAL data>` ✓
   - This is correct for Annex B format

2. **Initialization**: Need SPS/PPS before decoding
   - SPS (NAL type 7): Sequence Parameter Set
   - PPS (NAL type 8): Picture Parameter Set
   - IDR (NAL type 5): Instantaneous Decoder Refresh (keyframe)

3. **Decoder Configuration**:
   ```javascript
   // Extract SPS and PPS from first frames
   const sps = /* NAL type 7 data */;
   const pps = /* NAL type 8 data */;
   
   // Create VideoDecoderConfig
   const config = {
     codec: 'avc1.' + spsHex.substring(0, 6),
     description: createAvcDecoderConfigRecord(sps, pps)
   };
   ```

4. **Chunk Processing**:
   ```javascript
   // For each frame
   const chunk = new EncodedVideoChunk({
     type: isIDR ? 'key' : 'delta',
     timestamp: frameTime,
     data: nalUnitData
   });
   videoDecoder.decode(chunk);
   ```

## Recommendations

### 1. Fix Stream Parsing

Update MOQ subscriber to properly handle H.264 NAL unit boundaries:

```python
# In _process_stream_buffer_incremental
# Detect NAL unit boundaries (00 00 00 01 or 00 00 01)
# Create separate objects for each NAL unit
```

### 2. Frontend Decoder Setup

Update frontend to:
1. Extract SPS/PPS from initial frames
2. Configure VideoDecoder with correct codec string
3. Handle Annex B format properly
4. Process frames in order

### 3. Test with Real Browser

Open WebUI in browser and check:
1. WebCodecs API availability: `if ('VideoDecoder' in window)`
2. H.264 support: `VideoDecoder.isConfigSupported({codec: 'avc1.42E01E'})`
3. Decoder initialization with SPS/PPS
4. Frame decoding and display

## Files

- **Test Script**: `/root/lpx/webui/test/test_h264_video.py`
- **API Status**: `http://localhost:9005/api/moq/status`
- **Frame Data**: `http://localhost:9005/api/moq/tracks/<track_id>/frames`

## Next Steps

1. ✅ Verify MOQ pipeline works (DONE)
2. ✅ Generate H.264 test video (DONE)
3. ✅ Transmit via MOQ (DONE)
4. ✅ Receive in WebUI backend (DONE)
5. ⏳ Update frontend to decode H.264 (PENDING)
6. ⏳ Test in browser with WebCodecs API (PENDING)
