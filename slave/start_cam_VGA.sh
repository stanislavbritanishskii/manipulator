#!/bin/bash
CAMERA_ID=2
PC_IP="192.168.0.208"  # Change to your PC IP

python3  slave.py \
    --camera-id $CAMERA_ID \
    --host $PC_IP \
    --width 640 \
    --height 480 \
    --fps 30 \
    --quality 95
