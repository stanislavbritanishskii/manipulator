#!/bin/bash
CAMERA_ID=1
PC_IP="192.168.0.208"  # Change to your PC IP

python3  slave.py \
    --camera-id $CAMERA_ID \
    --host $PC_IP \
    --width 1280 \
    --height 720 \
    --fps 30 \
    --quality 95
