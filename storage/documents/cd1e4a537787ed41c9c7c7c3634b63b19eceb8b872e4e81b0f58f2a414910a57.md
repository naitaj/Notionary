# DOC-05: LeafGuard Server Architecture & Edge Inference Pipeline

**Document Code:** DOC-05  
**Version:** 1.2  
**Date:** 2026-02-20  
**Author:** Karan Mehta, Vikram  

## 1. Overview
LeafGuard operates primarily offline on farmer handheld units, with periodic asynchronous delta synchronization to the regional farm analytics server when 4G/Wi-Fi is available.

## 2. On-Device Edge Pipeline
The edge daemon runs an optimized deep neural network for continuous leaf spotting:
- **Selected Edge Architecture:** MobileNetV3-Small (per decision D-17).
- **Inference Runtime:** ONNX Runtime / TensorRT INT8.
- **Latency Budget:** 14.2ms nominal inference time per frame.
- **Export Artifact:** `leafguard_mobilenet_v3_int8.engine`

## 3. Server-Side Retraining & Ingestion
Telemetry and low-confidence classifications are aggregated in batches of 100 images and uploaded for semi-supervised re-annotation.
